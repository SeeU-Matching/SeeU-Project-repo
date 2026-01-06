@echo off
echo Starting Streamlit application...
echo.
cd /d "%~dp0"
venv\Scripts\python.exe -m streamlit run InfoMatching_Team4\my_app\app.py --server.port 8501
pause

