import os, time
from typing import List
from dotenv import load_dotenv
from pymongo import MongoClient
import fitz
from sentence_transformers import SentenceTransformer
from transformers import pipeline
import torch
import numpy as np

load_dotenv()
MONGO_URI = os.environ["MONGO_URI"] 
DB_NAME = os.getenv("ATLAS_DB", "rag_db")
COLL_NAME = os.getenv("ATLAS_COLLECTION", "pdf_chunks")
MODEL_NAME = os.getenv("EMBED_MODEL", "sentence-transformers/all-mpnet-base-v2")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device=0 if torch.cuda.is_available() else -1)

device = "cuda" if torch.cuda.is_available() else "cpu"
model = SentenceTransformer(MODEL_NAME, device=device, local_files_only=True)
EMBED_DIM = model.get_sentence_embedding_dimension()
print(f"LOADED {MODEL_NAME} on {device}, {EMBED_DIM}")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
coll = db[COLL_NAME]

def extract_text_from_pdf(path: str) -> List[dict]:
    doc = fitz.open(path)
    pages = []
    for i in range(len(doc)):
        text = doc[i].get_text("text")
        pages.append({"page_num": i+1, "text": text})
    doc.close()
    return pages

def chunk_text(text: str, max_chars = 1000, overlap = 100) -> List[str]:
    chunks, start, n = [], 0, len(text)

    while start < n:
        end = min(start + max_chars, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks

def embed_texts(texts: List[str], batch_size=64) -> List[List[float]]:
    return model.encode(texts, convert_to_numpy=True, batch_size=batch_size, show_progress_bar=True).tolist()

def ingest_pdf(pdf_path: str, pdf_id: str, upsert=True, batch_size=64):
    pages = extract_text_from_pdf(pdf_path)
    docs, chunk_id = [], 0
    all_chunks, meta_info = [], []

    for p in pages:
        page_num, text = p["page_num"], p["text"]
        chunks = chunk_text(text)
        if not chunks:
            continue
        all_chunks.extend(chunks)
        meta_info.extend([{"page": page_num, "created_at": time.time()}]*len(chunks))

    if not all_chunks:
        print(f"No text chunks found in {pdf_path}")
        return

    embeddings = embed_texts(all_chunks, batch_size=batch_size)

    for i, chunk in enumerate(all_chunks):
        docs.append({
            "pdf_id": pdf_id,
            "chunk_id": f"{pdf_id}_{chunk_id}",
            "text": chunk,
            "embedding": embeddings[i],
            "meta": meta_info[i]
        })
        chunk_id += 1

    if upsert:
        coll.delete_many({"pdf_id": pdf_id})

    BATCH_INSERT = 1000
    for i in range(0, len(docs), BATCH_INSERT):
        coll.insert_many(docs[i:i+BATCH_INSERT])

    print(f"Ingested {len(docs)} chunks for {pdf_id}")
    
def compare_pdfs_vectorized(pdf_id_a: str, pdf_id_b: str, k = 3):  # <-- NEW
    cursor_a = list(coll.find({"pdf_id": pdf_id_a}, {"_id":0,"text":1,"embedding":1}))
    cursor_b = list(coll.find({"pdf_id": pdf_id_b}, {"_id":0,"text":1,"embedding":1}))

    if not cursor_a or not cursor_b:
        return {"overall_similarity":0, "matches":[]}

    emb_a = np.array([d["embedding"] for d in cursor_a])
    emb_b = np.array([d["embedding"] for d in cursor_b])

    emb_a = emb_a / np.linalg.norm(emb_a, axis=1, keepdims=True)
    emb_b = emb_b / np.linalg.norm(emb_b, axis=1, keepdims=True)

    sim_matrix = np.dot(emb_a, emb_b.T)

    matches = []
    for i, doc_a in enumerate(cursor_a):
        top_idx = sim_matrix[i].argsort()[::-1][:k]
        for idx in top_idx:
            matches.append({
                "a_chunk": doc_a["text"],
                "b_chunk": cursor_b[idx]["text"],
                "score": float(sim_matrix[i, idx])
            })

    overall = float(sim_matrix.mean())
    matches = sorted(matches, key=lambda x:x["score"], reverse=True)
    return {"overall_similarity": overall, "matches": matches}

def summarize_matches(matches, max_chunks=5):
    top_matches = matches[:max_chunks]
    
    combined_text = ""
    for m in top_matches:
        if(m['score'] > 0.7):
            combined_text += f"{m['a_chunk']}\n {m['b_chunk']}\n\n"

    CHUNK_SIZE = 1000
    summaries = []
    for i in range(0, len(combined_text), CHUNK_SIZE):
        chunk = combined_text[i:i+CHUNK_SIZE]
        summary = summarizer(chunk, max_length=100, min_length=30, do_sample=False)[0]['summary_text']
        summaries.append(summary)
    
    return " ".join(summaries)

pdf_a_path = "<pdf path>"
pdf_b_path = "<pdf path>"

ingest_pdf(pdf_a_path, "pdf_A")
ingest_pdf(pdf_b_path, "pdf_B")

result = compare_pdfs_vectorized("pdf_A", "pdf_B", k = 3)
print("Overall similarity:", result["overall_similarity"])
if result["overall_similarity"] < 0.7:
    print("Similarity is very low.")
else:
    for m in result["matches"][:10]:
        print(f"Score: {m['score']:.3f}")
        print("A:", m["a_chunk"][:120].replace("\n", " "))
        print("B:", m["b_chunk"][:120].replace("\n", " "))
        print("---")

    summary_text = summarize_matches(result["matches"], max_chunks=5)
    print("Summary of similarities:\n", summary_text)
