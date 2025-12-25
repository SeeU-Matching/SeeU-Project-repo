# pages/3_Job_Matching_Result.py

import streamlit as st
import os
import pandas as pd

def main():
    st.markdown("<h1 style='font-size:24px;'>Job Matching Result</h1>", unsafe_allow_html=True)

    # Add a text input for the student name
    student_name = st.text_input("Enter Student Name to Filter Results")

    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../search_results.csv'))
    if not os.path.exists(csv_path):
        st.write("No matching results found. (milvus_matching_results.csv does not exist)")
        return

    df = pd.read_csv(csv_path)
    if student_name:
        filtered_df = df[df['name'].str.contains(student_name, case=False, na=False)]
    else:
        filtered_df = df

    if not filtered_df.empty:
        st.dataframe(filtered_df)
    else:
        st.write("No matching results found.")

if __name__ == "__main__":
    main()
