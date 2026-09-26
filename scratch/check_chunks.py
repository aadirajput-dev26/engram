import psycopg2

conn = psycopg2.connect("postgresql://postgres:postgres@localhost:5434/rag_ai")
cur = conn.cursor()
cur.execute("SELECT page_start, page_end, text FROM chunks WHERE document_id='db195497-020c-405e-9203-f09c55283a89' ORDER BY page_start LIMIT 100;")
rows = cur.fetchall()
print(f"Total chunks: {len(rows)}")
with open("scratch/doc_chunks_summary.txt", "w", encoding="utf-8") as f:
    for p_start, p_end, txt in rows:
        f.write(f"=== Page {p_start}-{p_end} ===\n{txt}\n\n")

print("Wrote summary to scratch/doc_chunks_summary.txt")
