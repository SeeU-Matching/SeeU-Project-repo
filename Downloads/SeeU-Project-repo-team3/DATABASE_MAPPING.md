# SQLite 与 Milvus 向量数据库映射说明

## 映射关系概述

项目使用 **`sql_id`** 字段作为 SQLite 数据库和 Milvus 向量数据库之间的映射桥梁。

## 映射机制

### 1. 数据结构映射

#### SQLite 数据库
- **表名**: `uploads` (简历) 和 `job_description` (职位描述)
- **主键**: `id` (INTEGER PRIMARY KEY AUTOINCREMENT)

#### Milvus 向量数据库
- **Collection**: `resume` 和 `job_postings`
- **主键**: `sql_id` (INT64) - **存储 SQLite 的 id 值**

### 2. 插入时的映射（SQLite → Milvus）

#### 简历映射
```python
# 位置: InfoMatching_Team1/matching_utils.py, insert_resumes()

# Milvus Collection Schema
fields = [
    FieldSchema(name="sql_id", dtype=DataType.INT64, is_primary=True),  # ← 映射字段
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
    FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=200),
    FieldSchema(name="email", dtype=DataType.VARCHAR, max_length=200),
    FieldSchema(name="phone", dtype=DataType.VARCHAR, max_length=100),
]

# 插入数据时，将 SQLite 的 id 存储到 Milvus 的 sql_id
sql_id = [resume.get("id", 0) for resume in resumes]  # ← 映射操作
collection.insert([
    sql_id,      # SQLite 的 id → Milvus 的 sql_id
    embeddings,
    names,
    emails,
    phones,
])
```

#### 职位描述映射
```python
# 位置: InfoMatching_Team1/matching_utils.py, insert_job_descriptions()

# Milvus Collection Schema
fields = [
    FieldSchema(name="sql_id", dtype=DataType.INT64, is_primary=True),  # ← 映射字段
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
    FieldSchema(name="job_company", dtype=DataType.VARCHAR, max_length=200),
    FieldSchema(name="job_title", dtype=DataType.VARCHAR, max_length=200),
    FieldSchema(name="job_application_url", dtype=DataType.VARCHAR, max_length=500),
]

# 插入数据时，将 SQLite 的 id 存储到 Milvus 的 sql_id
sql_id = [job.get("id", 0) for job in job_postings]  # ← 映射操作
collection.insert([
    sql_id,      # SQLite 的 id → Milvus 的 sql_id
    embeddings,
    job_companies,
    job_titles,
    job_urls,
])
```

### 3. 查询时的映射（Milvus → SQLite）

#### 匹配过程中的反向查询
```python
# 位置: InfoMatching_Team1/matching_utils.py, match_new_resumes_to_jobs()

# 1. 从 Milvus 查询出 sql_id
job_df = pd.DataFrame(job_col.query(
    expr="sql_id >= 0", 
    output_fields=["sql_id", "embedding", "job_company", "job_title", "job_application_url"]
))

# 2. 提取 sql_id 列表
job_ids = job_df['sql_id'].tolist()  # ← 获取 Milvus 中的 sql_id

# 3. 使用 sql_id 去 SQLite 查询详细信息
connection = sqlite3.connect(db_path)
cursor = connection.cursor()
placeholders = ', '.join(['?'] * len(job_ids))
query = f"SELECT * FROM job_description WHERE id IN ({placeholders})"  # ← 反向映射
cursor.execute(query, job_ids)  # 使用 sql_id 查询 SQLite
jd_content = cursor.fetchall()
```

## 映射流程图

```
┌─────────────────┐                    ┌──────────────────┐
│   SQLite DB     │                    │   Milvus DB      │
│                 │                    │                  │
│ uploads table   │                    │ resume collection│
│ ┌─────────────┐ │                    │ ┌──────────────┐ │
│ │ id (PK)     │ │ ────映射───────>  │ │ sql_id (PK)  │ │
│ │ name        │ │                    │ │ embedding    │ │
│ │ email       │ │                    │ │ name         │ │
│ │ ...         │ │                    │ │ email        │ │
│ └─────────────┘ │                    │ └──────────────┘ │
│                 │                    │                  │
│ job_description │                    │ job_postings     │
│ ┌─────────────┐ │                    │ ┌──────────────┐ │
│ │ id (PK)     │ │ ────映射───────>  │ │ sql_id (PK)  │ │
│ │ company     │ │                    │ │ embedding    │ │
│ │ title       │ │                    │ │ job_company  │ │
│ │ ...         │ │                    │ │ job_title    │ │
│ └─────────────┘ │                    │ └──────────────┘ │
└─────────────────┘                    └──────────────────┘
```

## 映射的关键代码位置

### 1. 插入映射（SQLite → Milvus）
- **简历**: `InfoMatching_Team1/matching_utils.py` 第 175 行
  ```python
  sql_id = [resume.get("id", 0) for resume in resumes]
  ```
- **职位**: `InfoMatching_Team1/matching_utils.py` 第 143 行
  ```python
  sql_id = [job.get("id", 0) for job in job_postings]
  ```

### 2. 查询映射（Milvus → SQLite）
- **匹配函数**: `InfoMatching_Team1/matching_utils.py` 第 287-290 行
  ```python
  job_ids = job_df['sql_id'].tolist()
  query = f"SELECT * FROM job_description WHERE id IN ({placeholders})"
  cursor.execute(query, job_ids)
  ```

### 3. 匹配结果中的映射
- **结果生成**: `InfoMatching_Team1/matching_utils.py` 第 244 行
  ```python
  "job_id": job_row["sql_id"],  # 使用 sql_id 作为 job_id
  ```

## 映射的作用

1. **数据关联**: 通过 `sql_id` 可以快速从 Milvus 找到对应的 SQLite 记录
2. **详细信息查询**: Milvus 只存储向量和关键字段，完整信息从 SQLite 查询
3. **数据一致性**: 确保两个数据库通过 id 保持同步
4. **删除操作**: 可以通过 `sql_id` 在 Milvus 中删除对应的向量

## 注意事项

1. **主键一致性**: SQLite 的 `id` 必须与 Milvus 的 `sql_id` 保持一致
2. **删除操作**: 删除 SQLite 记录时，需要同步删除 Milvus 中的对应记录
3. **更新操作**: 更新 SQLite 记录时，需要重新生成 embedding 并更新 Milvus

## 相关函数

- `insert_resumes()` - 插入简历时建立映射
- `insert_job_descriptions()` - 插入职位时建立映射
- `match_new_resumes_to_jobs()` - 匹配时使用映射查询 SQLite
- `match_all_resumes_to_new_jobs()` - 匹配时使用映射查询 SQLite
- `deleteResumeById()` - 删除时使用 sql_id
- `deleteJDById()` - 删除时使用 sql_id

