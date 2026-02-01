# pages/3_Job_Matching_Result.py

import streamlit as st
import os
import pandas as pd
import sqlite3
import sys

# Import delete functions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../InfoMatching_Team1')))
from matching_utils import deleteResumeById, deleteJDById

def main():
    st.markdown("<h1 style='font-size:24px;'>Job Matching Result</h1>", unsafe_allow_html=True)

    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../search_results.csv'))
    if not os.path.exists(csv_path):
        st.warning("No matching results found. (search_results.csv does not exist)")
        st.info("💡 **Tips:**")
        st.write("1. Make sure you have uploaded both resumes and job descriptions")
        st.write("2. The matching process should run automatically after upload")
        st.write("3. Check the console/terminal for any error messages")
        
        # Add diagnostic button
        if st.button("🔍 Check Milvus Status"):
            try:
                import sys
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../InfoMatching_Team1')))
                from matching_utils import connect_milvus
                from pymilvus import utility, Collection
                
                connect_milvus()
                
                has_resume = utility.has_collection("resume")
                has_job = utility.has_collection("job_postings")
                
                st.write("**Milvus Collections Status:**")
                if has_resume:
                    resume_col = Collection("resume")
                    resume_col.load()
                    num_resumes = resume_col.num_entities
                    st.success(f"✓ Resume collection exists with {num_resumes} entries")
                else:
                    st.error("✗ Resume collection does NOT exist")
                
                if has_job:
                    job_col = Collection("job_postings")
                    job_col.load()
                    num_jobs = job_col.num_entities
                    st.success(f"✓ Job postings collection exists with {num_jobs} entries")
                else:
                    st.error("✗ Job postings collection does NOT exist")
                
                if has_resume and has_job:
                    resume_col = Collection("resume")
                    job_col = Collection("job_postings")
                    resume_col.load()
                    job_col.load()
                    if resume_col.num_entities > 0 and job_col.num_entities > 0:
                        st.info("Both collections have data. Try uploading a resume or job description again to trigger matching.")
                    else:
                        st.warning("One or both collections are empty. Please upload data first.")
                else:
                    st.warning("Please upload resumes and job descriptions first.")
                    
            except Exception as e:
                st.error(f"Error checking Milvus: {e}")
                st.write("Make sure Milvus is running (check Docker containers)")
        
        return

    df = pd.read_csv(csv_path)
    
    # Handle missing create_date column for old CSV files
    if 'create_date' not in df.columns:
        # Add create_date column with empty values for old records
        df['create_date'] = ''

    # Normalize types for filtering
    if 'distance' in df.columns:
        df['distance'] = pd.to_numeric(df['distance'], errors='coerce')
    else:
        df['distance'] = pd.Series(dtype='float64')

    df['_create_dt'] = pd.to_datetime(df.get('create_date', ''), errors='coerce')

    # ----------------------------
    # Filters
    # ----------------------------
    with st.expander("Filters", expanded=True):
        c1, c2, c3 = st.columns(3)
        name_query = c1.text_input("Student name contains", value="", placeholder="e.g. yudong / fang")
        company_query = c2.text_input("Company contains", value="", placeholder="e.g. ripple / google")
        title_query = c3.text_input("Job title contains", value="", placeholder="e.g. data")

        dist_series = df['distance'].dropna()
        if len(dist_series) > 0:
            dist_min = float(dist_series.min())
            dist_max = float(dist_series.max())
            if dist_min == dist_max:
                st.caption(f"All distances are the same: {dist_min:.4f}")
                dist_low, dist_high = dist_min, dist_max
            else:
                step = max((dist_max - dist_min) / 200.0, 0.0001)
                dist_low, dist_high = st.slider(
                    "Distance range",
                    min_value=dist_min,
                    max_value=dist_max,
                    value=(dist_min, dist_max),
                    step=step,
                )
        else:
            st.caption("No valid distance values found; distance filter disabled.")
            dist_low, dist_high = None, None

        date_series = df['_create_dt'].dropna()
        date_mode = st.selectbox("Create date filter", ["Any", "Specific day", "Range"], index=0)
        selected_day = None
        selected_range = None
        if date_mode != "Any":
            if len(date_series) == 0:
                st.warning("No valid create_date values found; date filter disabled.")
                date_mode = "Any"
            else:
                min_day = date_series.min().date()
                max_day = date_series.max().date()
                if date_mode == "Specific day":
                    selected_day = st.date_input("Select a day", value=max_day)
                else:
                    selected_range = st.date_input("Select a date range", value=(min_day, max_day))

    # Apply filters
    filtered_df = df.copy()
    if name_query and 'name' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['name'].astype(str).str.contains(name_query, case=False, na=False)]
    if company_query and 'job_company' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['job_company'].astype(str).str.contains(company_query, case=False, na=False)]
    if title_query and 'job_title' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['job_title'].astype(str).str.contains(title_query, case=False, na=False)]

    if dist_low is not None and dist_high is not None:
        # Keep NaN distances even when filtering (rare, but avoids hiding rows unexpectedly)
        mask = filtered_df['distance'].isna() | filtered_df['distance'].between(dist_low, dist_high, inclusive='both')
        filtered_df = filtered_df[mask]

    if date_mode == "Specific day" and selected_day is not None:
        filtered_df = filtered_df[filtered_df['_create_dt'].notna()]
        filtered_df = filtered_df[filtered_df['_create_dt'].dt.date == selected_day]
    elif date_mode == "Range" and selected_range is not None and isinstance(selected_range, (list, tuple)) and len(selected_range) == 2:
        start_day, end_day = selected_range
        filtered_df = filtered_df[filtered_df['_create_dt'].notna()]
        filtered_df = filtered_df[
            (filtered_df['_create_dt'].dt.date >= start_day) &
            (filtered_df['_create_dt'].dt.date <= end_day)
        ]

    # Drop helper column from display (keep original create_date string)
    if '_create_dt' in filtered_df.columns:
        filtered_df = filtered_df.drop(columns=['_create_dt'])

    st.caption(f"Showing {len(filtered_df)} / {len(df)} result(s).")

    if not filtered_df.empty:
        # Add Select column for deletion
        filtered_df = filtered_df.copy()
        filtered_df.insert(0, "Select", False)
        
        # Display dataframe with selection
        edited_df = st.data_editor(
            filtered_df,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select"),
                "name": st.column_config.TextColumn("Student Name"),
                "job_id": st.column_config.NumberColumn("Job ID"),
                "job_company": st.column_config.TextColumn("Company"),
                "job_title": st.column_config.TextColumn("Job Title"),
                "job_application_url": st.column_config.LinkColumn("Application URL"),
                "distance": st.column_config.NumberColumn("Distance", format="%.4f"),
                "create_date": st.column_config.TextColumn("Create Date", help="Date when the match was created")
            },
            hide_index=True
        )
        
        # Get selected rows
        selected_rows = edited_df[edited_df["Select"] == True]
        
        if not selected_rows.empty:
            st.write(f"**Selected {len(selected_rows)} row(s) for deletion**")
        
        # Delete options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🗑️ Delete Selected Results", type="primary"):
                if not selected_rows.empty:
                    st.session_state.confirm_delete_results = True
                    st.session_state.rows_to_delete = selected_rows.to_dict('records')
                    st.rerun()
                else:
                    st.warning("Please select at least one row to delete.")
        
        with col2:
            if st.button("🗑️ Delete Selected Resumes"):
                if not selected_rows.empty:
                    st.session_state.confirm_delete_resumes = True
                    st.session_state.rows_to_delete = selected_rows.to_dict('records')
                    st.rerun()
                else:
                    st.warning("Please select at least one row to delete.")
        
        with col3:
            if st.button("🗑️ Delete Selected Jobs"):
                if not selected_rows.empty:
                    st.session_state.confirm_delete_jobs = True
                    st.session_state.rows_to_delete = selected_rows.to_dict('records')
                    st.rerun()
                else:
                    st.warning("Please select at least one row to delete.")
        
        # Initialize session state
        if "confirm_delete_results" not in st.session_state:
            st.session_state.confirm_delete_results = False
        if "confirm_delete_resumes" not in st.session_state:
            st.session_state.confirm_delete_resumes = False
        if "confirm_delete_jobs" not in st.session_state:
            st.session_state.confirm_delete_jobs = False
        
        # Confirm delete matching results only (from CSV)
        if st.session_state.confirm_delete_results:
            st.warning("⚠️ Are you sure you want to delete the selected matching results? This will only remove them from the results list, not delete the actual resumes or jobs.")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ Confirm Delete Results", type="primary"):
                    try:
                        # Read current CSV
                        current_df = pd.read_csv(csv_path)
                        
                        # Get indices to delete
                        rows_to_delete = st.session_state.rows_to_delete
                        indices_to_delete = [row.get('Index') for row in rows_to_delete]
                        
                        # Remove selected rows
                        current_df = current_df[~current_df['Index'].isin(indices_to_delete)]
                        
                        # Re-index
                        current_df['Index'] = range(1, len(current_df) + 1)
                        
                        # Save back to CSV
                        current_df.to_csv(csv_path, index=False)
                        
                        st.success(f"✅ Successfully deleted {len(rows_to_delete)} matching result(s)!")
                        st.session_state.confirm_delete_results = False
                        st.session_state.rows_to_delete = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting results: {e}")
                        import traceback
                        st.code(traceback.format_exc())
            
            with col_cancel:
                if st.button("❌ Cancel"):
                    st.session_state.confirm_delete_results = False
                    st.session_state.rows_to_delete = []
                    st.rerun()
        
        # Confirm delete resumes (from SQLite, Milvus, and CSV)
        if st.session_state.confirm_delete_resumes:
            st.warning("⚠️ Are you sure you want to delete the selected RESUMES? This will permanently delete them from the database and all related matching results.")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ Confirm Delete Resumes", type="primary"):
                    try:
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        db_path = os.path.join(script_dir, "..", "..", "..", "my_database.db")
                        connection = sqlite3.connect(db_path)
                        cursor = connection.cursor()
                        
                        rows_to_delete = st.session_state.rows_to_delete
                        deleted_count = 0
                        
                        for row in rows_to_delete:
                            name = row.get('name')
                            if name:
                                # Get resume id from SQLite by name
                                cursor.execute("SELECT id FROM uploads WHERE name = ?", (name,))
                                result = cursor.fetchone()
                                if result:
                                    resume_id = result[0]
                                    # Delete from SQLite
                                    cursor.execute("DELETE FROM uploads WHERE id = ?", (resume_id,))
                                    # Delete from Milvus
                                    deleteResumeById(resume_id)
                                    deleted_count += 1
                        
                        connection.commit()
                        connection.close()
                        
                        # Also delete from CSV - delete ALL matching results for these resumes
                        current_df = pd.read_csv(csv_path)
                        names_to_delete = [row.get('name') for row in rows_to_delete if row.get('name')]
                        if names_to_delete:
                            current_df = current_df[~current_df['name'].isin(names_to_delete)]
                            current_df['Index'] = range(1, len(current_df) + 1)
                            current_df.to_csv(csv_path, index=False)
                        
                        st.success(f"✅ Successfully deleted {deleted_count} resume(s) and related matching results!")
                        st.session_state.confirm_delete_resumes = False
                        st.session_state.rows_to_delete = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting resumes: {e}")
                        import traceback
                        st.code(traceback.format_exc())
            
            with col_cancel:
                if st.button("❌ Cancel"):
                    st.session_state.confirm_delete_resumes = False
                    st.session_state.rows_to_delete = []
                    st.rerun()
        
        # Confirm delete jobs (from SQLite, Milvus, and CSV)
        if st.session_state.confirm_delete_jobs:
            st.warning("⚠️ Are you sure you want to delete the selected JOBS? This will permanently delete them from the database and all related matching results.")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ Confirm Delete Jobs", type="primary"):
                    try:
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        db_path = os.path.join(script_dir, "..", "..", "..", "my_database.db")
                        connection = sqlite3.connect(db_path)
                        cursor = connection.cursor()
                        
                        rows_to_delete = st.session_state.rows_to_delete
                        deleted_count = 0
                        
                        for row in rows_to_delete:
                            job_id = row.get('job_id')
                            if job_id:
                                # Delete from SQLite
                                cursor.execute("DELETE FROM job_description WHERE id = ?", (job_id,))
                                # Delete from Milvus
                                deleteJDById(job_id)
                                deleted_count += 1
                        
                        connection.commit()
                        connection.close()
                        
                        # Also delete from CSV - delete ALL matching results for these jobs
                        current_df = pd.read_csv(csv_path)
                        job_ids_to_delete = [row.get('job_id') for row in rows_to_delete if row.get('job_id')]
                        if job_ids_to_delete:
                            current_df = current_df[~current_df['job_id'].isin(job_ids_to_delete)]
                            current_df['Index'] = range(1, len(current_df) + 1)
                            current_df.to_csv(csv_path, index=False)
                        
                        st.success(f"✅ Successfully deleted {deleted_count} job(s) and related matching results!")
                        st.session_state.confirm_delete_jobs = False
                        st.session_state.rows_to_delete = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting jobs: {e}")
                        import traceback
                        st.code(traceback.format_exc())
            
            with col_cancel:
                if st.button("❌ Cancel"):
                    st.session_state.confirm_delete_jobs = False
                    st.session_state.rows_to_delete = []
                    st.rerun()
        
        # Add "Delete All" button
        st.markdown("---")
        if st.button("🗑️ Delete All Results", type="secondary"):
            st.session_state.confirm_delete_all = True
            st.rerun()
        
        if "confirm_delete_all" not in st.session_state:
            st.session_state.confirm_delete_all = False
        
        if st.session_state.confirm_delete_all:
            st.warning("⚠️ Are you sure you want to delete ALL matching results? This will clear the entire results file.")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ Confirm Delete All", type="primary"):
                    try:
                        # Create empty CSV with headers
                        headers = ["Index", "name", "job_id", "job_company", "job_title", "job_application_url", "distance", "create_date"]
                        empty_df = pd.DataFrame(columns=headers)
                        empty_df.to_csv(csv_path, index=False)
                        
                        st.success("✅ All matching results deleted!")
                        st.session_state.confirm_delete_all = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting all results: {e}")
            
            with col_cancel:
                if st.button("❌ Cancel"):
                    st.session_state.confirm_delete_all = False
                    st.rerun()
    else:
        st.write("No matching results found.")

if __name__ == "__main__":
    main()
