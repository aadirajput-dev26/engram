import traceback
try:
    from app.core.vectorstore.qdrant_service import ensure_collection, _get_client
    client = _get_client()
    print("Qdrant client:", client)
    cols = client.get_collections()
    print("Collections:", cols)
    ensure_collection(768)
    print("ensure_collection(768) OK!")
except Exception as e:
    print("Qdrant Error:")
    traceback.print_exc()
