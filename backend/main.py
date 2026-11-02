"""Small, shared-key-protected PDF RAG demo. No local ML model is loaded."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from threading import Lock
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

load_dotenv(Path(__file__).with_name(".env"))

from llm import DIMENSIONS, embed_texts, generate_answer
from citations import cited_response
from storage import get_store

app = FastAPI(title="DocuChat AI", version="2.0.0")
operation_lock = Lock()


def require_demo_access(x_demo_key: str | None = Header(default=None)):
    expected = os.getenv("DOCUCHAT_DEMO_KEY", "")
    # Fail closed everywhere; local development uses the same protection.
    if not expected:
        raise HTTPException(503, "Demo access not configured")
    if not x_demo_key or not secrets.compare_digest(x_demo_key.encode(), expected.encode()):
        raise HTTPException(401, "Demo access required")


protected = [Depends(require_demo_access)]


class AccessAndBodyLimit:
    """Authenticate before multipart parsing and bound the entire incoming body."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        path = scope["path"]
        if path not in {"/upload", "/chat", "/search", "/documents"} and not path.startswith("/documents/"):
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        try:
            require_demo_access(headers.get(b"x-demo-key", b"").decode("utf-8"))
        except (HTTPException, UnicodeDecodeError) as error:
            status = error.status_code if isinstance(error, HTTPException) else 401
            detail = error.detail if isinstance(error, HTTPException) else "Demo access required"
            return await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
        mutation = scope["method"] in {"POST", "DELETE"}
        if mutation and not operation_lock.acquire(blocking=False):
            return await JSONResponse({"detail": "Demo is busy. Please retry shortly."}, status_code=429)(scope, receive, send)
        try:
            if scope["method"] == "POST":
                limit = 6 * 1024 * 1024 if path == "/upload" else 16 * 1024
                try:
                    length = int(headers.get(b"content-length", b"0"))
                except ValueError:
                    length = limit + 1
                if length < 0 or length > limit:
                    return await JSONResponse({"detail": "Request too large"}, status_code=413)(scope, receive, send)
                body = bytearray()
                while True:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        return
                    body.extend(event.get("body", b""))
                    if len(body) > limit:
                        return await JSONResponse({"detail": "Request too large"}, status_code=413)(scope, receive, send)
                    if not event.get("more_body", False):
                        break
                delivered = False

                async def replay():
                    nonlocal delivered
                    if delivered:
                        return await receive()
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}

                await self.app(scope, replay, send)
            else:
                await self.app(scope, receive, send)
        finally:
            if mutation:
                operation_lock.release()


app.add_middleware(AccessAndBodyLimit)
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
origins += [v.strip().rstrip("/") for v in os.getenv("FRONTEND_ORIGIN", "").split(",") if v.strip()]
# Add last so CORS headers also cover authentication and body-limit errors.
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "X-Demo-Key"])


def chunk_text(text, chunk_size=120, overlap=20):
    words = text.split()
    chunks = []
    for start in range(0, len(words), chunk_size - overlap):
        # The byte cap also bounds unusual unbroken or non-English input below
        # the embedding model's 2,048 input-token limit.
        part, byte_count = [], 0
        for char in " ".join(words[start:start + chunk_size]):
            size = len(char.encode("utf-8"))
            if byte_count + size > 1600:
                chunks.append("".join(part))
                part, byte_count = [], 0
            part.append(char)
            byte_count += size
        if part:
            chunks.append("".join(part))
    return chunks


def extract_pdf(pdf_bytes):
    # Parse untrusted PDFs in an isolated process with a Linux memory cap/time limit.
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("pdf_extract.py"))],
                                input=pdf_bytes, capture_output=True, timeout=25, check=False)
        if result.returncode:
            detail = result.stdout.decode(errors="replace")
            if detail.startswith("LIMIT:"):
                raise HTTPException(413, detail[6:])
            raise HTTPException(400, "Cannot read PDF (encrypted, malformed, or too complex)")
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(413, "PDF took too long to process. Try a smaller document.") from None
    except (ValueError, OSError):
        raise HTTPException(400, "Cannot read PDF") from None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    document_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_id: str = Field(pattern=r"^[a-f0-9]{32}$")


def retrieve_matches(question, document_id):
    if not question.strip():
        raise HTTPException(400, "Question cannot be empty")
    store = get_store()
    if not store.get_document(document_id):
        raise HTTPException(404, "Selected document not found")
    vector = embed_texts([question.strip()], "RETRIEVAL_QUERY")[0]
    return store.search(document_id, vector, limit=3)


@app.post("/upload", dependencies=protected)
def upload_pdf(file: UploadFile = File(...)):
    try:
        pdf_bytes = file.file.read(5 * 1024 * 1024 + 1)
    finally:
        file.file.close()
    if len(pdf_bytes) > 5 * 1024 * 1024:
        raise HTTPException(413, "PDF too large (maximum 5 MB)")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(400, "Invalid PDF")
    store = get_store()
    documents = store.list_documents()
    if len(documents) >= 20:
        raise HTTPException(413, "Demo library is full (20 documents). Delete a document first.")
    extracted = extract_pdf(pdf_bytes)
    chunks = []
    for page_number, text in enumerate(extracted["pages"], start=1):
        for text_chunk in chunk_text(text):
            chunks.append({"text": text_chunk, "chunk": len(chunks) + 1, "page": page_number})
    if not chunks:
        raise HTTPException(422, "No extractable text. Scanned PDFs need OCR first.")
    if len(chunks) > 250 or sum(d["chunks"] for d in documents) + len(chunks) > 2000:
        raise HTTPException(413, "Document or demo library too large. Use a smaller PDF or delete documents.")
    vectors = embed_texts([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT")
    metadata = {"document_id": uuid4().hex,
                "filename": Path((file.filename or "uploaded.pdf").replace("\\", "/")).name[:200],
                "pages": len(extracted["pages"]), "characters": sum(map(len, extracted["pages"])),
                "chunks": len(chunks), "embedding_dimensions": DIMENSIONS}
    store.add_document(metadata, chunks, vectors)
    return metadata


@app.post("/search", dependencies=protected)
def search(request: SearchRequest):
    matches = retrieve_matches(request.question, request.document_id)
    return {"filename": matches[0]["filename"] if matches else "", "matches": matches}


@app.post("/chat", dependencies=protected)
def chat(request: ChatRequest):
    matches = retrieve_matches(request.message, request.document_id)
    if not matches:
        return {"reply": "I couldn't find information in the selected PDF.", "sources": [],
                "other_context": [], "citation_warning": ""}
    return cited_response(generate_answer(request.message.strip(), matches), matches)


@app.get("/documents", dependencies=protected)
def list_documents():
    mode = os.getenv("VECTOR_STORE", "qdrant" if os.getenv("RENDER") == "true" else "sqlite").strip().lower()
    return {"documents": get_store().list_documents(), "storage": {
        "mode": mode,
        "notice": ("Stored in Qdrant Cloud; subject to cluster limits and inactivity policy."
                   if mode == "qdrant" else "Temporary demo storage: reupload PDFs after Render restarts.")}}


@app.delete("/documents/{document_id}", dependencies=protected)
def delete_document(document_id: str):
    if not get_store().delete_document(document_id):
        raise HTTPException(404, "Document not found")
    return {"message": "Document deleted", "document_id": document_id}


@app.get("/health")
def health():
    # Liveness only; external services and secrets are deliberately not disclosed.
    return {"status": "ok"}
