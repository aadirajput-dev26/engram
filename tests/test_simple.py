import sys
import traceback

print("Starting test_simple.py...")

try:
    print("Importing rapidocr_onnxruntime...")
    import rapidocr_onnxruntime
    print("rapidocr OK!")
except Exception as e:
    print("rapidocr ERROR:")
    traceback.print_exc()

try:
    print("Importing fastembed...")
    import fastembed
    print("fastembed OK!")
except Exception as e:
    print("fastembed ERROR:")
    traceback.print_exc()

try:
    print("Importing app.main...")
    import app.main
    print("app.main OK!")
except Exception as e:
    print("app.main ERROR:")
    traceback.print_exc()

print("End of test_simple.py")
