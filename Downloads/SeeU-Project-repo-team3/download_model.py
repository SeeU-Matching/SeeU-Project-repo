"""
Pre-download BGE-M3 model to avoid issues when loading in Streamlit.
Run this script once before using the application.
"""
import os
import sys

# Set environment variables to avoid Windows stdout issues
if sys.platform == 'win32':
    os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
    os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['HF_HUB_DISABLE_TQDM'] = '1'

print("=" * 60)
print("Pre-downloading BGE-M3 Model")
print("=" * 60)
print()
print("This will download the embedding model (~1-2GB)")
print("to avoid tqdm compatibility issues in Streamlit.")
print()
print("Downloading BGE-M3 model...")
print("This may take a few minutes on first run...")
print()

try:
    from FlagEmbedding import BGEM3FlagModel
    print("Loading model (this will download if not already cached)...")
    model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False)
    print()
    print("=" * 60)
    print("✓ Model downloaded and loaded successfully!")
    print("=" * 60)
    print()
    print("You can now run the Streamlit application.")
    print("The model will load from cache (much faster).")
except Exception as e:
    print()
    print("=" * 60)
    print("✗ Error downloading model")
    print("=" * 60)
    print(f"Error: {e}")
    print()
    print("Troubleshooting:")
    print("1. Make sure you have internet connection")
    print("2. Check if you have enough disk space (model is ~1-2GB)")
    print("3. Try running as administrator")
    print("4. Check if antivirus is blocking the download")
    sys.exit(1)

