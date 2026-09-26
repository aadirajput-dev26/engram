from app.core.storage.local_storage import get_storage
import os

storage = get_storage()
key = "documents/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222/test_doc/test_ver/AI_Legal_Case_Management_System_Project_Specification.pdf"

print("1. Saving file...")
storage.save_file(key, b"hello test")

print("2. Getting file path...")
p = storage.get_file_path(key)
print("Saved file path:", p)
print("Path exists?", os.path.exists(p))
