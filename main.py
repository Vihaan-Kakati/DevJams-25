import os, time
from typing import List
from dotenv import load_dotenv
from pymongo import MongoClient
import fitz
from sentence_transformers import SentenceTransformer
from scipy.sparse import csr_matrix, issparse

load_dotenv()
MONGO_URI = os.environ["MONGO_URI"] 
DB_NAME = os.getenv("ATLAS_DB", "rag_db")
COLL_NAME = os.getenv("ATLAS_COLLECTION", "pdf_chunks")
MODEL_NAME = os.getenv("EMBED_MODEL", "sentence-transformers/all-mpnet-base-v2")

model = SentenceTransformer(MODEL_NAME)
EMBED_DIM = model.get_sentence_embedding_dimension()
print(f"LOADED {MODEL_NAME}, {EMBED_DIM}")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
coll = db[COLL_NAME]

#coll.create_index("pdf_id")
#coll.create_index("chunk_id")

def extract_text_from_pdf(path: str) -> List[dict]:
    doc = fitz.open(path)
    pages = []
    for i in range(len(doc)):
        text = doc[i].get_text("text")
        pages.append({"page_num": i+1, "text": text})
    doc.close()
    return pages

def chunk_text(text: str, max_chars = 500, overlap = 100) -> List[str]:
    chunks, start, n = [], 0, len(text)
    while start < n:
        end = min(start + max_chars, n)
        #while text[end] not in " .?!\n":
        #    if end == n: break
        #    end += 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks

def embed_texts(texts: List[str]) -> List[List[float]]:
    return model.encode(texts, convert_to_numpy=True).tolist()

def ingest_pdf(pdf_path: str, pdf_id: str, upsert=True):
    pages = extract_text_from_pdf(pdf_path)
    docs, chunk_id = [], 0
    for p in pages:
        page_num, text = p["page_num"], p["text"]
        chunks = chunk_text(text)
        if not chunks:
            continue
        embeddings = embed_texts(chunks)
        for i, chunk in enumerate(chunks):
            docs.append({
                "pdf_id": pdf_id,
                "chunk_id": f"{pdf_id}_{chunk_id}",
                "text": chunk,
                "embedding": embeddings[i],
                "meta": {"page": page_num, "created_at": time.time()}
            })
            chunk_id += 1

    if upsert:
        coll.delete_many({"pdf_id": pdf_id})
    if docs:
        coll.insert_many(docs)
    print(f"Ingested {len(docs)} chunks for {pdf_id}")
    
def search_similar(vector: List[float], other_pdf_id: str, k=3):
    pipeline = [
        {"$vectorSearch": {
            "index": "vector_index",
            "path": "embedding",
            "queryVector": vector,
            "numCandidates": 100,
            "limit": k,
            "filter": {"pdf_id": other_pdf_id}   # filter inside vector search
        }},
        {"$project": {
            "chunk_id": 1,
            "text": 1,
            "score": {"$meta": "vectorSearchScore"}
        }}
        ]
    return list(coll.aggregate(pipeline))

def compare_pdfs(pdf_id_a: str, pdf_id_b: str, k = 2):
    cursor = coll.find({"pdf_id": pdf_id_a}, {"_id": 0, "chunk_id": 1, "embedding": 1, "text": 1})
    matches, scores = [], []
    for doc in cursor:
        vector = doc["embedding"]
        results = search_similar(vector, pdf_id_b, k)
        for r in results:
            matches.append({"a_chunk": doc["text"], "b_chunk": r["text"], "score": r["score"]})
            scores.append(r["score"])
            
    overall = sum(scores)/len(scores) if scores else 0
    matches = sorted(matches, key = lambda x: x["score"], reverse = True)
    return {"overall_similarity": overall, "matches": matches}

pdf_a_path = "document_C.pdf"
pdf_b_path = "document_D.pdf"

ingest_pdf(pdf_a_path, "pdf_A")
ingest_pdf(pdf_b_path, "pdf_B")

result = compare_pdfs("pdf_A", "pdf_B", k = 3)
print("Overall similarity:", result["overall_similarity"])
for m in result["matches"][:10]:
    print(f"Score: {m['score']:.3f}")
    print("A:", m["a_chunk"][:120].replace("\n", " "))
    print("B:", m["b_chunk"][:120].replace("\n", " "))
    print("---")