@echo off
echo ========================================
echo SeeU Project - Dependency Installation
echo ========================================
echo.
echo Installing Python packages from requirements.txt...
echo This may take several minutes...
echo.

python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to install packages!
    echo Please make sure Python is installed and added to PATH.
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo You can now run launch_app.bat to start the application.
echo.
pause

