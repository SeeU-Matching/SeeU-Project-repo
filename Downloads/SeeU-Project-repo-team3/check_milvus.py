"""
Diagnostic script to check Milvus status and collections.
Run this to verify if data is properly stored in Milvus.
"""
import sys
import os

# Add path to matching_utils
sys.path.append(os.path.join(os.path.dirname(__file__), 'InfoMatching_Team1'))

try:
    from matching_utils import connect_milvus
    from pymilvus import utility, Collection
    
    print("=" * 50)
    print("Milvus Diagnostic Tool")
    print("=" * 50)
    print()
    
    # Connect to Milvus
    print("Connecting to Milvus...")
    try:
        connect_milvus()
        print("✓ Connected to Milvus successfully")
    except Exception as e:
        print(f"✗ Failed to connect to Milvus: {e}")
        print("\nMake sure:")
        print("1. Docker is running")
        print("2. Milvus is started (run launch_app.bat or docker-compose up in milvus_setup/)")
        sys.exit(1)
    
    print()
    print("Checking collections...")
    print("-" * 50)
    
    # Check resume collection
    has_resume = utility.has_collection("resume")
    if has_resume:
        resume_col = Collection("resume")
        resume_col.load()
        num_resumes = resume_col.num_entities
        print(f"✓ Resume collection exists")
        print(f"  - Number of entries: {num_resumes}")
        if num_resumes > 0:
            # Get a sample
            sample = resume_col.query(expr="sql_id >= 0", limit=1, output_fields=["sql_id", "name"])
            if sample:
                print(f"  - Sample entry: {sample[0]}")
    else:
        print("✗ Resume collection does NOT exist")
        print("  → Upload resumes first to create this collection")
    
    print()
    
    # Check job_postings collection
    has_job = utility.has_collection("job_postings")
    if has_job:
        job_col = Collection("job_postings")
        job_col.load()
        num_jobs = job_col.num_entities
        print(f"✓ Job postings collection exists")
        print(f"  - Number of entries: {num_jobs}")
        if num_jobs > 0:
            # Get a sample
            sample = job_col.query(expr="sql_id >= 0", limit=1, output_fields=["sql_id", "job_company", "job_title"])
            if sample:
                print(f"  - Sample entry: {sample[0]}")
    else:
        print("✗ Job postings collection does NOT exist")
        print("  → Upload job descriptions first to create this collection")
    
    print()
    print("-" * 50)
    print("Summary:")
    
    if has_resume and has_job:
        resume_col = Collection("resume")
        job_col = Collection("job_postings")
        resume_col.load()
        job_col.load()
        if resume_col.num_entities > 0 and job_col.num_entities > 0:
            print("✓ Both collections exist and have data")
            print("  → Matching should work. Check if search_results.csv was generated.")
        else:
            print("⚠ Both collections exist but one or both are empty")
            print("  → Upload data through the Streamlit app")
    elif has_resume or has_job:
        print("⚠ Only one collection exists")
        print("  → Upload both resumes and job descriptions")
    else:
        print("✗ No collections exist")
        print("  → Upload data through the Streamlit app first")
    
    print()
    print("=" * 50)
    
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

