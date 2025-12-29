import streamlit as st
import sqlite3
import os
import pandas as pd
import sys
import re

# Append the path to the parent directory of InfoMatching_Team3
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../InfoMatching_Team3')))
from resume_interface import read_resume
# Import Milvus embedding/insert function
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../InfoMatching_Team1')))
from matching_utils import insert_resumes

def sanitize_column_name(name):
    return re.sub(r'\W|^(?=\d)', '_', name).lower()

def main():
    st.markdown("<h1 style='font-size:24px;'>Resume</h1>", unsafe_allow_html=True)

    with st.sidebar:
        st.header("Upload Resumes")
        uploaded_resumes = st.file_uploader("Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "..", "..", "..", "my_database.db")
    uploads_dir = os.path.join(script_dir, "..", "..", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    
    print("Using database at:", os.path.abspath(db_path))

    if uploaded_resumes:
        for uploaded_resume in uploaded_resumes:
            file_path = os.path.join(uploads_dir, uploaded_resume.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_resume.getbuffer())

    # Fetch existing columns in the database
    cursor.execute("PRAGMA table_info(uploads)")
    column_names = [info[1] for info in cursor.fetchall()]

    if uploaded_resumes:
        resumes_to_insert = []
        for uploaded_resume in uploaded_resumes:
            extracted_data = read_resume(file_object=uploaded_resume)
            data = {
                'file_name': uploaded_resume.name,
                'file_path': os.path.join("uploads", uploaded_resume.name),
                **{sanitize_column_name(k): (', '.join(map(str, v)) if isinstance(v, list) else v) for k, v in extracted_data.items()}
            }
            
            # Ensure all necessary columns exist in the database
            cursor.execute("PRAGMA table_info(uploads)")
            existing_columns = {info[1].lower() for info in cursor.fetchall()}
            new_columns = {sanitize_column_name(col) for col in data.keys()} - existing_columns
            
            for column in new_columns:
                cursor.execute(f"ALTER TABLE uploads ADD COLUMN {column} TEXT")
                column_names.append(column)
            
            cursor.execute("SELECT COUNT(*) FROM uploads WHERE file_name = ?", (uploaded_resume.name,))
            count = cursor.fetchone()[0]
            if count == 0:
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['?'] * len(data))
                cursor.execute(f'INSERT INTO uploads ({columns}) VALUES ({placeholders})', list(data.values()))
                # get sql id
                new_id = cursor.lastrowid
                # add sql id to resume
                extracted_data['id'] = new_id
                # Add to resumes_to_insert for embedding
                resumes_to_insert.append(extracted_data)
            else:
                update_columns = ', '.join([f"{key} = ?" for key in data.keys()])
                cursor.execute(f'UPDATE uploads SET {update_columns} WHERE file_name = ?', list(data.values()) + [uploaded_resume.name])
                # For update, also embed/insert (Milvus will deduplicate by content)
                cursor.execute("SELECT id FROM uploads WHERE file_name = ?", (uploaded_resume.name,))
                existing_id = cursor.fetchone()[0]
                extracted_data['id'] = existing_id
                resumes_to_insert.append(extracted_data)
                
        connection.commit()
        # Insert new/updated resumes into Milvus
        if resumes_to_insert:
            # Drop and recreate only the resume collection to avoid duplicates
            from pymilvus import utility
            from matching_utils import connect_milvus, insert_resumes, match_resumes_to_jobs
            connect_milvus()
            if utility.has_collection("resume"):
                utility.drop_collection("resume")
            # Re-insert all resumes from SQL
            insert_resumes(resumes_to_insert, model_name="bge-m3")
            # Only call matching if both collections exist and are non-empty
            if utility.has_collection("resume") and utility.has_collection("job_postings"):
                from pymilvus import Collection
                resume_col = Collection("resume")
                job_col = Collection("job_postings")
                resume_col.load()
                job_col.load()
                if resume_col.num_entities > 0 and job_col.num_entities > 0:
                    from matching_utils import match_new_resumes_to_jobs
                    match_new_resumes_to_jobs(resumes_to_insert, model_name="bge-m3")
        st.success("Resumes uploaded and embedded successfully!")
    
    with st.sidebar:
        st.header("Filters")
        essential_columns = ['url','file_name']
        filter_columns = [col for col in column_names if col not in ['file_path']]
        selectable_columns = [col for col in filter_columns if col not in essential_columns]
        selected_columns = st.multiselect("Display columns", options=selectable_columns, default=selectable_columns if selectable_columns else [])
        query = "SELECT " + ', '.join(column_names) + " FROM uploads WHERE 1=1"
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
        server_url = "http://localhost:8000"
        df['url'] = df['file_name'].apply(lambda file: f'{server_url}/{file}')
        display_columns = essential_columns + selected_columns  # Ensure essential columns are always included
        df = df[display_columns]
        df.insert(0, "Select", False)
        edited_df = st.data_editor(
            df, 
            column_config={
                "url": st.column_config.LinkColumn("Download Link", help="Click to open the file"),
                "file_name": st.column_config.TextColumn("File Name", help="Uploaded file"),
                "Select": st.column_config.CheckboxColumn("Select")
            },
            hide_index=True
        )
        selected_files = edited_df[edited_df["Select"] == True]["file_name"].tolist()
        st.write("Selected Files:", selected_files)
        if "confirm_delete" not in st.session_state:
            st.session_state.confirm_delete = False
        if "files_to_delete" not in st.session_state:
            st.session_state.files_to_delete = []
        if st.button("Delete Selected"):
            if selected_files:
                st.session_state.confirm_delete = True
                st.session_state.files_to_delete = selected_files
                st.rerun()
        if st.session_state.confirm_delete:
            st.warning("Are you sure you want to delete the selected files?")
            if st.button("Confirm Delete"):
                connection = sqlite3.connect(db_path)
                cursor = connection.cursor()
                for file_name in st.session_state.files_to_delete:
                    cursor.execute("DELETE FROM uploads WHERE file_name = ?", (file_name,))
                connection.commit()
                connection.close()
                st.success("Selected files deleted successfully!")
                st.session_state.confirm_delete = False
                st.session_state.files_to_delete = []
                st.rerun()

if __name__ == "__main__":
    main()
