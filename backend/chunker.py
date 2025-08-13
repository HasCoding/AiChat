from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List

def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """
    Uzun metni chunk'lara ayırır. Her chunk yaklaşık `chunk_size` karakter olur.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_text(text)
    return chunks
