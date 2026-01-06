# SeeU-project-Team3

## 📌 Platform-Specific Instructions

- **Windows Users**: Use `.bat` files in the root directory (see below)
- **Mac Users**: See [`Mac/README_MAC.md`](Mac/README_MAC.md) and use `.sh` scripts in the `Mac/` directory
- **Linux Users**: Use the Mac scripts (they work on Linux too!)

---

## Windows Setup

1. Replace the OpenAI API key in `gpt_key.txt` with your own key. Alternatively, use Qwen model from Ali, and replace the Ali API key in `ds_key.txt` with your own key.

2. Make sure you have Docker installed and running on your machine

3. To run the code, do the following:
    run install_dependencies to install all library dependencies
        - (You only need to do this when you first start the application)
    run launch_app.bat to automatically start the application. It will:
        - start a local milvus db.
        - start the database for the project
        - automatically open the matching platform on your browser where you can upload
            - resume (pdf & word)
            - job description (excel)

    use stop_milvus.bat to stop the milvus database

4. Running the code with manual commands:
    - run database.py with command "python InfoMatching_Team4/database.py" --> generate my_database.db file
    - run db_Parsed.py with command "python InfoMatching_Team4/db_Parsed.py" --> generate my_database_parsed.db file
    - make sure your environment have streamlit installed
    - run "python -m http.server --directory uploads 8000" --> put the uploads directory to serve, to make sure the downloading link work
    - run the web app with command "streamlit run InfoMatching_Team4/my_app/app.py"
        Within the app, you can:
        - upload resume (pdf)
        - upload job description (excel)

