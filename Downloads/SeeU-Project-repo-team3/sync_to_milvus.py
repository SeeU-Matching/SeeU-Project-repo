"""
Sync data from SQLite database to Milvus.
This script will read all resumes and job descriptions from SQLite
and insert them into Milvus with embeddings.
"""
import sqlite3
import os
import sys

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), 'InfoMatching_Team1'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'InfoMatching_Team3'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'InfoMatching_Team2'))

from matching_utils import connect_milvus, insert_resumes, insert_job_descriptions
from resume_interface import read_resume
from jd_function import extract_job_data

def sync_resumes():
    """Sync resumes from SQLite to Milvus."""
    print("=" * 50)
    print("Syncing Resumes to Milvus")
    print("=" * 50)
    
    # Connect to SQLite
    db_path = os.path.join(os.path.dirname(__file__), 'my_database.db')
    if not os.path.exists(db_path):
        print(f"✗ Database file not found: {db_path}")
        return False
    
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    
    # Get all resumes
    cursor.execute("SELECT id, file_name, file_path FROM uploads")
    resumes = cursor.fetchall()
    
    if not resumes:
        print("No resumes found in database.")
        return False
    
    print(f"Found {len(resumes)} resume(s) in database")
    
    # Connect to Milvus
    try:
        connect_milvus()
        from pymilvus import utility
        if utility.has_collection("resume"):
            utility.drop_collection("resume")
            print("Dropped existing resume collection")
    except Exception as e:
        print(f"Error connecting to Milvus: {e}")
        return False
    
    # Process each resume
    resumes_to_insert = []
    uploads_dir = os.path.join(os.path.dirname(__file__), 'InfoMatching_Team4', 'uploads')
    
    for resume_id, file_name, file_path in resumes:
        print(f"Processing: {file_name}...")
        try:
            # Read resume file
            full_path = os.path.join(uploads_dir, file_name) if not os.path.isabs(file_path) else file_path
            if not os.path.exists(full_path):
                print(f"  ⚠ File not found: {full_path}")
                continue
            
            # Extract data
            with open(full_path, 'rb') as f:
                extracted_data = read_resume(file_object=f)
                extracted_data['id'] = resume_id
                extracted_data['file_name'] = file_name
                resumes_to_insert.append(extracted_data)
                print(f"  ✓ Extracted data for {file_name}")
        except Exception as e:
            print(f"  ✗ Error processing {file_name}: {e}")
            import traceback
            traceback.print_exc()
    
    if not resumes_to_insert:
        print("No resumes to insert.")
        return False
    
    # Insert into Milvus
    try:
        print(f"\nInserting {len(resumes_to_insert)} resume(s) into Milvus...")
        insert_resumes(resumes_to_insert, model_name="bge-m3")
        print("✓ Resumes synced successfully!")
        return True
    except Exception as e:
        print(f"✗ Error inserting resumes: {e}")
        import traceback
        traceback.print_exc()
        return False


def sync_job_descriptions():
    """Sync job descriptions from SQLite to Milvus."""
    print("\n" + "=" * 50)
    print("Syncing Job Descriptions to Milvus")
    print("=" * 50)
    
    # Connect to SQLite
    db_path = os.path.join(os.path.dirname(__file__), 'my_database.db')
    if not os.path.exists(db_path):
        print(f"✗ Database file not found: {db_path}")
        return False
    
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    
    # Get all job descriptions
    cursor.execute("SELECT id, job_company, job_title, job_description, job_application_url FROM job_description")
    jobs = cursor.fetchall()
    
    if not jobs:
        print("No job descriptions found in database.")
        return False
    
    print(f"Found {len(jobs)} job description(s) in database")
    
    # Connect to Milvus
    try:
        connect_milvus()
    except Exception as e:
        print(f"Error connecting to Milvus: {e}")
        return False
    
    # Prepare job data
    jobs_to_insert = []
    for job_id, company, title, description, url in jobs:
        jobs_to_insert.append({
            'id': job_id,
            'job_company': company or '',
            'job_title': title or '',
            'job_description': description or '',
            'job_application_url': url or ''
        })
        print(f"  ✓ Prepared: {company} - {title}")
    
    if not jobs_to_insert:
        print("No jobs to insert.")
        return False
    
    # Insert into Milvus
    try:
        print(f"\nInserting {len(jobs_to_insert)} job description(s) into Milvus...")
        insert_job_descriptions(jobs_to_insert, model_name="bge-m3")
        print("✓ Job descriptions synced successfully!")
        return True
    except Exception as e:
        print(f"✗ Error inserting job descriptions: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_matching():
    """Run matching after syncing."""
    print("\n" + "=" * 50)
    print("Running Matching")
    print("=" * 50)
    
    try:
        from matching_utils import match_resumes_to_jobs
        connect_milvus()
        from pymilvus import utility, Collection
        
        if not utility.has_collection("resume") or not utility.has_collection("job_postings"):
            print("✗ Collections not found. Please sync data first.")
            return False
        
        resume_col = Collection("resume")
        job_col = Collection("job_postings")
        resume_col.load()
        job_col.load()
        
        if resume_col.num_entities == 0 or job_col.num_entities == 0:
            print("✗ One or both collections are empty.")
            return False
        
        print(f"Resumes: {resume_col.num_entities}, Jobs: {job_col.num_entities}")
        print("Running matching...")
        match_resumes_to_jobs(csv_path="search_results.csv")
        print("✓ Matching completed! Check search_results.csv")
        return True
    except Exception as e:
        print(f"✗ Error running matching: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Sync SQLite to Milvus Tool")
    print("=" * 50)
    print()
    
    # Sync resumes
    resume_success = sync_resumes()
    
    # Sync job descriptions
    job_success = sync_job_descriptions()
    
    # Run matching if both succeeded
    if resume_success and job_success:
        run_matching()
    
    print("\n" + "=" * 50)
    print("Sync Complete")
    print("=" * 50)

