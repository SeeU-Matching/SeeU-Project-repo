#!/bin/bash

echo "========================================"
echo "SeeU Project - Dependency Installation"
echo "========================================"
echo ""
echo "Installing Python packages from requirements.txt..."
echo "This may take several minutes..."
echo ""

python3 -m pip install -r ../requirements.txt

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "You can now run launch_app.sh to start the application."
echo ""
read -p "Press Enter to continue..."

