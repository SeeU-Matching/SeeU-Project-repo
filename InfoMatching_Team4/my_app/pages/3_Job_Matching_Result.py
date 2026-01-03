# pages/3_Job_Matching_Result.py

import sys
import os

# Ensure project root is on sys.path so `from InfoMatching_Team4...` works in Streamlit
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st
import pandas as pd
import sqlite3

from InfoMatching_Team4.llm_fit import rate_fit

LLM_COL = "LLM Fit (ChatGPT)"


def get_latest_resume_id_by_name(cur, student_name: str):
    cur.execute(
        """
        SELECT id FROM uploads
        WHERE name = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (student_name,),
    )
    r = cur.fetchone()
    return int(r[0]) if r else None


def build_resume_text_from_uploads(cur, resume_id: int) -> str:
    # Get all columns in uploads table
    cur.execute("PRAGMA table_info(uploads)")
    cols = [r[1] for r in cur.fetchall()]

    cur.execute(f"SELECT {', '.join(cols)} FROM uploads WHERE id = ?", (resume_id,))
    row = cur.fetchone()
    if not row:
        return ""

    d = dict(zip(cols, row))

    # Prefer common fields if present; otherwise concatenate all non-empty text fields
    preferred = [
        "major",
        "degree",
        "gpa",
        "business_domain",
        "education",
        "skills",
        "experience",
        "projects",
        "summary",
    ]
    keys = [k for k in preferred if k in d]

    if not keys:
        skip = {"id", "file_path", "uploaded_at", "created_at"}
        keys = [k for k in cols if k not in skip]

    parts = []
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() != "nan":
            parts.append(f"{k}: {s}")
    return "\n".join(parts)


def get_jd_text(cur, job_id: int) -> str:
    cur.execute("SELECT job_description FROM job_description WHERE id = ?", (job_id,))
    r = cur.fetchone()
    return str(r[0]) if r and r[0] else ""


def main():
    st.markdown("<h1 style='font-size:24px;'>Job Matching Result</h1>", unsafe_allow_html=True)

    student_name = st.text_input("Enter Student Name to Filter Results")

    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../search_results.csv"))
    if not os.path.exists(csv_path):
        st.write("No matching results found. (search_results.csv does not exist)")
        return

    df = pd.read_csv(csv_path)
    df = df.drop_duplicates(subset=["name", "job_id", "job_application_url"], keep="last").reset_index(drop=True)

    if student_name and "name" in df.columns:
        df = df[df["name"].astype(str).str.contains(student_name, case=False, na=False)]

    if df.empty:
        st.write("No matching results found.")
        return

    # LLM rating controls
    st.caption("Optional: Use ChatGPT (OpenAI API) to rate match quality (High/Medium/Low) based on resume experience vs JD text.")
    run_rating = st.button("Compute LLM Fit (ChatGPT) for ALL matches")

    if "llm_cache" not in st.session_state:
        st.session_state["llm_cache"] = {}

    if run_rating:
        if "name" not in df.columns or "job_id" not in df.columns:
            st.error(f"search_results.csv must contain 'name' and 'job_id'. Found: {list(df.columns)}")
        else:
            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../my_database.db"))
            if not os.path.exists(db_path):
                st.error("my_database.db not found in project root.")
            else:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()

                df_top = df.copy()
                ratings, confs = [], []

                for _, row in df_top.iterrows():
                    sname = str(row["name"]).strip()
                    try:
                        jid = int(row["job_id"])
                    except Exception:
                        ratings.append("Medium")
                        confs.append(0.0)
                        continue

                    resume_id = get_latest_resume_id_by_name(cur, sname)
                    if resume_id is None:
                        ratings.append("Medium")
                        confs.append(0.0)
                        continue

                    resume_text = build_resume_text_from_uploads(cur, resume_id)
                    jd_text = get_jd_text(cur, jid)

                    if not resume_text or not jd_text:
                        ratings.append("Medium")
                        confs.append(0.0)
                        continue

                    out = rate_fit(resume_text, jd_text, cache=st.session_state["llm_cache"])
                    ratings.append(out["rating"])
                    try:
                        confs.append(round(float(out["confidence"]), 3))  # <-- 3 decimal
                    except Exception:
                        confs.append(0.000)

                conn.close()

                for col in [LLM_COL, "LLM Confidence"]:
                    if col not in df.columns:
                        df[col] = ""

                df.loc[df_top.index, LLM_COL] = ratings
                df.loc[df_top.index, "LLM Confidence"] = confs

    st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
