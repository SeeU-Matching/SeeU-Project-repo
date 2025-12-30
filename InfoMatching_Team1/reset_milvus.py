from pymilvus import utility
from matching_utils import connect_milvus
connect_milvus()
for name in ["resume", "job_postings"]:
    if utility.has_collection(name):
        utility.drop_collection(name)