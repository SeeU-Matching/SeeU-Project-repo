import streamlit as st
import sqlite3
import os
import pandas as pd
import sys
import re
import time
import gc

# On Windows, force UTF-8 for stdout/stderr so Unicode from libs (e.g. embedding model) does not cause GBK errors
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
    os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['HF_HUB_DISABLE_TQDM'] = '1'

# Append the path to the parent directory of InfoMatching_Team2
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../InfoMatching_Team2')))
# JD extraction: use jd_function (local Qwen2-3B or OpenAI) so upload-to-SQL and downstream use the same extractor.
from jd_function import extract_job_data
# Import Milvus embedding/insert function
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../InfoMatching_Team1')))
from matching_utils import insert_job_descriptions, deleteJDById

def open_db(db_path: str) -> sqlite3.Connection:
    """
    Open SQLite connection with retry/backoff to avoid 'database is locked'
    during Streamlit reruns or long-running uploads.
    """
    last_err = None
    for attempt in range(6):
        try:
            conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
            try:
                conn.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            # WAL allows readers during writes and reduces lock contention.
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except Exception:
                pass
            return conn
        except sqlite3.OperationalError as e:
            last_err = e
            if "locked" in str(e).lower():
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise
    raise last_err if last_err else sqlite3.OperationalError("database is locked")


def sanitize_column_name(name):
    return re.sub(r'\W|^(?=\d)', '_', name).lower()

def main():
    st.markdown("<h1 style='font-size:24px;'>Job Description</h1>", unsafe_allow_html=True)

    with st.sidebar:
        st.header("Upload Job Descriptions")
        uploaded_file = st.file_uploader("Upload Excel or CSV File", type=["xlsx", "csv"])
        st.caption("If JD is already in the database but matching says collections missing, use:")
        if st.button("Sync JD from database to Milvus"):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "..", "..", "..", "my_database.db")
            if not os.path.exists(db_path):
                st.error("Database file not found.")
            else:
                try:
                    connection = open_db(db_path)
                    cursor = connection.cursor()
                    cursor.execute("SELECT id, job_company, job_title, job_description, job_application_url FROM job_description")
                    rows = cursor.fetchall()
                    connection.close()
                    if not rows:
                        st.warning("No job descriptions in database. Upload a file first.")
                    else:
                        from matching_utils import connect_milvus, insert_job_descriptions
                        from pymilvus import utility
                        connect_milvus()
                        if utility.has_collection("job_postings"):
                            utility.drop_collection("job_postings")
                        batch = [{"id": r[0], "job_company": r[1] or "", "job_title": r[2] or "", "job_description": r[3] or "", "job_application_url": r[4] or ""} for r in rows]
                        insert_job_descriptions(batch, model_name="bge-m3")
                        st.success(f"Synced {len(batch)} job(s) from database to Milvus. You can run matching on the Result page.")
                except Exception as e:
                    st.error(f"Sync failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "..", "..", "..", "my_database.db")
    # Read schema (with retry) – keep the connection short-lived.
    try:
        connection = open_db(db_path)
        cursor = connection.cursor()
        cursor.execute("PRAGMA table_info(job_description)")
        column_names = [info[1] for info in cursor.fetchall()]
        connection.close()
    except Exception as e:
        st.error(f"Failed to open database: {e}")
        st.info("If you have another upload running, wait for it to finish and retry.")
        return

    if uploaded_file is not None:
        filename = (getattr(uploaded_file, "name", "") or "").lower()
        required_cols = {"job_company", "job_title", "job_description", "job_application_url"}
        CHUNK_ROWS = 2000
        BATCH_COMMIT = 1000

        def safe_str(v):
            try:
                if pd.isna(v):
                    return ""
            except Exception:
                pass
            return "" if v is None else str(v).strip()

        def write_prepared_to_db(prepared_rows, connection, cursor, existing_columns_ref):
            if not prepared_rows:
                return 0
            all_keys = set()
            for r in prepared_rows:
                all_keys.update({sanitize_column_name(k) for k in r.keys()})
            new_cols = all_keys - existing_columns_ref[0]
            for col in sorted(new_cols):
                cursor.execute(f"ALTER TABLE job_description ADD COLUMN {col} TEXT")
            existing_columns_ref[0] |= new_cols
            written = 0
            for i, data in enumerate(prepared_rows):
                cursor.execute(
                    "SELECT COUNT(*) FROM job_description WHERE job_company = ? AND job_title = ?",
                    (data["job_company"], data["job_title"])
                )
                count = cursor.fetchone()[0]
                if count == 0:
                    cols = ", ".join(data.keys())
                    placeholders = ", ".join(["?"] * len(data))
                    cursor.execute(f"INSERT INTO job_description ({cols}) VALUES ({placeholders})", list(data.values()))
                else:
                    upd = ", ".join([f"{k} = ?" for k in data.keys()])
                    cursor.execute(
                        f"UPDATE job_description SET {upd} WHERE job_company = ? AND job_title = ?",
                        list(data.values()) + [data["job_company"], data["job_title"]]
                    )
                written += 1
                if (i + 1) % BATCH_COMMIT == 0:
                    connection.commit()
            connection.commit()
            return written

        try:
            if filename.endswith(".csv"):
                # Detect encoding with a small read
                enc = None
                for e in ["utf-8", "utf-8-sig", "gb18030", "gbk", "cp1252", "latin1"]:
                    try:
                        uploaded_file.seek(0)
                        pd.read_csv(uploaded_file, encoding=e, nrows=5)
                        enc = e
                        break
                    except Exception:
                        pass
                if enc is None:
                    enc = "utf-8"
                    uploaded_file.seek(0)
                    st.warning("CSV encoding fallback: utf-8 with replacement. Re-export as UTF-8 if garbled.")
                uploaded_file.seek(0)
                reader = pd.read_csv(uploaded_file, encoding=enc, encoding_errors="replace" if enc == "utf-8" else "strict", chunksize=CHUNK_ROWS)
            else:
                df = pd.read_excel(uploaded_file)
                df.columns = [str(c).strip() for c in df.columns]
                missing = sorted(required_cols - set(df.columns))
                if missing:
                    st.error(f"Missing required columns: {missing}")
                    return
                if len(df) > 5000:
                    st.warning(f"**Large file:** {len(df):,} rows. Processing in batches to reduce memory. Do not refresh.")
                reader = None
        except Exception as e:
            st.error(f"Failed to read uploaded file: {e}")
            return

        skipped_missing_required = 0
        filled_empty_url = 0
        total_written = 0
        first_extraction_error = None
        connection = open_db(db_path)
        cursor = connection.cursor()
        cursor.execute("PRAGMA table_info(job_description)")
        existing_columns_ref = [{info[1].lower() for info in cursor.fetchall()}]

        try:
            if filename.endswith(".csv"):
                for chunk in reader:
                    chunk.columns = [str(c).strip() for c in chunk.columns]
                    if required_cols - set(chunk.columns):
                        st.error(f"Missing required columns. Expected: job_company, job_title, job_description, job_application_url")
                        break
                    prepared_rows = []
                    for _, row in chunk.iterrows():
                        job_company = safe_str(row.get("job_company"))
                        job_title = safe_str(row.get("job_title"))
                        job_description = safe_str(row.get("job_description"))
                        job_application_url = safe_str(row.get("job_application_url"))
                        if not job_company or not job_title or not job_description:
                            skipped_missing_required += 1
                            continue
                        if not job_application_url:
                            filled_empty_url += 1
                        extracted_data = extract_job_data(job_description)
                        extra_data = {}
                        if isinstance(extracted_data, dict) and "error" not in extracted_data:
                            extra_data = {sanitize_column_name(k): (", ".join(v) if isinstance(v, list) else v) for k, v in extracted_data.items()}
                        elif isinstance(extracted_data, dict) and "error" in extracted_data:
                            if first_extraction_error is None:
                                first_extraction_error = extracted_data.get("error", "Unknown error")
                            extra_data = {}
                        prepared_rows.append({
                            "job_company": job_company, "job_title": job_title,
                            "job_description": job_description, "job_application_url": job_application_url,
                            **extra_data
                        })
                    total_written += write_prepared_to_db(prepared_rows, connection, cursor, existing_columns_ref)
                    del prepared_rows
                    gc.collect()
            else:
                for start in range(0, len(df), CHUNK_ROWS):
                    chunk = df.iloc[start : start + CHUNK_ROWS]
                    prepared_rows = []
                    for _, row in chunk.iterrows():
                        job_company = safe_str(row.get("job_company"))
                        job_title = safe_str(row.get("job_title"))
                        job_description = safe_str(row.get("job_description"))
                        job_application_url = safe_str(row.get("job_application_url"))
                        if not job_company or not job_title or not job_description:
                            skipped_missing_required += 1
                            continue
                        if not job_application_url:
                            filled_empty_url += 1
                        extracted_data = extract_job_data(job_description)
                        extra_data = {}
                        if isinstance(extracted_data, dict) and "error" not in extracted_data:
                            extra_data = {sanitize_column_name(k): (", ".join(v) if isinstance(v, list) else v) for k, v in extracted_data.items()}
                        elif isinstance(extracted_data, dict) and "error" in extracted_data:
                            if first_extraction_error is None:
                                first_extraction_error = extracted_data.get("error", "Unknown error")
                            extra_data = {}
                        prepared_rows.append({
                            "job_company": job_company, "job_title": job_title,
                            "job_description": job_description, "job_application_url": job_application_url,
                            **extra_data
                        })
                    total_written += write_prepared_to_db(prepared_rows, connection, cursor, existing_columns_ref)
                    del prepared_rows
                    gc.collect()
        finally:
            connection.close()

        if first_extraction_error:
            st.warning(f"JD extraction failed (rows saved with basic fields only). First error: {first_extraction_error}")
        if skipped_missing_required > 0:
            st.warning(f"Skipped {skipped_missing_required} row(s) with empty job_company/job_title/job_description.")
        if filled_empty_url > 0:
            st.info(f"Filled {filled_empty_url} empty job_application_url value(s) with empty string.")

        if total_written > 0:
            try:
                from matching_utils import insert_job_descriptions, match_resumes_to_jobs
                from pymilvus import utility, Collection
                if utility.has_collection("job_postings"):
                    utility.drop_collection("job_postings")
                connection = open_db(db_path)
                cursor = connection.cursor()
                cursor.execute("SELECT id, job_company, job_title, job_description, job_application_url FROM job_description")
                MILVUS_BATCH = 2000
                total_milvus = 0
                while True:
                    rows = cursor.fetchmany(MILVUS_BATCH)
                    if not rows:
                        break
                    batch = [
                        {"id": r[0], "job_company": r[1] or "", "job_title": r[2] or "", "job_description": r[3] or "", "job_application_url": r[4] or ""}
                        for r in rows
                    ]
                    insert_job_descriptions(batch, model_name="bge-m3")
                    total_milvus += len(batch)
                    del batch
                    gc.collect()
                connection.close()
                if utility.has_collection("resume") and utility.has_collection("job_postings"):
                    resume_col = Collection("resume")
                    job_col = Collection("job_postings")
                    resume_col.load()
                    job_col.load()
                    if resume_col.num_entities > 0 and job_col.num_entities > 0:
                        csv_path = os.path.abspath(os.path.join(script_dir, "..", "..", "..", "search_results.csv"))
                        match_resumes_to_jobs(csv_path=csv_path)
                        try:
                            res_df = pd.read_csv(csv_path)
                            if len(res_df) == 0:
                                st.warning(f"[OK] {total_written} job(s) uploaded, matching ran but **0 pairs** passed hard constraints (degree/domain/intern). Check resume and JD fields.")
                            else:
                                st.success(f"[OK] {total_written} job(s) uploaded, {total_milvus} in Milvus, {len(res_df)} match(es) written.")
                        except Exception:
                            st.success(f"[OK] {total_written} job(s) uploaded, {total_milvus} in Milvus, matching done.")
                    else:
                        st.warning(f"[OK] {total_written} job(s) uploaded and embedded. Upload resumes to enable matching.")
                else:
                    st.warning(f"[OK] {total_written} job(s) uploaded and embedded. Upload resumes to enable matching.")
            except Exception as e:
                st.error(f"Error inserting job descriptions into Milvus: {e}")
                st.info("Job descriptions were saved to database. Check Milvus connection.")
                import traceback
                st.code(traceback.format_exc())
    
    # Open a fresh connection for browsing/filtering below
    try:
        connection = open_db(db_path)
        cursor = connection.cursor()
        cursor.execute("PRAGMA table_info(job_description)")
        column_names = [info[1] for info in cursor.fetchall()]
    except Exception as e:
        st.error(f"Failed to open database for browsing: {e}")
        return

    # Only show these columns: original JD fields + created_at/created_date + hard-constraint fields
    allowed_display = {'id', 'job_company', 'job_title', 'job_description', 'job_application_url',
                      'created_at', 'created_date', 'minimum_academic_qualification', 'experience_domain'}
    essential_columns = ['job_company', 'job_title', 'id']
    allowed_optional = [c for c in ['job_description', 'job_application_url', 'created_at', 'created_date',
                                    'minimum_academic_qualification', 'experience_domain'] if c in allowed_display]

    with st.sidebar:
        st.header("Filters")
        # Filter inputs only for allowed DB columns (exclude job_application_url for filter)
        filter_columns = [col for col in column_names if col in allowed_display and col != 'job_application_url']
        selectable_columns = [col for col in allowed_optional if col in column_names]
        if 'created_at' in column_names and 'created_date' not in selectable_columns:
            created_at_idx = selectable_columns.index('created_at') + 1 if 'created_at' in selectable_columns else len(selectable_columns)
            selectable_columns.insert(created_at_idx, 'created_date')
        selected_columns = st.multiselect("Display columns", options=selectable_columns, default=selectable_columns)
        query = "SELECT " + ', '.join(column_names) + " FROM job_description WHERE 1=1"
        params = []
        for column in filter_columns:
            filter_input = st.text_input(f"{column}", key=column)
            if filter_input:
                query += f" AND {column} LIKE ?"
                params.append(f"%{filter_input}%")
    
    cursor.execute(query, params)
    data = cursor.fetchall()
    connection.close()

    if data:
        df = pd.DataFrame(data, columns=column_names)
        
        # Add created_date column from created_at (extract date part only)
        # created_date is a computed column, not in database - users can select it separately from created_at
        if 'created_at' in df.columns and 'created_date' not in df.columns:
            # Extract date part from datetime string (format: YYYY-MM-DD HH:MM:SS -> YYYY-MM-DD)
            created_date_values = df['created_at'].apply(lambda x: str(x).split(' ')[0] if x and pd.notna(x) and str(x).strip() else '')
            # Insert created_date right after created_at
            created_at_idx = df.columns.get_loc('created_at')
            df.insert(created_at_idx + 1, 'created_date', created_date_values)
        
        display_columns = essential_columns + selected_columns
        display_columns = [col for col in display_columns if col in df.columns and col in allowed_display]
        df = df[display_columns]
        df.insert(0, "Select", False)
        edited_df = st.data_editor(
            df, 
            column_config={
                "job_title": st.column_config.TextColumn("Job Title", help="Job position"),
                "job_company": st.column_config.TextColumn("Company", help="Company name"),
                "Select": st.column_config.CheckboxColumn("Select")
            },
            hide_index=True
        )
        selected_files = [f"{row['id']}: {row['job_company']}: {row['job_title']}" for _, row in edited_df.iterrows() if row["Select"]]
        st.write("Selected Jobs:", selected_files)
        if "confirm_delete" not in st.session_state:
            st.session_state.confirm_delete = False
        if "jobs_to_delete" not in st.session_state:
            st.session_state.jobs_to_delete = []
        if st.button("Delete Selected"):
            if selected_files:
                st.session_state.confirm_delete = True
                st.session_state.jobs_to_delete = selected_files
                st.rerun()
        if st.session_state.confirm_delete:
            st.warning("Are you sure you want to delete the selected job descriptions?")
            if st.button("Confirm Delete"):
                connection = open_db(db_path)
                cursor = connection.cursor()
                for job in st.session_state.jobs_to_delete:
                    id_str, company, title = job.split(": ", 2)
                    id = int(id_str)
                    cursor.execute("DELETE FROM job_description WHERE id = ?", (id, ))
                    deleteJDById(id)
                connection.commit()
                connection.close()
                st.success("Selected job descriptions deleted successfully!")
                st.session_state.confirm_delete = False
                st.session_state.jobs_to_delete = []
                st.rerun()

        st.markdown("---")
        if st.button("🗑️ Delete All Job Descriptions", type="secondary"):
            st.session_state.confirm_delete_all_jobs = True
            st.rerun()
        if "confirm_delete_all_jobs" not in st.session_state:
            st.session_state.confirm_delete_all_jobs = False
        if st.session_state.confirm_delete_all_jobs:
            st.warning("⚠️ Delete ALL job descriptions? This will clear the JD table and Milvus, and clear matching results. Cannot undo.")
            col_ok, col_no = st.columns(2)
            with col_ok:
                if st.button("✅ Confirm Delete All", type="primary"):
                    try:
                        connection = open_db(db_path)
                        cursor = connection.cursor()
                        cursor.execute("DELETE FROM job_description")
                        connection.commit()
                        connection.close()
                        from matching_utils import connect_milvus
                        from pymilvus import utility
                        connect_milvus()
                        if utility.has_collection("job_postings"):
                            utility.drop_collection("job_postings")
                        csv_path = os.path.abspath(os.path.join(script_dir, "..", "..", "..", "search_results.csv"))
                        if os.path.exists(csv_path):
                            headers = ["Index", "name", "job_id", "job_company", "job_title", "job_application_url", "distance", "create_date"]
                            pd.DataFrame(columns=headers).to_csv(csv_path, index=False)
                        st.success("All job descriptions and related matching results cleared.")
                        st.session_state.confirm_delete_all_jobs = False
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with col_no:
                if st.button("❌ Cancel"):
                    st.session_state.confirm_delete_all_jobs = False
                    st.rerun()

if __name__ == "__main__":
    main()
