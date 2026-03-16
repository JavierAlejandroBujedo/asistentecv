import os
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX_NAME")

pc = Pinecone(api_key=api_key)
index = pc.Index(index_name)

print(f"Stats for index: {index_name}")
print(index.describe_index_stats())
