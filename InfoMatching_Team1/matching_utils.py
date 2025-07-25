import pandas as pd
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, connections, utility
from FlagEmbedding import BGEM3FlagModel
from sentence_transformers import SentenceTransformer
import threading
import json
from jsonschema import validate, ValidationError
import os
from typing import List, Dict, Optional
import csv

# Model config
MODEL = {
    "bge-m3": {"loader": lambda: BGEM3FlagModel('BAAI/bge-m3', use_fp16=True), "dim": 1024},
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
                _model_cache[model_name] = MODEL[model_name]["loader"]()
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
        FieldSchema(name="job_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="job_company", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="job_title", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="job_application_url", dtype=DataType.VARCHAR, max_length=500)
    ]
    collection = create_or_load_collection(collection_name, dim, fields)
    texts = [f"{job['job_company']} {job['job_title']} {job['job_description']}" for job in job_postings]
    embeddings = generate_embeddings(texts, model_name=model_name)
    job_companies = [job["job_company"] for job in job_postings]
    job_titles = [job["job_title"] for job in job_postings]
    job_urls = [job["job_application_url"] for job in job_postings]
    collection.insert([
        embeddings,
        job_companies,
        job_titles,
        job_urls
    ])
    collection.flush()
    print(f"Inserted {len(job_postings)} job_postings into collection '{collection_name}'.")


def insert_resumes(resumes: List[Dict], model_name="bge-m3", collection_name="resume"):
    """Insert parsed resumes into Milvus after embedding."""
    connect_milvus()
    dim = MODEL[model_name]["dim"]
    fields = [
        FieldSchema(name="resume_id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="email", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="phone", dtype=DataType.VARCHAR, max_length=100)
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
    collection.insert([
        embeddings,
        names,
        emails,
        phones
    ])
    collection.flush()
    print(f"Inserted {len(resumes)} resumes into collection '{collection_name}'.")


def match_to_csv(matching, csv_path="search_results.csv"):
    if not matching:
        print("No matching result to save.")
        return
    headers = ["Index", "name", "job_id", "job_company", "job_title", "job_application_url", "distance"]
    import os
    file_exists = os.path.exists(csv_path)
    try:
        # Sort by distance (ascending: best matches first)
        matching_sorted = sorted(matching, key=lambda x: x.get("distance", float('inf')))
        with open(csv_path, mode="a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)
            # Only write header if file does not exist or is empty
            if not file_exists or os.stat(csv_path).st_size == 0:
                writer.writeheader()
            for idx, row in enumerate(matching_sorted, start=1):
                row_i = {"Index": idx, **row}
                writer.writerow(row_i)
        print(f"Matching results appended to '{csv_path}'.")
    except Exception as e:
        print(f"Failed to save CSV: {e}")


def match_resumes_to_jobs(
    resume_collection_name="resume",
    job_collection_name="job_postings",
    model_name="bge-m3",
    top_k: Optional[int] = None,
    csv_path="search_results.csv"
):
    """Match every resume to every job description, append results to CSV."""
    connect_milvus()
    # Load collections
    if not utility.has_collection(resume_collection_name) or not utility.has_collection(job_collection_name):
        raise RuntimeError("Resume or job collection does not exist in Milvus.")
    resume_col = Collection(name=resume_collection_name)
    job_col = Collection(name=job_collection_name)
    resume_col.load()
    job_col.load()
    # Get all resume embeddings and info
    resume_df = pd.DataFrame(resume_col.query(expr="resume_id >= 0", output_fields=["resume_id", "embedding", "name", "email", "phone"]))
    job_df = pd.DataFrame(job_col.query(expr="job_id >= 0", output_fields=["job_id", "embedding", "job_company", "job_title", "job_application_url"]))
    # Compute all-pairs similarity (L2 distance)
    from sklearn.metrics.pairwise import euclidean_distances
    import numpy as np
    resume_embs = np.vstack(resume_df["embedding"].tolist())
    job_embs = np.vstack(job_df["embedding"].tolist())
    dists = euclidean_distances(resume_embs, job_embs)
    # Prepare results
    results = []
    for i, resume_row in resume_df.iterrows():
        for j, job_row in job_df.iterrows():
            score = dists[i, j]
            results.append({
                "name": resume_row["name"],
                "job_id": job_row["job_id"],
                "job_company": job_row["job_company"],
                "job_title": job_row["job_title"],
                "job_application_url": job_row["job_application_url"],
                "distance": score
            })
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


def match_new_resumes_to_jobs(new_resumes, model_name="bge-m3", csv_path="search_results.csv"):
    connect_milvus()
    from pymilvus import Collection, utility
    if not utility.has_collection("job_postings"):
        print("No job postings in Milvus.")
        return
    job_col = Collection("job_postings")
    job_col.load()
    job_df = pd.DataFrame(job_col.query(expr="job_id >= 0", output_fields=["job_id", "embedding", "job_company", "job_title", "job_application_url"]))
    if job_df.empty:
        print("No jobs to match.")
        return

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
        dists = euclidean_distances([embedding], job_embs)[0]
        for j, job_row in job_df.iterrows():
            results.append({
                "name": name,
                "job_id": job_row["job_id"],
                "job_company": job_row["job_company"],
                "job_title": job_row["job_title"],
                "job_application_url": job_row["job_application_url"],
                "distance": dists[j]
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
    resume_df = pd.DataFrame(resume_col.query(expr="resume_id >= 0", output_fields=["resume_id", "embedding", "name", "email", "phone"]))
    if resume_df.empty:
        print("No resumes to match.")
        return

    # Prepare new job embeddings
    texts = [f"{job.get('job_company', '')} {job.get('job_title', '')} {job.get('job_description', '')}" for job in new_jobs]
    embeddings = generate_embeddings(texts, model_name=model_name)
    if isinstance(embeddings, list) and len(embeddings) > 0 and isinstance(embeddings[0], float):
        embeddings = [embeddings]
    job_infos = [(job.get("job_id", None), job.get("job_company", ""), job.get("job_title", ""), job.get("job_application_url", "")) for job in new_jobs]

    import numpy as np
    from sklearn.metrics.pairwise import euclidean_distances
    resume_embs = np.vstack(resume_df["embedding"].tolist())
    results = []
    for i, (embedding, (job_id, job_company, job_title, job_application_url)) in enumerate(zip(embeddings, job_infos)):
        dists = euclidean_distances(resume_embs, [embedding])[:, 0]
        for j, resume_row in resume_df.iterrows():
            results.append({
                "name": resume_row["name"],
                "job_id": job_id,
                "job_company": job_company,
                "job_title": job_title,
                "job_application_url": job_application_url,
                "distance": dists[j]
            })
    match_to_csv(results, csv_path=csv_path) 