#!/bin/bash

echo "========================================"
echo "SeeU Project - Job Matching App Launcher"
echo "========================================"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

echo "Step 1: Starting Milvus vector database..."
cd milvus_setup
docker-compose up -d
if [ $? -ne 0 ]; then
    echo "Warning: Failed to start Milvus. Make sure Docker is installed and running."
    echo "You can install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    cd ..
    read -p "Press Enter to exit..."
    exit 1
fi
cd ..
echo "Milvus started successfully!"
echo "Waiting for Milvus to initialize (5 seconds)..."
sleep 5
echo ""

echo "Step 2: Generating database (my_database.db)..."
python3 InfoMatching_Team4/database.py
if [ $? -ne 0 ]; then
    echo "Error: Failed to generate database. Please check if Python is installed and files exist."
    read -p "Press Enter to exit..."
    exit 1
fi
echo "Database generated successfully!"
echo ""

echo "Step 3: Generating parsed database (my_database_parsed.db)..."
python3 InfoMatching_Team4/db_Parsed.py
if [ $? -ne 0 ]; then
    echo "Error: Failed to generate parsed database."
    read -p "Press Enter to exit..."
    exit 1
fi
echo "Parsed database generated successfully!"
echo ""

echo "Step 4: Starting file server on port 8000..."
python3 -m http.server --directory uploads 8000 &
FILE_SERVER_PID=$!
echo "File server started (PID: $FILE_SERVER_PID)"
echo ""

echo "Step 5: Launching Streamlit app..."
echo "The app will open in your default browser."
echo ""
echo "Note: To stop the application, press Ctrl+C in this terminal."
echo "To stop Milvus, run: ./Mac/stop_milvus.sh"
echo "To stop the file server, run: kill $FILE_SERVER_PID"
echo ""

# Store PIDs for cleanup
echo $FILE_SERVER_PID > .file_server.pid

# Trap Ctrl+C to cleanup
trap 'echo ""; echo "Stopping file server..."; kill $FILE_SERVER_PID 2>/dev/null; rm -f .file_server.pid; echo "Application closed."; exit' INT

streamlit run InfoMatching_Team4/my_app/app.py

# Cleanup on normal exit
kill $FILE_SERVER_PID 2>/dev/null
rm -f .file_server.pid
echo ""
echo "Application closed."

