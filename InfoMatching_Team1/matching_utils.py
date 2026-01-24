import pandas as pd
import os
import sys
import re

# Set environment variables early to avoid Windows stdout issues with tqdm
# This must be done BEFORE importing model-related modules
if sys.platform == 'win32':
    os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
    os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    # Disable tqdm completely for HuggingFace
    os.environ['HF_HUB_DISABLE_TQDM'] = '1'
    # Additional environment variables to disable tqdm
    os.environ['TQDM_DISABLE'] = '1'
    # Disable tqdm in huggingface_hub
    os.environ['HF_HUB_DISABLE_EXPERIMENTAL_WARNING'] = '1'

# Completely disable tqdm by redirecting its output to a null device
# This is safer than monkey-patching and prevents tqdm from causing errors
if sys.platform == 'win32':
    try:
        # Redirect stderr to null to prevent tqdm from writing to it
        # This is done before any imports that might use tqdm
        import io
        # Create a null file-like object
        class NullIO(io.TextIOWrapper):
            def __init__(self):
                pass
            def write(self, *args, **kwargs):
                pass
            def flush(self, *args, **kwargs):
                pass
            def close(self, *args, **kwargs):
                pass
        
        # Store original stderr
        _original_stderr = sys.stderr
        # Note: We don't actually replace stderr here because it might break other things
        # Instead, we rely on environment variables which should be sufficient
    except Exception:
        pass

from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, connections, utility
from FlagEmbedding import BGEM3FlagModel
from sentence_transformers import SentenceTransformer
import threading
import json
from jsonschema import validate, ValidationError
from typing import List, Dict, Optional
import csv
import time, traceback
import sqlite3
from datetime import datetime

# Model config
# Note: use_fp16=False for Windows compatibility
MODEL = {
    "bge-m3": {"loader": lambda: BGEM3FlagModel('BAAI/bge-m3', use_fp16=False), "dim": 1024},
    "all-MiniLM-L6-v2": {"loader": lambda: SentenceTransformer('all-MiniLM-L6-v2'), "dim": 384}
}

_model_cache = {}
_model_lock = threading.Lock()


def load_model(model_name="bge-m3"):
    """Lazily load and cache the embedding model."""
    with _model_lock:
        if model_name not in _model_cache:
            if model_name in MODEL:
                print(f"Loading embedding model: {model_name}")
                # Environment variables are already set at module import time
                # But ensure they're set again here as a safety measure
                if sys.platform == 'win32':
                    os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
                    os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
                    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
                    os.environ['HF_HUB_DISABLE_TQDM'] = '1'
                
                try:
                    # Try to load the model
                    # If it fails due to tqdm issues, we'll catch and provide alternatives
                    _model_cache[model_name] = MODEL[model_name]["loader"]()
                    print(f"Successfully loaded model: {model_name}")
                except (OSError, IOError) as e:
                    if "Invalid argument" in str(e) or "Errno 22" in str(e):
                        error_msg = (
                            f"Failed to load model {model_name} due to Windows/Streamlit compatibility issue.\n"
                            f"Error: {e}\n\n"
                            "Solutions:\n"
                            "1. Run 'download_model.bat' first to pre-download the model (recommended)\n"
                            "2. Or use the alternative model 'all-MiniLM-L6-v2' (smaller, faster)\n"
                            "3. Or restart Streamlit after running download_model.bat"
                        )
                        print(error_msg)
                        raise RuntimeError(error_msg) from e
                    else:
                        raise
                except Exception as e:
                    print(f"Error loading model {model_name}: {e}")
                    print("Try running download_model.bat first to pre-download the model.")
                    raise
            else:
                raise ValueError(f"Unsupported model: {model_name}")
        return _model_cache[model_name]


def generate_embeddings(texts, model_name="bge-m3"):
    """Generate embeddings for a list of texts using the specified model."""
    if isinstance(texts, str):
        texts = [texts]
    model = load_model(model_name)
    if model_name == "bge-m3":
            embeddings = model.encode(
            texts,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False
        )["dense_vecs"].tolist()
    else:
        embeddings = model.encode(texts)
    if len(embeddings) == 1:
        return embeddings[0]
    return embeddings


def connect_milvus(host="127.0.0.1", port="19530", user=None, password=None, secure=False, alias="default"):
    """Connect to Milvus vector DB."""
    if connections.has_connection(alias):
        return
    connect_params = {"host": host, "port": port, "secure": secure}
    if user and password:
        connect_params.update({"user": user, "password": password})
    connections.connect(alias, **connect_params)


# ==================== Hard Constraints ====================

def has_summer_before_graduation(graduation_time_str):
    """
    判断从当前时间到毕业时间之间是否还有暑假。
    
    规则：
    - 暑假通常指6-8月
    - 如果毕业时间在6月，说明6月就毕业了，无法利用该年暑假，返回False（推荐全职）
    - 如果毕业时间在6月之后（7-12月），说明还能利用该年暑假，返回True（推荐实习）
    - 如果毕业时间在明年或更晚，说明还有暑假，返回True（推荐实习）
    
    Args:
        graduation_time_str: 毕业时间，格式 "YYYY-MM" (例如 "2026-12")
    
    Returns:
        bool: True表示还有暑假（推荐实习），False表示没有暑假（推荐全职）
              如果毕业时间未指定或格式错误，返回False（推荐全职）
    """
    if not graduation_time_str or graduation_time_str.strip() == "":
        return False  # 未指定，推荐全职
    
    try:
        from datetime import datetime, date
        
        # 解析毕业时间
        grad_date = datetime.strptime(graduation_time_str.strip(), "%Y-%m").date()
        today = date.today()
        
        # 如果毕业时间已经过了，推荐全职
        if grad_date <= today:
            return False
        
        current_year = today.year
        current_month = today.month
        grad_year = grad_date.year
        grad_month = grad_date.month
        
        # 如果毕业年份 > 当前年份，肯定还有暑假（至少明年有）
        if grad_year > current_year:
            return True
        
        # 如果毕业年份 == 当前年份
        if grad_year == current_year:
            # 如果毕业月份 > 6（7-12月），说明还能利用该年暑假
            if grad_month > 6:
                return True
            # 如果毕业月份 == 6，说明6月就毕业了，无法利用该年暑假
            elif grad_month == 6:
                return False
            # 如果毕业月份 < 6（1-5月），说明在暑假之前就毕业了，没有暑假
            else:
                return False
        
        # 如果毕业年份 < 当前年份（不应该发生，但处理一下）
        return False
        
    except (ValueError, AttributeError) as e:
        print(f"Error parsing graduation time '{graduation_time_str}': {e}")
        return False  # 格式错误，推荐全职


def is_intern_position(job_title):
    """
    判断职位是否是实习职位（基于职位标题）。
    
    Args:
        job_title: 职位标题字符串
    
    Returns:
        bool: True表示是实习职位，False表示是全职职位
    """
    if not job_title:
        return False
    
    intern_keywords = ['intern', 'internship', 'co-op', 'coop', '实习', 'internship program']
    job_title_lower = str(job_title).lower()
    
    return any(keyword in job_title_lower for keyword in intern_keywords)


def check_intern_vs_fulltime_constraint(resume_graduation_time, job_title):
    """
    硬约束1：根据毕业时间和职位类型进行匹配。
    
    规则：
    - 如果到毕业时间之间还有暑假 → 推荐实习职位
    - 如果到毕业时间之间没有暑假 → 推荐全职职位
    - 如果毕业时间未指定 → 推荐全职职位
    
    Args:
        resume_graduation_time: 简历的毕业时间，格式 "YYYY-MM"
        job_title: 职位标题
    
    Returns:
        bool: True表示通过约束（可以推荐），False表示不通过约束（不推荐）
    """
    has_summer = has_summer_before_graduation(resume_graduation_time)
    is_intern = is_intern_position(job_title)
    
    # 如果还有暑假，应该推荐实习职位
    if has_summer:
        return is_intern
    # 如果没有暑假，应该推荐全职职位
    else:
        return not is_intern


def get_degree_level(degree_str):
    """
    从学位字符串中提取等级（简化版，格式已统一）。
    
    学位等级：
    - 3: PhD
    - 2: Master
    - 1: Bachelor
    - 0: 未知或无法识别
    
    Args:
        degree_str: 学位字符串，现在统一为 "Bachelor", "Master", 或 "PhD"
    
    Returns:
        int: 学位等级 (0-3)
    """
    if not degree_str:
        return 0
    
    # 转换为字符串并去除首尾空格
    degree = str(degree_str).strip()
    
    # 直接比较（格式已统一，不需要复杂的匹配）
    if degree == "PhD":
        return 3
    elif degree == "Master":
        return 2
    elif degree == "Bachelor":
        return 1
    
    return 0  # 未知或无法识别


def get_highest_degree_from_resume(degree_list):
    """
    从简历的学位列表中找出最高学位等级（简化版）。
    
    Args:
        degree_list: 学位列表，格式已统一为 ["Bachelor", "Master", "PhD"] 或类似
    
    Returns:
        int: 最高学位等级 (0=未知, 1=Bachelor, 2=Master, 3=PhD)
    """
    if not degree_list:
        return 0
    
    # 如果是字符串，尝试转换为列表（兼容旧数据）
    if isinstance(degree_list, str):
        # 尝试按逗号分割
        if ',' in degree_list:
            degree_list = [d.strip() for d in degree_list.split(',')]
        else:
            degree_list = [degree_list]
    
    # 确保是列表
    if not isinstance(degree_list, list):
        degree_list = [degree_list]
    
    max_level = 0
    for degree in degree_list:
        if degree and str(degree).strip():
            level = get_degree_level(str(degree))
            max_level = max(max_level, level)
    
    return max_level


def get_required_degree_level(qualification_str):
    """
    从职位要求的学历中提取最低要求等级（简化版）。
    
    规则：
    - 格式已统一为 "Bachelor", "Master", "PhD", 或 "Not specified"
    - "Not specified" 返回 0（无要求）
    
    Args:
        qualification_str: 职位要求的学历，格式已统一
    
    Returns:
        int: 要求的学位等级 (0=无要求, 1=Bachelor, 2=Master, 3=PhD)
    """
    if not qualification_str:
        return 0  # 未指定，无要求
    
    # 转换为字符串并去除首尾空格
    qualification = str(qualification_str).strip()
    
    # 检查是否是无要求
    if qualification.lower() in ["not specified", "not required", "none", "any", "no requirement"]:
        return 0  # 无要求
    
    # 直接获取等级（格式已统一）
    return get_degree_level(qualification)


def check_degree_constraint(resume_degree_list, job_qualification):
    """
    硬约束2：检查简历的最高学位是否满足职位的最低学历要求（简化版）。
    
    规则：
    - 简历最高学位 >= 职位最低要求 → 通过
    - 职位要求未指定（"Not specified"）→ 通过（无要求）
    - 否则 → 不通过
    
    Args:
        resume_degree_list: 简历的学位列表，格式已统一为 ["Bachelor", "Master", "PhD"]
        job_qualification: 职位的最低学历要求，格式已统一为 "Bachelor", "Master", "PhD", 或 "Not specified"
    
    Returns:
        bool: True表示通过约束，False表示不通过约束
    """
    resume_highest_level = get_highest_degree_from_resume(resume_degree_list)
    job_minimum_level = get_required_degree_level(job_qualification)
    
    # 如果职位要求未指定，通过约束（无要求）
    if job_minimum_level == 0:
        return True
    
    # 如果简历最高学位 >= 职位最低学历要求，通过约束
    return resume_highest_level >= job_minimum_level


def check_domain_constraint(resume_domains, job_domains):
    """
    硬约束3：检查简历的领域和职位的领域是否有交集。
    
    规则：
    - 简历的business_domain和JD的Experience domain有交集（至少一个相同）→ 通过
    - 完全无交集 → 不通过
    - 任一为空/None → 不通过（严格处理）
    
    Args:
        resume_domains: 简历的business_domain列表，例如 ["Computer Science", "Business"]
        job_domains: 职位的Experience domain列表，例如 ["Computer Science", "Engineering"]
    
    Returns:
        bool: True表示通过约束，False表示不通过约束
    """
    # 如果任一为空或None，不通过（严格处理）
    if not resume_domains or not job_domains:
        return False
    
    # 确保是列表
    # 如果是字符串，可能是逗号分隔的格式（从SQLite读取的）
    if isinstance(resume_domains, str):
        # 尝试按逗号分割，如果包含逗号说明是多个值
        if ',' in resume_domains:
            resume_domains = [d.strip() for d in resume_domains.split(',') if d.strip()]
        else:
            resume_domains = [resume_domains.strip()] if resume_domains.strip() else []
    if isinstance(job_domains, str):
        # 尝试按逗号分割，如果包含逗号说明是多个值
        if ',' in job_domains:
            job_domains = [d.strip() for d in job_domains.split(',') if d.strip()]
        else:
            job_domains = [job_domains.strip()] if job_domains.strip() else []
    
    # 如果已经是列表，确保元素是字符串
    if isinstance(resume_domains, list):
        resume_domains = [str(d).strip() for d in resume_domains if d]
    if isinstance(job_domains, list):
        job_domains = [str(d).strip() for d in job_domains if d]
    
    # 转换为小写列表进行比较（忽略大小写）
    resume_domains_lower = [d.lower() for d in resume_domains if d]
    job_domains_lower = [d.lower() for d in job_domains if d]
    
    # 如果转换后任一为空，不通过
    if not resume_domains_lower or not job_domains_lower:
        return False
    
    # 检查是否有交集
    resume_set = set(resume_domains_lower)
    job_set = set(job_domains_lower)
    
    # 有交集 → 通过
    return len(resume_set & job_set) > 0


def create_or_load_collection(collection_name: str, dim: int, fields: List[FieldSchema], overwrite: bool = False) -> Collection:
    """Create or load a Milvus collection with the given schema."""
    if overwrite and utility.has_collection(collection_name):
        utility.drop_collection(collection_name)
    if utility.has_collection(collection_name):
        collection = Collection(name=collection_name)
    else:
        schema = CollectionSchema(fields, description=f"{collection_name} with embeddings")
        collection = Collection(name=collection_name, schema=schema)
        collection.flush()
    if len(collection.indexes) == 0:
        index_params = {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 128}}
        collection.create_index(field_name="embedding", index_params=index_params, index_name="embedding_index")
    return collection


def insert_job_descriptions(job_postings: List[Dict], model_name="bge-m3", collection_name="job_postings"):
    """Insert parsed job descriptions into Milvus after embedding."""
    connect_milvus()
    dim = MODEL[model_name]["dim"]
    fields = [
        FieldSchema(name="sql_id", dtype=DataType.INT64, is_primary=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="job_company", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="job_title", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="job_application_url", dtype=DataType.VARCHAR, max_length=1000),  # Increased from 500 to 1000
    ]
    collection = create_or_load_collection(collection_name, dim, fields)
    texts = [f"{job['job_company']} {job['job_title']} {job['job_description']}" for job in job_postings]
    embeddings = generate_embeddings(texts, model_name=model_name)
    job_companies = [job["job_company"] for job in job_postings]
    job_titles = [job["job_title"] for job in job_postings]
    # Truncate URLs if they exceed max_length (safety measure)
    job_urls = [str(job["job_application_url"])[:1000] if job.get("job_application_url") else "" for job in job_postings]
    sql_id = [job.get("id", 0) for job in job_postings]
    collection.insert([
        sql_id,
        embeddings,
        job_companies,
        job_titles,
        job_urls,
    ])
    collection.flush()
    print(f"Inserted {len(job_postings)} job_postings into collection '{collection_name}'.")


def insert_resumes(resumes: List[Dict], model_name="bge-m3", collection_name="resume"):
    """Insert parsed resumes into Milvus after embedding."""
    connect_milvus()
    dim = MODEL[model_name]["dim"]
    fields = [
        FieldSchema(name="sql_id", dtype=DataType.INT64,  is_primary=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="email", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="phone", dtype=DataType.VARCHAR, max_length=100),
    ]
    collection = create_or_load_collection(collection_name, dim, fields)
    texts = [f"{resume.get('name', '')} {resume.get('major', '')} {resume.get('tech_skills', '')} {resume.get('experiences', '')}" for resume in resumes]
    embeddings = generate_embeddings(texts, model_name=model_name)
    # Patch: Ensure embeddings is always a list of lists
    if isinstance(embeddings, list) and len(embeddings) > 0 and isinstance(embeddings[0], float):
        embeddings = [embeddings]
    names = [resume.get("name", "") for resume in resumes]
    emails = [resume.get("email", "") for resume in resumes]
    phones = [resume.get("phone", "") for resume in resumes]
    sql_id = [resume.get("id", 0) for resume in resumes]
    collection.insert([
        sql_id,
        embeddings,
        names,
        emails,
        phones,
        
    ])
    collection.flush()
    print(f"Inserted {len(resumes)} resumes into collection '{collection_name}'.")


def match_to_csv(matching, csv_path="search_results.csv"):
    if not matching:
        print("No matching result to save.")
        return
    headers = ["Index", "name", "job_id", "job_company", "job_title", "job_application_url", "distance", "create_date"]
    import os
    try:
        # Sort by distance (ascending: best matches first)
        matching_sorted = sorted(matching, key=lambda x: x.get("distance", float('inf')))
        # Use write mode ("w") to overwrite existing file instead of append
        with open(csv_path, mode="w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)
            writer.writeheader()
            for idx, row in enumerate(matching_sorted, start=1):
                row_i = {"Index": idx, **row}
                writer.writerow(row_i)
        print(f"Matching results saved to '{csv_path}' ({len(matching_sorted)} results).")
    except Exception as e:
        print(f"Failed to save CSV: {e}")
        import traceback
        traceback.print_exc()


def match_resumes_to_jobs(
    resume_collection_name="resume",
    job_collection_name="job_postings",
    model_name="bge-m3",
    top_k: Optional[int] = None,
    csv_path="search_results.csv"
):
    """Match every resume to every job description, overwrite results to CSV."""
    print(f"\n{'='*50}")
    print(f"Starting matching process...")
    print(f"CSV path: {os.path.abspath(csv_path)}")
    print(f"{'='*50}\n")
    
    try:
        connect_milvus()
        # Load collections
        if not utility.has_collection(resume_collection_name) or not utility.has_collection(job_collection_name):
            raise RuntimeError("Resume or job collection does not exist in Milvus.")
        resume_col = Collection(name=resume_collection_name)
        job_col = Collection(name=job_collection_name)
        resume_col.load()
        job_col.load()
        
        # Get all resume embeddings and info
        resume_df = pd.DataFrame(resume_col.query(expr="sql_id >= 0", output_fields=["sql_id", "embedding", "name", "email", "phone"]))
        job_df = pd.DataFrame(job_col.query(expr="sql_id >= 0", output_fields=["sql_id", "embedding", "job_company", "job_title", "job_application_url"]))
        
        print(f"Found {len(resume_df)} resumes and {len(job_df)} jobs in Milvus")
        
        if resume_df.empty:
            print("⚠️ Warning: No resumes found in Milvus!")
            return
        if job_df.empty:
            print("⚠️ Warning: No jobs found in Milvus!")
            return
        
        # HARD CONSTRAINTS: Get resume data from SQLite
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(script_dir, "..", "my_database.db")
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        
        # Get graduation times, degrees, and business_domains for all resumes
        resume_ids = resume_df['sql_id'].tolist()
        placeholders = ', '.join(['?'] * len(resume_ids))
        query = f"SELECT id, graduation_time, degree, business_domain FROM uploads WHERE id IN ({placeholders})"
        cursor.execute(query, resume_ids)
        resume_data = {}
        for row in cursor.fetchall():
            resume_data[row[0]] = {
                'graduation_time': row[1],
                'degree': row[2] if len(row) > 2 else None,
                'business_domain': row[3] if len(row) > 3 else None
            }
        
        # Get job qualifications, Experience domain, and created_at
        job_ids = job_df['sql_id'].tolist()
        placeholders = ', '.join(['?'] * len(job_ids))
        query = f"SELECT id, minimum_academic_qualification, experience_domain, created_at FROM job_description WHERE id IN ({placeholders})"
        cursor.execute(query, job_ids)
        job_data = {}
        for row in cursor.fetchall():
            job_data[row[0]] = {
                'minimum_academic_qualification': row[1] if len(row) > 1 else None,
                'experience_domain': row[2] if len(row) > 2 else None,
                'created_at': row[3] if len(row) > 3 else None
            }
        connection.close()
        
        # Compute all-pairs similarity (L2 distance)
        from sklearn.metrics.pairwise import euclidean_distances
        import numpy as np
        resume_embs = np.vstack(resume_df["embedding"].tolist())
        job_embs = np.vstack(job_df["embedding"].tolist())
        dists = euclidean_distances(resume_embs, job_embs)
        
        # Prepare results
        results = []
        constraint_stats = {
            'total_pairs': 0,
            'failed_constraint1': 0,
            'failed_constraint2': 0,
            'failed_constraint3': 0,
            'passed_all': 0
        }
        
        for i, resume_row in resume_df.iterrows():
            resume_id = resume_row["sql_id"]
            resume_info = resume_data.get(resume_id, {})
            graduation_time = resume_info.get('graduation_time', None)
            degree_list = resume_info.get('degree', None)
            resume_domains = resume_info.get('business_domain', None)
            
            for j, job_row in job_df.iterrows():
                constraint_stats['total_pairs'] += 1
                job_id = job_row["sql_id"]
                job_info = job_data.get(job_id, {})
                job_qualification = job_info.get('minimum_academic_qualification', None)
                job_domains = job_info.get('experience_domain', None)
                
                # HARD CONSTRAINT 1: Intern vs Full-time based on graduation time
                if not check_intern_vs_fulltime_constraint(graduation_time, job_row["job_title"]):
                    constraint_stats['failed_constraint1'] += 1
                    continue  # Skip this match if constraint fails
                
                # HARD CONSTRAINT 2: Degree requirement
                if not check_degree_constraint(degree_list, job_qualification):
                    constraint_stats['failed_constraint2'] += 1
                    continue  # Skip this match if constraint fails
                
                # HARD CONSTRAINT 3: Domain matching
                domain_check = check_domain_constraint(resume_domains, job_domains)
                if not domain_check:
                    constraint_stats['failed_constraint3'] += 1
                    # Debug: Print first few failures to help diagnose
                    if constraint_stats['failed_constraint3'] <= 3:
                        print(f"  [Debug] Domain constraint failed: resume_domains={resume_domains} (type={type(resume_domains)}), job_domains={job_domains} (type={type(job_domains)})")
                    continue  # Skip this match if constraint fails
                
                constraint_stats['passed_all'] += 1
                score = dists[i, j]
                # Use job's created_at as create_date, fallback to current time if None
                job_created_at = job_info.get('created_at', None)
                if job_created_at:
                    create_date = str(job_created_at)
                else:
                    create_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                results.append({
                    "name": resume_row["name"],
                    "job_id": job_row["sql_id"],
                    "job_company": job_row["job_company"],
                    "job_title": job_row["job_title"],
                    "job_application_url": job_row["job_application_url"],
                    "distance": score,
                    "create_date": create_date
                })
        
        # Print constraint statistics
        print(f"\n{'='*50}")
        print(f"Constraint Statistics:")
        print(f"  Total pairs checked: {constraint_stats['total_pairs']}")
        print(f"  Failed constraint 1 (Intern/Full-time): {constraint_stats['failed_constraint1']}")
        print(f"  Failed constraint 2 (Degree): {constraint_stats['failed_constraint2']}")
        print(f"  Failed constraint 3 (Domain): {constraint_stats['failed_constraint3']}")
        print(f"  Passed all constraints: {constraint_stats['passed_all']}")
        print(f"{'='*50}\n")
        
        # Optionally, keep only top_k matches per resume
        if top_k is not None:
            import heapq
            from collections import defaultdict
            top_results = defaultdict(list)
            for r in results:
                heapq.heappush(top_results[r["job_id"]], (r.get("distance", 0), r))
            filtered = []
            for job_id, heap in top_results.items():
                filtered.extend([r for _, r in heapq.nsmallest(top_k, heap)])
            results = filtered
        
        # Write to CSV using the new function
        match_to_csv(results, csv_path=csv_path)
        print(f"✓ Matching completed! {len(results)} results saved to '{os.path.abspath(csv_path)}'")
        
    except Exception as e:
        print(f"✗ Error in match_resumes_to_jobs: {e}")
        import traceback
        traceback.print_exc()
        raise


def match_new_resumes_to_jobs(new_resumes, model_name="bge-m3", csv_path="search_results.csv"):
    connect_milvus()
    from pymilvus import Collection, utility
    if not utility.has_collection("job_postings"):
        print("No job postings in Milvus.")
        return
    job_col = Collection("job_postings")
    job_col.load()
    job_df = pd.DataFrame(job_col.query(expr="sql_id >= 0", output_fields=["sql_id", "embedding", "job_company", "job_title", "job_application_url"]))
    if job_df.empty:
        print("No jobs to match.")
        return
    print("------------------------------")
    print(job_df)
    print("------------------------------")
    # HARD CONSTRAINTS
    # connect to sqlite
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "..", "my_database.db")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    # Get job qualifications, Experience domain, and created_at for HARD CONSTRAINTS
    job_ids = job_df['sql_id'].tolist()
    placeholders = ', '.join(['?'] * len(job_ids))
    query = f"SELECT id, minimum_academic_qualification, experience_domain, created_at FROM job_description WHERE id IN ({placeholders})"
    cursor.execute(query, job_ids)
    job_data = {}
    for row in cursor.fetchall():
        job_data[row[0]] = {
            'minimum_academic_qualification': row[1] if len(row) > 1 else None,
            'experience_domain': row[2] if len(row) > 2 else None,
            'created_at': row[3] if len(row) > 3 else None
        }
    connection.close()
    
    # Prepare new resume embeddings
    texts = [f"{resume.get('name', '')} {resume.get('major', '')} {resume.get('tech_skills', '')} {resume.get('experiences', '')}" for resume in new_resumes]
    embeddings = generate_embeddings(texts, model_name=model_name)
    if isinstance(embeddings, list) and len(embeddings) > 0 and isinstance(embeddings[0], float):
        embeddings = [embeddings]
    names = [resume.get("name", "") for resume in new_resumes]

    import numpy as np
    from sklearn.metrics.pairwise import euclidean_distances
    job_embs = np.vstack(job_df["embedding"].tolist())
    results = []

    for i, (embedding, name) in enumerate(zip(embeddings, names)):
        # Get graduation time, degree, and business_domain for this resume
        resume = new_resumes[i]
        graduation_time = resume.get("graduation_time", None)
        degree_list = resume.get("degree", None)
        resume_domains = resume.get("business_domain", None)
        
        dists = euclidean_distances([embedding], job_embs)[0]
        for j, job_row in job_df.iterrows():
            job_id = job_row["sql_id"]
            job_info = job_data.get(job_id, {})
            job_qualification = job_info.get('minimum_academic_qualification', None)
            job_domains = job_info.get('experience_domain', None)
            
            # HARD CONSTRAINT 1: Intern vs Full-time based on graduation time
            if not check_intern_vs_fulltime_constraint(graduation_time, job_row["job_title"]):
                continue  # Skip this match if constraint fails
            
            # HARD CONSTRAINT 2: Degree requirement
            if not check_degree_constraint(degree_list, job_qualification):
                continue  # Skip this match if constraint fails
            
            # HARD CONSTRAINT 3: Domain matching
            if not check_domain_constraint(resume_domains, job_domains):
                continue  # Skip this match if constraint fails
            
            # Use job's created_at as create_date, fallback to current time if None
            job_created_at = job_info.get('created_at', None)
            if job_created_at:
                create_date = str(job_created_at)
            else:
                create_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            results.append({
                "name": name,
                "job_id": job_row["sql_id"],
                "job_company": job_row["job_company"],
                "job_title": job_row["job_title"],
                "job_application_url": job_row["job_application_url"],
                "distance": dists[j],
                "create_date": create_date
            })
    match_to_csv(results, csv_path=csv_path)


def match_all_resumes_to_new_jobs(new_jobs, model_name="bge-m3", csv_path="search_results.csv"):
    connect_milvus()
    from pymilvus import Collection, utility
    if not utility.has_collection("resume"):
        print("No resumes in Milvus.")
        return
    resume_col = Collection("resume")
    resume_col.load()
    resume_df = pd.DataFrame(resume_col.query(expr="sql_id >= 0", output_fields=["sql_id", "embedding", "name", "email", "phone"]))
    if resume_df.empty:
        print("No resumes to match.")
        return
    
    print("############################")
    print(resume_df)
    print("############################")
    # HARD CONSTRAINTS
    # connect to sqlite
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "..", "my_database.db")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    # Get resume data for HARD CONSTRAINTS
    resume_ids = resume_df['sql_id'].tolist()
    placeholders = ', '.join(['?'] * len(resume_ids))
    query = f"SELECT id, graduation_time, degree, business_domain FROM uploads WHERE id IN ({placeholders})"
    cursor.execute(query, resume_ids)
    resume_data = {}
    for row in cursor.fetchall():
        resume_data[row[0]] = {
            'graduation_time': row[1],
            'degree': row[2] if len(row) > 2 else None,
            'business_domain': row[3] if len(row) > 3 else None
        }
    
    # Get job qualifications, Experience domain, and created_at
    job_ids = [job.get("id", None) for job in new_jobs]
    job_ids = [jid for jid in job_ids if jid is not None]
    job_data = {}
    if job_ids:
        placeholders = ', '.join(['?'] * len(job_ids))
        query = f"SELECT id, minimum_academic_qualification, experience_domain, created_at FROM job_description WHERE id IN ({placeholders})"
        cursor.execute(query, job_ids)
        for row in cursor.fetchall():
            job_data[row[0]] = {
                'minimum_academic_qualification': row[1] if len(row) > 1 else None,
                'experience_domain': row[2] if len(row) > 2 else None,
                'created_at': row[3] if len(row) > 3 else None
            }
    
    connection.close()

    # Prepare new job embeddings
    texts = [f"{job.get('job_company', '')} {job.get('job_title', '')} {job.get('job_description', '')}" for job in new_jobs]
    embeddings = generate_embeddings(texts, model_name=model_name)
    if isinstance(embeddings, list) and len(embeddings) > 0 and isinstance(embeddings[0], float):
        embeddings = [embeddings]
    job_infos = [(job.get("id", None), job.get("job_company", ""), job.get("job_title", ""), job.get("job_application_url", "")) for job in new_jobs]
    
    import numpy as np
    from sklearn.metrics.pairwise import euclidean_distances
    resume_embs = np.vstack(resume_df["embedding"].tolist())
    results = []
    for i, (embedding, (job_id, job_company, job_title, job_application_url)) in enumerate(zip(embeddings, job_infos)):
        job_info = job_data.get(job_id, {})
        job_qualification = job_info.get('minimum_academic_qualification', None)
        job_domains = job_info.get('experience_domain', None)
        dists = euclidean_distances(resume_embs, [embedding])[:, 0]
        for j, resume_row in resume_df.iterrows():
            resume_id = resume_row["sql_id"]
            resume_info = resume_data.get(resume_id, {})
            graduation_time = resume_info.get('graduation_time', None)
            degree_list = resume_info.get('degree', None)
            resume_domains = resume_info.get('business_domain', None)
            
            # HARD CONSTRAINT 1: Intern vs Full-time based on graduation time
            if not check_intern_vs_fulltime_constraint(graduation_time, job_title):
                continue  # Skip this match if constraint fails
            
            # HARD CONSTRAINT 2: Degree requirement
            if not check_degree_constraint(degree_list, job_qualification):
                continue  # Skip this match if constraint fails
            
            # HARD CONSTRAINT 3: Domain matching
            if not check_domain_constraint(resume_domains, job_domains):
                continue  # Skip this match if constraint fails
            
            # Use job's created_at as create_date, fallback to current time if None
            job_created_at = job_info.get('created_at', None)
            if job_created_at:
                create_date = str(job_created_at)
            else:
                create_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            results.append({
                "name": resume_row["name"],
                "job_id": job_id,
                "job_company": job_company,
                "job_title": job_title,
                "job_application_url": job_application_url,
                "distance": dists[j],
                "create_date": create_date
            })
    match_to_csv(results, csv_path=csv_path) 

def deleteResumeById(id):
    connect_milvus()
    from pymilvus import Collection, utility
    if not utility.has_collection("resume"):
        print("No resumes in Milvus.")
        return
    resume_col = Collection("resume")
    resume_col.load()
    delete_query = f"sql_id in [{id}]"
    resume_col.delete(delete_query)
    resume_col.flush()
    print(f"Successfully deleted resume with ID {id} from Milvus.")
    return

def deleteJDById(id):
    connect_milvus()
    from pymilvus import Collection, utility
    if not utility.has_collection("job_postings"):
        print("No JDs in Milvus.")
        return
    job_col = Collection("job_postings")
    job_col.load()
    delete_query = f"sql_id in [{id}]"
    job_col.delete(delete_query)
    job_col.flush()
    print(f"Successfully deleted jd with ID {id} from Milvus.")
    return
