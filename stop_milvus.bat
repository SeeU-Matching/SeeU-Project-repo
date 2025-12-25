@echo off
echo ========================================
echo Stopping Milvus Vector Database
echo ========================================
echo.

cd milvus_setup
docker-compose down

if %errorlevel% neq 0 (
    echo Error: Failed to stop Milvus.
) else (
    echo Milvus stopped successfully!
)

cd ..
echo.
pause

