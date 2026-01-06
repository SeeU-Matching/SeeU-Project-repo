@echo off
echo ========================================
echo Milvus Diagnostic Tool
echo ========================================
echo.
echo This script will check if Milvus is running
echo and if your data is properly stored.
echo.
pause

venv\Scripts\python.exe check_milvus.py

echo.
pause

