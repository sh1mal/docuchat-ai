
# DocuChat AI

A full-stack Retrieval-Augmented Generation (RAG) application that lets users upload PDF documents and ask questions about their contents using Google Gemini.

Built with React, FastAPI, Sentence Transformers, and ChromaDB.

## Features

- Upload and process multiple PDF documents
- Extract text and split it into overlapping chunks
- Generate semantic embeddings using Sentence Transformers
- Store document chunks persistently in ChromaDB
- Select a document and ask questions about its contents
- Generate document-grounded answers using Google Gemini
- Expand source citations to inspect retrieved text
- View and delete saved documents
- Render AI responses with Markdown formatting
- Dark-themed, responsive chat interface

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React, JavaScript, Vite, CSS |
| Backend | Python, FastAPI, Pydantic |
| LLM | Google Gemini API |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) |
| Vector Database | ChromaDB |
| PDF Processing | pypdf |
| Markdown Rendering | react-markdown, remark-gfm |

## How RAG Works

**Document ingestion**

1. A user uploads a PDF through the React interface.
2. FastAPI extracts text from the document using pypdf.
3. The extracted text is divided into overlapping chunks.
4. Sentence Transformers converts each chunk into an embedding.
5. ChromaDB stores the chunks, embeddings, and document metadata.

**Question answering**

1. The user selects a PDF and submits a question.
2. The backend converts the question into an embedding.
3. ChromaDB retrieves the most similar chunks from the selected PDF.
4. The retrieved text is supplied to Gemini as context.
5. Gemini generates an answer based on that context.
6. React displays the answer and expandable source references.

The retrieval process uses document IDs to prevent chunks from different selected PDFs from being mixed together.

## Project Structure

```text
docuchat-ai/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── test.py
├── my-react-app/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md
```

The local `.env`, virtual environment, ChromaDB database files, and uploaded private documents are excluded from Git.

## Running Locally

### Prerequisites

- Python and pip
- Node.js and npm
- A Google Gemini API key

### 1. Clone the repository

```bash
git clone https://github.com/sh1mal/docuchat-ai.git
cd docuchat-ai
```

### 2. Set up the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a `.env` file inside `backend/`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Start FastAPI:

```bash
fastapi dev main.py
```

The backend runs at:

`http://127.0.0.1:8000`

API documentation is available at:

`http://127.0.0.1:8000/docs`

### 3. Set up the frontend

Open a second terminal in the project directory:

```bash
cd my-react-app
npm ci
npm run dev
```

Open:

`http://localhost:5173`

### 4. Use the application

1. Navigate to the Chat page.
2. Upload a PDF containing extractable text.
3. Select a document from Saved Documents.
4. Ask a question related to the selected PDF.
5. Expand the source chunks to inspect the retrieved context.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/upload` | Upload and index a PDF |
| GET | `/documents` | List indexed PDFs |
| DELETE | `/documents/{document_id}` | Delete an indexed PDF |
| POST | `/search` | Retrieve relevant document chunks |
| POST | `/chat` | Generate an answer using RAG |

The `/chat` endpoint accepts JSON containing `message` and `document_id`.

## Current Limitations

- The application is designed for local development.
- PDF uploads are limited to 5 MB.
- Scanned PDFs without extractable text are not supported.
- ChromaDB stores extracted text and embeddings, not the original PDF file.
- Document data is stored on the local machine.
- Authentication and per-user access control are not yet implemented.
- Chat history is maintained in React state and is not persisted.
- Gemini responses may be affected by API availability and rate limits.

Do not expose this version as a public multi-user application without implementing authentication, document access controls, and API abuse protection.

## Future Improvements

- User authentication and private document libraries
- Persistent conversation history
- More precise page-level citations
- Improved retrieval relevance filtering
- Cloud deployment with durable vector storage
- Automated backend and frontend tests

## Author

Developed by [sh1mal](https://github.com/sh1mal).
