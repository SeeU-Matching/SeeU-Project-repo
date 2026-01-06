@echo off
echo ========================================
echo Sync SQLite to Milvus Tool
echo ========================================
echo.
echo This script will:
echo 1. Read all resumes and job descriptions from SQLite
echo 2. Insert them into Milvus with embeddings
echo 3. Run matching to generate search_results.csv
echo.
pause

venv\Scripts\python.exe sync_to_milvus.py

echo.
pause

