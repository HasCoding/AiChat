import os
import numpy as np
import faiss
from typing import List
from sentence_transformers import SentenceTransformer
import pickle

# Türkçe ve çok dilli destek için uygun bir model
embedding_model = SentenceTransformer("intfloat/multilingual-e5-base")

def embed_chunks(chunks: List[str]) -> np.ndarray:
    """
    Verilen metin chunk'larını embed eder ve numpy array olarak döner.
    """
    embeddings = embedding_model.encode(chunks, show_progress_bar=True)
    return np.array(embeddings)

def save_faiss_index(embeddings: np.ndarray, save_path: str):
    """
    Embedding'leri FAISS index'e ekler ve dosya olarak kaydeder.
    """
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    faiss.write_index(index, save_path)
    print(f"📦 FAISS index kaydedildi: {save_path}")  # ← ekle bunu

def load_faiss_index(index_path: str) -> faiss.Index:
    """
    Kayıtlı FAISS index dosyasını yükler.
    """
    return faiss.read_index(index_path)

def save_chunks(chunks: List[str], filename: str, save_dir: str = "backend/chunks"):
    os.makedirs(save_dir, exist_ok=True)
    chunk_path = os.path.join(save_dir, filename + ".pkl")
    with open(chunk_path, "wb") as f:
        pickle.dump(chunks, f)