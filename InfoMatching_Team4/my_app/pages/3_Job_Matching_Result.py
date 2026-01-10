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

LLM_COL = "LLM Fit (Strict)"
SCORE_COL = "LLM Score"


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
    # ONLY use the parsed resume experience field (plural!)
    # resume_interface.py outputs "experiences"
    cur.execute("SELECT experiences FROM uploads WHERE id = ?", (resume_id,))
    r = cur.fetchone()
    if not r or r[0] is None:
        return ""

    s = str(r[0]).strip()
    if not s or s.lower() == "nan":
        return ""

    return s


def get_jd_text(cur, job_id: int) -> str:
    cur.execute("SELECT job_description FROM job_description WHERE id = ?", (job_id,))
    r = cur.fetchone()
    return str(r[0]) if r and r[0] else ""


def apply_high_cap(df_in: pd.DataFrame) -> pd.DataFrame:
    if "name" not in df_in.columns or SCORE_COL not in df_in.columns:
        return df_in

    def _band(score: float) -> str:
        if score >= 85:
            return "High"
        if score >= 60:
            return "Medium"
        return "Low"

    def _cap_group(g: pd.DataFrame) -> pd.DataFrame:
        gg = g.copy()
        gg[SCORE_COL] = pd.to_numeric(gg[SCORE_COL], errors="coerce").fillna(0.0)

        # 1) label by score thresholds
        gg[LLM_COL] = gg[SCORE_COL].apply(lambda x: _band(float(x)))

        # 2) cap High to <= 5% by keeping only top-k High scores
        gg_sorted = gg.sort_values(SCORE_COL, ascending=False)
        n = len(gg_sorted)
        k = int(n * 0.05)  # allow 0

        if k <= 0:
            gg[LLM_COL] = gg[LLM_COL].replace({"High": "Medium"})
            return gg

        high_idx = gg_sorted.index[gg_sorted[LLM_COL] == "High"].tolist()
        # keep first k highs, downgrade the rest
        for idx in high_idx[k:]:
            gg.at[idx, LLM_COL] = "Medium"

        return gg

    return df_in.groupby("name", group_keys=False).apply(_cap_group)


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

    st.caption(
        "Optional: Use LLM to rate match quality (High/Medium/Low) STRICTLY based on resume EXPERIENCE (internships + projects) vs JD text. "
        "Final High will be capped to <= 5% per student."
    )
    run_rating = st.button("Compute LLM Fit (Strict) for ALL matches")

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
                rating_raw_list, scores = [], []

                for _, row in df_top.iterrows():
                    sname = str(row["name"]).strip()
                    try:
                        jid = int(row["job_id"])
                    except Exception:
                        rating_raw_list.append("Medium")
                        scores.append(0)
                        continue

                    resume_id = get_latest_resume_id_by_name(cur, sname)
                    if resume_id is None:
                        rating_raw_list.append("Medium")
                        scores.append(0)
                        continue

                    resume_text = build_resume_text_from_uploads(cur, resume_id)
                    jd_text = get_jd_text(cur, jid)

                    if not resume_text or not jd_text:
                        rating_raw_list.append("Medium")
                        scores.append(0)
                        continue

                    out = rate_fit(resume_text, jd_text, cache=st.session_state["llm_cache"])
                    rating_raw_list.append(out.get("rating_raw", "Medium"))
                    scores.append(out.get("score", 0))

                conn.close()

                for col in [LLM_COL, SCORE_COL, "LLM Rating Raw"]:
                    if col not in df.columns:
                        df[col] = ""

                df.loc[df_top.index, "LLM Rating Raw"] = rating_raw_list
                df.loc[df_top.index, SCORE_COL] = scores

                # Apply strict cap so final LLM_COL satisfies High <= 5%
                df = apply_high_cap(df)

    st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
