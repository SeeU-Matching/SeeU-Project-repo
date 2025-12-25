macOS Security Setup

### Step 1: Allow Terminal to Access Files

When you first run the scripts, macOS may block access. You need to grant permissions:

1. **Open System Settings** (or System Preferences on older macOS)
2. Go to **Privacy & Security** → **Files and Folders**
3. Find **Terminal** (or your terminal app)
4. Enable access to:
   - Desktop
   - Documents
   - Downloads (if needed)

### Step 2: Gatekeeper - Allow Script Execution

If you get "operation not permitted" errors:

```bash
# Navigate to the project directory
cd "path/to/SeeU-Project-main"

# Make scripts executable
chmod +x Mac/*.sh

# For first run, you may need to allow the script
xattr -d com.apple.quarantine Mac/*.sh
```

### Step 3: Docker Permissions

1. Open **Docker Desktop**
2. Go to **Settings** → **Resources**
3. Ensure Docker has access to:
   - File Sharing: Add your project directory
   - Minimum Resources: 4 GB RAM, 2 CPUs

### Step 4: Python Security Prompt

When Python tries to access files, macOS will show a prompt:
- Click **"OK"** or **"Allow"**
- This is normal and only happens once per permission type

