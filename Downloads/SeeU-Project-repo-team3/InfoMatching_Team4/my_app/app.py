import os
import sys

# Set environment variables early to avoid Windows stdout issues with tqdm
# This must be done BEFORE importing any model-related modules
if sys.platform == 'win32':
    os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
    os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import streamlit as st

st.set_page_config(
    page_title="Job Matching Demo",
    layout="wide",
)

st.title("Job Matching Demo")
st.write("Welcome! Use the sidebar to navigate to the different pages.")
