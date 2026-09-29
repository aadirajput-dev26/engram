import sys
import os
sys.path.insert(0, os.path.abspath("."))

import asyncio
import traceback
from app.db.session import async_session_factory
from app.services.query_service import process_query

async def main():
    async with async_session_factory() as db:
        try:
            res = await process_query(
                db=db,
                query_text="Summarize document",
                org_id="bb5fada1-d7aa-4c49-af0d-117f2b074229",
                workspace_id="21af0e43-cd85-413e-8f38-655e5cc733c8",
                collection_id="4412e2d0-78ee-409b-8eea-06ea44801e78",
                top_k=5,
            )
            print("SUCCESS! RESULT:")
            print("Route used:", res.get("route_used"))
            print("Answer:", res.get("answer")[:200] if res.get("answer") else "None")
        except Exception as e:
            print("ERROR CAUGHT:")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
