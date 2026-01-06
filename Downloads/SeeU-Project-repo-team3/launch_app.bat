@echo off
echo ========================================
echo SeeU Project - Job Matching App Launcher
echo ========================================
echo.

REM Set Python path to use virtual environment
set PYTHON_PATH=venv\Scripts\python.exe

REM Check if virtual environment exists
if not exist "%PYTHON_PATH%" (
    echo Error: Virtual environment not found!
    echo Please make sure you have created the virtual environment first.
    echo Run: python -m venv venv
    pause
    exit /b 1
)

echo Step 1: Starting Milvus vector database...
cd milvus_setup
docker-compose up -d
if %errorlevel% neq 0 (
    echo Warning: Failed to start Milvus. Make sure Docker is installed and running.
    echo You can install Docker Desktop from: https://www.docker.com/products/docker-desktop
    cd ..
    pause
    exit /b 1
)
cd ..
echo Milvus started successfully!
echo Waiting for Milvus to initialize (15 seconds)...
echo This may take longer on first run as Docker images are downloaded...
timeout /t 15 /nobreak >nul
echo.

echo Step 2: Generating database (my_database.db)...
"%PYTHON_PATH%" InfoMatching_Team4/database.py
if %errorlevel% neq 0 (
    echo Error: Failed to generate database. Please check if Python is installed and files exist.
    pause
    exit /b 1
)
echo Database generated successfully!
echo.

echo Step 3: Generating parsed database (my_database_parsed.db)...
"%PYTHON_PATH%" InfoMatching_Team4/db_Parsed.py
if %errorlevel% neq 0 (
    echo Error: Failed to generate parsed database.
    pause
    exit /b 1
)
echo Parsed database generated successfully!
echo.

echo Step 4: Starting file server on port 8000...
start "File Server" cmd /k ""%PYTHON_PATH%" -m http.server --directory uploads 8000"
echo File server started in a new window.
echo.

echo Step 5: Launching Streamlit app...
echo The app will open in your default browser.
echo.
echo Note: To stop the application, close this window and the File Server window.
echo To stop Milvus, run: stop_milvus.bat
echo.
"%PYTHON_PATH%" -m streamlit run InfoMatching_Team4/my_app/app.py

echo.
echo Application closed.
pause

