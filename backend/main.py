from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import os
import json
import re
from retriever import search_in_index
from pdf_reader import pdf_to_text
from chunker import split_text
from embedder import embed_chunks, save_faiss_index, save_chunks
from dotenv import load_dotenv
import asyncio

# .env dosyasındaki ortam değişkenlerini yükle
load_dotenv()

# --- Konfigürasyon Yolları ---
json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/data.json'))
prompt_path = os.path.join(os.path.dirname(__file__), "prompt.json")
PDF_DIR = "pdfData"
INDEX_DIR = "indexes"

# --- Sıkça Sorulan Soruları Yükle ---
with open(json_path, "r", encoding="utf-8") as f:
    frequent_questions = json.load(f)

# --- CORS Ayarları ---
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# --- FastAPI App ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Prompt Ayarı ---
OLLAMA_URL = "http://localhost:11434/api/chat"  # Ollama'nın yerel adresi
PROMPT_MD = ""

try:
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_data = json.load(f)
        PROMPT_MD = prompt_data.get("system_prompt", "Sen yardımcı bir asistansın.")
except Exception:
    PROMPT_MD = """
        Sen Pamukkale Üniversitesi için görevli bir yardımcı asistansın. 
        - Sadece verilen bağlamdan bilgi üret. 
        - Bağlamda olmayan şeyleri uydurma, tahminde bulunma. 
        - Yanıtları kısa, net ve odaklı ver.
        """

# --- PDF İşleme ---
def process_pdfs_and_create_indexes(pdf_files: list):
    os.makedirs(INDEX_DIR, exist_ok=True)
    for file in pdf_files:
        pdf_path = os.path.join(PDF_DIR, file)
        index_name = file.replace(".pdf", "")
        index_path = os.path.join(INDEX_DIR, index_name + ".faiss")
        if not os.path.exists(pdf_path):
            continue
        if os.path.exists(index_path):
            continue
        try:
            text = pdf_to_text(pdf_path)
            chunks = split_text(text)
            if chunks:
                embeddings = embed_chunks(chunks)
                save_chunks(chunks, index_name, save_dir=INDEX_DIR)
                save_faiss_index(embeddings, index_path)
        except Exception as e:
            print(f"⚠️ Hata ({file}): {e}")

# --- Başlangıçta PDF'leri işle ---
@app.on_event("startup")
async def startup_event():
    print("🚀 FastAPI başlatılıyor...")
    TARGET_PDF_FILES = ["personel.pdf", "ogrenci.pdf"]
    process_pdfs_and_create_indexes(TARGET_PDF_FILES)
    print("✅ PDF indeksleme tamam.")

# --- Sabitler ---
REDIRECT_URL = "https://app.pusula.pau.edu.tr/gbs/Oneri/Talep.aspx"
CONTINUATION_THRESHOLD = 3

# Chat API fonksiyonunuzun ilgili kısmı (düzeltilmiş)
@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("content")
    bot_response_count = data.get("bot_response_count", 0)
    user_role = data.get("role")

    if not user_message:
        raise HTTPException(status_code=400, detail="Mesaj içeriği boş olamaz.")

    # --- ÖZEL KOMUTLARI YÖNET (Normal JSON yanıtı) ---
    if user_message == "ACTION_CONTINUE_NO":
        return JSONResponse({
            "message": {"content": "Sorunuz çözüme ulaştı mı?", "role": "assistant"},
            "type": "resolution_prompt",
            "options": [
                {"text": "Evet, çözüldü", "payload": "ACTION_RESOLVED_YES"},
                {"text": "Talep oluştur sayfasına yönlendir", "payload": "ACTION_RESOLVED_NO"}
            ]
        })

    if user_message == "ACTION_RESOLVED_YES":
        return JSONResponse({
            "message": {"content": "Yardımcı olabildiğime sevindim. İyi günler dilerim!", "role": "assistant"},
            "type": "end_chat"
        })

    if user_message == "ACTION_RESOLVED_NO":
        return JSONResponse({
            "message": {"content": f"Anlıyorum. Daha fazla yardım için sizi talep sayfamıza yönlendiriyorum.", "role": "assistant"},
            "type": "redirect",
            "url": REDIRECT_URL
        })
        
    if user_message == "ACTION_CONTINUE_YES":
        return JSONResponse({
            "message": {"content": "Elbette, lütfen sorunuzu sorun.", "role": "assistant"},
            "type": "reset_and_continue"
        })

    # Belirli sayıda bot cevabına ulaşıldığında devam etme sorusunu sor
    if bot_response_count >= CONTINUATION_THRESHOLD:
        return JSONResponse({
            "message": {"content": "Sohbete devam etmek istiyor musunuz?", "role": "assistant"},
            "type": "continuation_prompt",
            "options": [
                {"text": "Evet", "payload": "ACTION_CONTINUE_YES"},
                {"text": "Hayır", "payload": "ACTION_CONTINUE_NO"}
            ]
        })

    # --- NORMAL SOHBET AKIŞI (Streaming yanıtı) ---
    index_name_map = {"ogrenci": "ogrenci", "personel": "personel"}
    user_role_cleaned = user_role.lower().strip() if user_role else ""
    if user_role_cleaned not in index_name_map:
        raise HTTPException(status_code=400, detail=f"Geçersiz kullanıcı rolü. Lütfen önce bir rol seçin.")

    target_index_name = index_name_map[user_role_cleaned]

    try:
        results = search_in_index(user_message, index_name=target_index_name, k=5)
        rag_context = "\n\n".join([item["text"] for item in results]) if results else "Bağlam verisi yok."
        sources_found = list(set([item["source_pdf"] for item in results])) if results else []
    except Exception as e:
        print(f"⚠️ Arama hatası: {e}")
        rag_context = "Bağlam verisi yok."
        sources_found = []

    system_message = f"{PROMPT_MD}\n\n### BAĞLAM\n{rag_context}"
    
    # Payload ve headers burada tanımlanıyor
    payload = {
        "model": "deepseek-r1:8b",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ],
        "stream": True
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    # Stream generator fonksiyonunu chat fonksiyonunun içinde tanımla
    async def stream_generator():
        metadata = {"type": "metadata", "sources": sources_found}
        yield f"data: {json.dumps(metadata)}\n\n"
        
        # Think tag durumunu takip etmek için değişkenler
        inside_think = False
        buffer = ""
        think_buffer = ""

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", OLLAMA_URL, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            message_chunk = chunk.get("message", {})
                            text_chunk = message_chunk.get("content", "")
                            
                            if not text_chunk:
                                continue
                                
                            # Buffer'a ekle
                            buffer += text_chunk
                            
                            # Think tag kontrolü ve temizleme
                            while buffer:
                                if not inside_think:
                                    # <think> tag'i arayalım
                                    think_start = buffer.find('<think>')
                                    if think_start != -1:
                                        # <think> öncesindeki içeriği gönder
                                        if think_start > 0:
                                            clean_content = buffer[:think_start]
                                            if clean_content:
                                                message_data = {"type": "message_chunk", "content": clean_content}
                                                yield f"data: {json.dumps(message_data)}\n\n"
                                                await asyncio.sleep(0.01)
                                        
                                        # <think> moduna geç
                                        inside_think = True
                                        buffer = buffer[think_start + 7:]  # '<think>' uzunluğu
                                        think_buffer = ""
                                    else:
                                        # <think> yok, tüm içeriği gönder
                                        if buffer:
                                            message_data = {"type": "message_chunk", "content": buffer}
                                            yield f"data: {json.dumps(message_data)}\n\n"
                                            await asyncio.sleep(0.01)
                                        buffer = ""
                                        break
                                else:
                                    # </think> tag'i arayalım
                                    think_end = buffer.find('</think>')
                                    if think_end != -1:
                                        # Think içeriğini buffer'a ekle (göndermeyeceğiz)
                                        think_buffer += buffer[:think_end]
                                        
                                        # </think> sonrasını al
                                        buffer = buffer[think_end + 8:]  # '</think>' uzunluğu
                                        inside_think = False
                                        think_buffer = ""  # Think içeriğini temizle
                                    else:
                                        # Henüz </think> bulamadık, think_buffer'a ekle
                                        think_buffer += buffer
                                        buffer = ""
                                        break

                            if chunk.get("done"):
                                # Kalan buffer'ı gönder (think tag'i dışında)
                                if buffer and not inside_think:
                                    message_data = {"type": "message_chunk", "content": buffer}
                                    yield f"data: {json.dumps(message_data)}\n\n"
                                break

                        except json.JSONDecodeError:
                            print(f"JSON Decode Hatası: {line}")
                            continue
                            
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            error_message = {"type": "error", "detail": f"API Hatası: {error_detail}"}
            yield f"data: {json.dumps(error_message)}\n\n"
        except Exception as e:
            error_message = {"type": "error", "detail": f"Sunucu Hatası: {str(e)}"}
            yield f"data: {json.dumps(error_message)}\n\n"
        finally:
            # Akış sonlandığında done mesajı gönder
            finally_data = {"type": "done"}
            yield f"data: {json.dumps(finally_data)}\n\n"

    # Normal stream generator'ı çağır
    return StreamingResponse(stream_generator(), media_type="text/event-stream")

# --- SSS Getir ---
@app.post("/get-faq")
async def get_faq(data: dict):
    url = data.get("url")
    role = data.get("role")
    if not url or not role:
        raise HTTPException(status_code=400, detail="Eksik parametre: url veya role")
    clean_url = url.replace(".aspx", "")
    entry = frequent_questions.get(clean_url)
    if not entry or entry.get("ktype") != role:
        return {"faq": []}
    return {"faq": entry["faqs"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)