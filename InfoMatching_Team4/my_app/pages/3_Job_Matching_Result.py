# pages/3_Job_Matching_Result.py

import streamlit as st
import os
import pandas as pd

from InfoMatching_Team4.qwen_evaluator import rate_match
import sqlite3



def _load_resume_job_texts():
    """
    Build lookup dicts from SQLite so we can feed Qwen:
    - resume_text: combine main resume fields saved in uploads table
    - job_text: combine main job fields saved in job_description table
    """
    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "my_database.db")
    db_path = os.path.abspath(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # uploads table
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='uploads'")
    has_uploads = cur.fetchone() is not None

    resumes = {}
    if has_uploads:
        df_u = pd.read_sql_query("SELECT * FROM uploads", conn)
        # Try to build a compact text block
        for _, r in df_u.iterrows():
            # file_name is usually stable; fallback to name
            rid = str(r.get("file_name") or r.get("name") or "")
            if not rid:
                continue
            parts = []
            for k in ["name", "major", "tech_skills", "experiences", "email", "phone"]:
                v = r.get(k, "")
                if pd.notna(v) and str(v).strip():
                    parts.append(f"{k}: {v}")
            resumes[rid] = "\n".join(parts)

    # job_description table
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='job_description'")
    has_jobs = cur.fetchone() is not None

    jobs = {}
    if has_jobs:
        df_j = pd.read_sql_query("SELECT * FROM job_description", conn)
        for _, j in df_j.iterrows():
            # create stable id for lookup
            jid = str(j.get("job_application_url") or f"{j.get('job_company','')}-{j.get('job_title','')}")
            if not jid:
                continue
            parts = []
            for k in ["job_company", "job_title", "job_description", "job_application_url"]:
                v = j.get(k, "")
                if pd.notna(v) and str(v).strip():
                    parts.append(f"{k}: {v}")
            jobs[jid] = "\n".join(parts)

    conn.close()
    return resumes, jobs

def main():
    st.title("Job Matching Results")

    csv_path = "search_results.csv"
    if not os.path.exists(csv_path):
        st.error("No search_results.csv found. Please run matching first.")
        return

    df = pd.read_csv(csv_path)

    # Ensure evaluation columns exist
    if "match_level" not in df.columns:
        df["match_level"] = ""
    if "match_confidence" not in df.columns:
        df["match_confidence"] = ""
    if "match_reasons" not in df.columns:
        df["match_reasons"] = ""
    if "match_key_gaps" not in df.columns:
        df["match_key_gaps"] = ""

    st.dataframe(df)

    st.divider()
    st.subheader("Evaluate match quality with Qwen (LOW / MEDIUM / HIGH)")

    top_k = st.number_input("Evaluate top-K per resume", min_value=1, max_value=50, value=5, step=1)
    only_missing = st.checkbox("Only evaluate rows with empty match_level", value=True)

    if st.button("Run Qwen evaluation"):
        resumes_map, jobs_map = _load_resume_job_texts()

        # Try to detect column names in search_results.csv
        # (Your CSV likely has resume/job identifiers; we handle common names.)
        resume_cols = [c for c in df.columns if c.lower() in {"resume", "resume_name", "candidate", "file_name", "resume_file"}]
        job_cols = [c for c in df.columns if c.lower() in {"job", "job_title", "job_id", "job_application_url", "url"}]
        score_cols = [c for c in df.columns if "score" in c.lower() or "distance" in c.lower()]

        resume_col = resume_cols[0] if resume_cols else None
        job_col = job_cols[0] if job_cols else None
        score_col = score_cols[0] if score_cols else None

        if not resume_col or not job_col:
            st.error(
                "Cannot auto-detect resume/job columns in search_results.csv. "
                "Please ensure it contains resume identifier and job identifier columns."
            )
            return

        # Evaluate top-K per resume by best score if score exists; else first K
        updated = 0
        for resume_id, group in df.groupby(resume_col, dropna=False):
            grp = group.copy()
            if score_col:
                # higher-is-better or lower-is-better unknown; assume higher better if 'score', lower better if 'distance'
                lower_is_better = "distance" in score_col.lower()
                grp = grp.sort_values(score_col, ascending=lower_is_better)
            grp = grp.head(int(top_k))

            for idx in grp.index:
                if only_missing and str(df.at[idx, "match_level"]).strip():
                    continue

                job_id = df.at[idx, job_col]

                # Build resume/job text for evaluator
                rtxt = resumes_map.get(str(resume_id), str(resume_id))
                jtxt = jobs_map.get(str(job_id), str(job_id))

                try:
                    out = rate_match(rtxt, jtxt)
                except Exception as e:
                    st.warning(f"Qwen evaluation failed at row {idx}: {e}")
                    continue

                df.at[idx, "match_level"] = out.get("rating", "")
                df.at[idx, "match_confidence"] = out.get("confidence", "")
                df.at[idx, "match_reasons"] = " | ".join(out.get("reasons", [])[:5])
                df.at[idx, "match_key_gaps"] = " | ".join(out.get("key_gaps", [])[:5])
                updated += 1

        df.to_csv(csv_path, index=False)
        st.success(f"Evaluation complete. Updated {updated} rows and saved back to {csv_path}.")
        st.dataframe(df)



if __name__ == "__main__":
    main()
