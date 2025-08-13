import fitz  # PyMuPDF

def pdf_to_text(pdf_path: str) -> str:
    """
    Verilen PDF dosyasındaki tüm sayfalardan metin çıkarır.
    """
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    return full_text.strip()
