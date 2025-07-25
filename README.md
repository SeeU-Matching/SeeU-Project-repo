# SeeU-project-Team3

1. Replace the OpenAI API key in `gpt_key.txt` with your own key. Alternatively, use Qwen model from Ali, and replace the Ali API key in `ds_key.txt` with your own key.
2. You will need a locally deployed Milvus database to be able to run the code
3. To run the code, do the following:
    - run database.py with command "python InfoMatching_Team4/database.py" --> generate my_database.db file
    - run db_Parsed.py with command "python InfoMatching_Team4/db_Parsed.py" --> generate my_database_parsed.db file
    - make sure your environment have streamlit installed
    - run "python -m http.server --directory uploads 8000" --> put the uploads directory to serve, to make sure the downloading link work
    - run the web app with command "streamlit run InfoMatching_Team4/my_app/app.py"
        Within the app, you can:
        - upload resume (pdf)
        - upload job description (excel)

