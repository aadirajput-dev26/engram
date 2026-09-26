import traceback
try:
    from app.main import app
    print("app loaded successfully")
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
except Exception as e:
    print("EXCEPTION OCCURRED:")
    traceback.print_exc()
