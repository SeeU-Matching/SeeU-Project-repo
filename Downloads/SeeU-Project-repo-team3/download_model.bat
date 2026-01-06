@echo off
echo ========================================
echo Pre-downloading BGE-M3 Model
echo ========================================
echo.
echo This script will download the embedding model before running the app.
echo This helps avoid errors when loading the model in Streamlit.
echo.
pause

venv\Scripts\python.exe download_model.py

echo.
echo ========================================
if %errorlevel% equ 0 (
    echo Model download completed successfully!
) else (
    echo Model download failed. Please check the error messages above.
)
echo ========================================
pause

