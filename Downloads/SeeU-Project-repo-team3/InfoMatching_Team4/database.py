import sqlite3
import os
import sys

# Set environment variables early to avoid Windows stdout issues with tqdm
if sys.platform == 'win32':
    os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
    os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'

# Create SQLite database and table
connection = sqlite3.connect('my_database.db')
cursor = connection.cursor()

# table 1: resume
cursor.execute('''
    CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
# cursor.execute('''
#     CREATE TABLE IF NOT EXISTS uploads (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         student_name TEXT NOT NULL UNIQUE,
#         file_name TEXT NOT NULL,
#         file_path TEXT NOT NULL,
#         uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
# ''')

#SIMULATION - existing data
# student_name = "John Doe"
# file_name = "example.txt" # change to your testing file name
# file_path = "uploads/example.txt" # change to your testing file path

# insert data into table 1
# if new resume uploaded, update the existing record (only one record in the table for all the time)
# cursor.execute('''
#     INSERT INTO uploads (id, file_name, file_path, uploaded_at)
#     VALUES (1, ?, ?, CURRENT_TIMESTAMP)
#     ON CONFLICT (id) DO UPDATE SET  
#         file_name = excluded.file_name,
#         file_path = excluded.file_path,
#         uploaded_at = CURRENT_TIMESTAMP
# ''', (file_name, file_path))
# cursor.execute("INSERT INTO uploads (student_name, file_name, file_path) VALUES (?, ?, ?)", (student_name, file_name, file_path))
# cursor.execute("INSERT INTO uploads (file_name, file_path) VALUES (?, ?)", (file_name, file_path))


# table 2: job description
cursor.execute('''
    CREATE TABLE IF NOT EXISTS job_description (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_company TEXT NOT NULL,                    
        job_title TEXT NOT NULL,
        job_description TEXT NOT NULL,
        job_application_url TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
# cursor.execute('''
#     CREATE TABLE IF NOT EXISTS job_description (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         job_company TEXT NOT NULL,                    
#         job_title TEXT NOT NULL,
#         job_description TEXT NOT NULL,
#         job_application_url TEXT NOT NULL,
#         company_industry_field TEXT,
#         major TEXT,
#         tech_skills TEXT,
#         graduation_time TEXT,
#         qualification TEXT, 
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
# ''')
#SIMULATION - existing data 
# job_company = "Google" 
# job_title = "Software Engineer" 
# job_description = "We are looking for a software engineer to join our team. The ideal candidate will have experience in software development and threat intelligence." 
# job_application_url = "https://www.google.com/about/careers/applications/jobs/results/93187212962603718-software-engineer-google-threat-intelligence" 
# cursor.execute("INSERT INTO job_description (job_company, job_title, job_description, job_application_url) VALUES (?, ?, ?, ?)", (job_company, job_title, job_description, job_application_url))

# job_company = "Microsoft" 
# job_title = "Software Engineer - AI/ML" 
# job_description = "You will develop software, tools, and code to be used in support of design, infrastructure, and technology platforms including large and small language models (LLMs/SLMs)." 
# job_application_url = "https://jobs.careers.microsoft.com/global/en/share/1798164/?utm_source=Job Share&utm_campaign=Copy-job-share" 
# cursor.execute("INSERT INTO job_description (job_company, job_title, job_description, job_application_url) VALUES (?, ?, ?, ?)", (job_company, job_title, job_description, job_application_url))

# job_company = "Meta"
# job_title = "Software Engineer, Infrastructure"
# job_description = "Meta is seeking experienced full-stack Software Engineers to join our product teams."
# job_application_url = "https://www.metacareers.com/jobs/804955741151464/"
# cursor.execute("INSERT INTO job_description (job_company, job_title, job_description, job_application_url) VALUES (?, ?, ?, ?)", (job_company, job_title, job_description, job_application_url))


# # table 3: job matching result
# # cursor.execute('''
# #     CREATE TABLE IF NOT EXISTS job_matching_result (
# #         id INTEGER PRIMARY KEY AUTOINCREMENT,
# #         job_id INTEGER NOT NULL,
# #         matching_score REAL NOT NULL,
# #         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# #     )
# # ''')
# cursor.execute('''
#     CREATE TABLE IF NOT EXISTS job_matching_result (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         job_id INTEGER NOT NULL,
#         resume_id INTEGER NOT NULL,
#         student_name TEXT NOT NULL,
#         matching_score REAL NOT NULL,
#         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     )
# ''')
# #SIMULATION
# job_id = 1
# resume_id = 1
# student_name = "John Doe"
# matching_score = 0.8
# cursor.execute("INSERT INTO job_matching_result (job_id, resume_id, student_name, matching_score) VALUES (?, ?, ?, ?)", (job_id, resume_id, student_name, matching_score))
# # cursor.execute("INSERT INTO job_matching_result (job_id, resume_id, matching_score) VALUES (?, ?, ?)", (job_id, resume_id, matching_score))
# # cursor.execute("INSERT INTO job_matching_result (job_id, matching_score) VALUES (?, ?)", (job_id, matching_score))

# job_id = 3
# resume_id = 1
# student_name = "John Doe"
# matching_score = 0.6
# cursor.execute("INSERT INTO job_matching_result (job_id, resume_id, student_name, matching_score) VALUES (?, ?, ?, ?)", (job_id, resume_id, student_name, matching_score))
# # cursor.execute("INSERT INTO job_matching_result (job_id, resume_id, matching_score) VALUES (?, ?, ?)", (job_id, resume_id, matching_score))
# # cursor.execute("INSERT INTO job_matching_result (job_id, matching_score) VALUES (?, ?)", (job_id, matching_score))

# job_id = 2
# resume_id = 1
# student_name = "John Doe"
# matching_score = 0.2
# cursor.execute("INSERT INTO job_matching_result (job_id, resume_id, student_name, matching_score) VALUES (?, ?, ?, ?)", (job_id, resume_id, student_name, matching_score))
# # cursor.execute("INSERT INTO job_matching_result (job_id, resume_id, matching_score) VALUES (?, ?, ?)", (job_id, resume_id, matching_score))
# # cursor.execute("INSERT INTO job_matching_result (job_id, matching_score) VALUES (?, ?)", (job_id, matching_score))


connection.commit()
connection.close()

# --- Milvus Consistency Patch ---
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'InfoMatching_Team1')))
from matching_utils import insert_resumes, insert_job_descriptions, match_resumes_to_jobs, connect_milvus
from pymilvus import utility

MODEL_NAME = "bge-m3"

# Read resumes and jobs from SQLite database
db_path = os.path.join(os.path.dirname(__file__), '..', 'my_database.db')
connection = sqlite3.connect(db_path)
cursor = connection.cursor()

# Read resumes from uploads table
cursor.execute("SELECT * FROM uploads")
resume_rows = cursor.fetchall()
resume_columns = [desc[0] for desc in cursor.description]
resumes = [dict(zip(resume_columns, row)) for row in resume_rows]

# Clean up resumes: ensure all string fields are not None
for resume in resumes:
    for key in ["name", "email", "phone"]:
        if key not in resume or resume[key] is None:
            resume[key] = ""

# Read jobs from job_description table
cursor.execute("SELECT * FROM job_description")
job_rows = cursor.fetchall()
job_columns = [desc[0] for desc in cursor.description]
jobs = [dict(zip(job_columns, row)) for row in job_rows]

# Clean up jobs: ensure all string fields are not None
for job in jobs:
    for key in ["job_company", "job_title", "job_description", "job_application_url"]:
        if key not in job or job[key] is None:
            job[key] = ""

connection.close()

# Connect to Milvus first!
connect_milvus()

# Drop old collections to avoid dimension mismatch
for collection_name in ["resume", "job_postings"]:
    if utility.has_collection(collection_name):
        utility.drop_collection(collection_name)

# Insert data using the same model
if resumes:
    insert_resumes(resumes, model_name=MODEL_NAME)
if jobs:
    insert_job_descriptions(jobs, model_name=MODEL_NAME)

# Run matching and generate CSV
try:
    match_resumes_to_jobs(model_name=MODEL_NAME)
    print("search_results.csv created successfully!")
except Exception as e:
    print(f"Failed to create search_results.csv: {e}")

print("Data inserted successfully!")