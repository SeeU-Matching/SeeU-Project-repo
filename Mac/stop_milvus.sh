#!/bin/bash

echo "========================================"
echo "Stopping Milvus Vector Database"
echo "========================================"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

cd milvus_setup
docker-compose down

if [ $? -ne 0 ]; then
    echo "Error: Failed to stop Milvus."
else
    echo "Milvus stopped successfully!"
fi

cd ..
echo ""
read -p "Press Enter to continue..."

