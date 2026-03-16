import os
from main import init_index, DOCUMENTS_DIR
from dotenv import load_dotenv

load_dotenv()

print(f"Checking {DOCUMENTS_DIR}...")
if os.path.exists(DOCUMENTS_DIR):
    print(f"Files: {os.listdir(DOCUMENTS_DIR)}")
else:
    print("Documents dir not found")

try:
    print("Initializing index...")
    init_index()
    print("Init finished.")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
