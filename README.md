# DocuChat AI

A React + FastAPI PDF chatbot with hosted Gemini embeddings, document-filtered semantic search, Gemini answers and expandable page/chunk citations. The backend does **not** install or load PyTorch, Sentence Transformers, ChromaDB or NumPy.

## Features

- Upload multiple text PDFs and select a document to ask questions about it.
- View and delete documents from a shared demo library.
- Retrieve only chunks belonging to the selected document.
- Display retrieved text, page numbers and chunk references alongside Markdown answers.
- Protect every data endpoint with a server-side shared demo key. The frontend keeps it in page memory only.
- Store extracted text, metadata and 768-dimensional embeddings in Qdrant Cloud, outside Render's temporary filesystem.

## Architecture

```text
React (Render static site)
  └─ X-Demo-Key → FastAPI (Render Free, one worker)
       ├─ pypdf subprocess → bounded text chunks
       ├─ Gemini embedding API → gemini-embedding-001 (768 dimensions)
       ├─ Qdrant Cloud → document metadata + chunk text + vectors
       └─ Gemini generation API → answer + retrieved sources
```

Original PDF files and chat history are not retained. The old MiniLM/Chroma vectors are incompatible with Gemini vectors: reupload sample PDFs after migrating.

## Run locally

Requires Python 3.14 (tested with 3.14.5), Node.js 22.12+ and npm.

```bash
cd backend
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` privately: set `GEMINI_API_KEY`, a long random `DOCUCHAT_DEMO_KEY`, and Qdrant settings. Use `VECTOR_STORE=sqlite` only for a local experiment without a Qdrant account. Its file survives local restarts if retained, but **SQLite on Render Free is temporary and can be lost on restart, redeploy or spin-down**.

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

In another terminal:

```bash
cd my-react-app
npm ci
npm run dev
```

Open `http://localhost:5173/chat` and enter the demo key. Local API calls require the key too. A missing server key fails closed with 503; a wrong/missing client key returns 401. The public `/health` endpoint reports process liveness only.

## Deploy the existing Render services

Follow [DEPLOYMENT.md](DEPLOYMENT.md). It includes Qdrant provisioning, exact backend/frontend settings, private environment variables and live acceptance checks. No paid instance or persistent disk is required for this architecture.

## Verify changes

From the repository root after installing backend dependencies:

```bash
backend/.venv/bin/python -B -m unittest discover -s backend/tests -v
cd my-react-app
npm ci
npm run build
npm run lint
```

The offline suite tests real PDF extraction and SQLite lifecycles; Gemini and Qdrant HTTP contracts use mocks. Passing it does not establish live API-key/model access, quota availability or Render memory usage.

## API

Every data request requires `X-Demo-Key: <private demo key>`.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Public process liveness |
| GET | `/documents` | Library metadata and storage notice |
| POST | `/upload` | Multipart PDF upload (`file`) |
| POST | `/search` | `{ "question": "...", "document_id": "..." }` |
| POST | `/chat` | `{ "message": "...", "document_id": "..." }` |
| DELETE | `/documents/{document_id}` | Remove selected document and its chunks |

## Demo limits and privacy

- One upload, search, chat or deletion at a time; other operations receive 429 and can be retried. Start exactly one worker.
- Maximum 5 MB, 50 pages, 200,000 extracted characters and 250 chunks per PDF; 20 documents / 2,000 chunks for the shared library.
- PDF extraction has a 25-second timeout and, on Linux, a 192 MB subprocess address-space cap. Complex PDFs may be rejected. Scanned PDFs need OCR first.
- Everyone with the demo key shares the library and can read/delete its documents. This is not individual-user authentication. Use sample/public PDFs.
- Extracted text is sent to Google for embeddings/answers and stored in Qdrant when configured. Gemini free-tier input/output may be used to improve Google's products.
- Retrieval can select irrelevant excerpts and Gemini may make mistakes. Expand the sources and verify answers. Displayed sources are retrieved context, not independently verified claims.
- Render Free can sleep after 15 minutes idle and may take about a minute to wake. Qdrant free clusters can suspend after one week unused and be deleted after four weeks of inactivity.
- Gemini free quotas vary by project/model. Quota exhaustion returns an error; the code has no paid-provider fallback. Enabling billing or upgrading providers changes costs.

Provider references: [Render Free](https://render.com/docs/free), [Qdrant free cluster](https://qdrant.tech/documentation/cloud/create-cluster/), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini quotas](https://ai.google.dev/gemini-api/docs/rate-limits).

Developed by [sh1mal](https://github.com/sh1mal).
