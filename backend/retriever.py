import os
import numpy as np
import faiss
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from embedder import load_faiss_index
import pickle

embedding_model = SentenceTransformer("intfloat/multilingual-e5-base")

# Chunk metinlerini burada tutacağız (her PDF için ayrı .pkl dosyası)
INDEX_DIR = "indexes"
CHUNK_DIR = "indexes"

def load_chunks(pdf_basename: str) -> List[str]:
    """
    PDF adına göre chunk metinlerini yükle (.pkl dosyasından)
    """
    chunk_path = os.path.join(CHUNK_DIR, pdf_basename + ".pkl")
    with open(chunk_path, "rb") as f:
        return pickle.load(f)

def search_in_index(query: str, index_name: str, k: int = 3) -> List[dict]:
    index_path = os.path.join(INDEX_DIR, index_name + ".faiss")
    index = load_faiss_index(index_path)
    chunks = load_chunks(index_name)

    query_embedding = embedding_model.encode([query])
    D, I = index.search(np.array(query_embedding), k)

    results = []
    for idx, i in enumerate(I[0]):
        if i == -1:
            continue  # 🔐 eşleşme yoksa atla
        if i < len(chunks):
            results.append({
                "text": chunks[i],
                "score": float(D[0][idx]),
                "source_pdf": index_name + ".pdf"
            })
    return results

def load_faiss_index(index_path: str) -> faiss.Index:
    """
    Kayıtlı FAISS index dosyasını yükler.
    """
    abs_path = os.path.abspath(index_path)
    print(f"📥 FAISS index yükleniyor: {abs_path}")
    return faiss.read_index(abs_path)