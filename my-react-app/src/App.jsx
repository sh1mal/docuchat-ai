
import { useState, useEffect } from "react";
import { Routes, Route, Link } from "react-router";
import "./App.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";



function Home() {
  return <h1>Welcome to DocuChat AI</h1>;
}

function About() {
  return <h1>Chat with your PDF documents using RAG.</h1>;
}

function Chat() {

  // Stores all chat messages as an array
  const [messages, setMessages] = useState([]);

  // Stores the current typed question
  const [message, setMessage] = useState("");

  // Stores selected PDF and upload response
  const [file, setFile] = useState(null);
  const [pdfInfo, setPdfInfo] = useState(null);

  // Loading and error states
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [showSources, setShowSources] = useState(true);

  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  

  // Upload PDF to FastAPI
  async function handleUpload(e) {
    e.preventDefault();

    if (!file) return;

    setUploading(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(
        `${API_BASE_URL}/upload`,
        {
          method: "POST",
          body: formData
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      await loadDocuments(data.document_id);
      setMessages([]);

      // Save document information
      setPdfInfo(data);

      // Reset chat when switching documents
      setMessages([]);

    } catch (err) {
      setError(err.message);

    } finally {
      setUploading(false);
    }
  }

  // Send question to Gemini via FastAPI
  async function handleSubmit(e) {
    e.preventDefault();

    const question = message.trim();

    if (!question || loading || !pdfInfo) return;

    // Immediately display the user's message
    setMessages(prev => [
      ...prev,
      { role: "user", text: question }
    ]);

    setMessage("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
  message: question,
  document_id: selectedDocumentId
})
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Chat failed");
      }

      // Add Gemini's response to chat history
      setMessages(prev => [
        ...prev,
        {
          role: "bot",
          text: data.reply,
          sources: data.sources || []
        }
      ]);

    } catch (err) {
      setError(err.message);

    } finally {
      setLoading(false);
    }
  }
  async function handleRefresh() {
  setError("");

  try {
    await loadDocuments();
  } catch (error) {
    console.error(error);
    setError(error.message);
  }
}
 

async function loadDocuments(preferredId = "") {
  const response = await fetch(
    `${API_BASE_URL}/documents`
  );

  if (!response.ok) {
    throw new Error("Failed to load documents");
  }

  const data = await response.json();
  const docs = data.documents;

  setDocuments(docs);

  // Prefer a newly uploaded document, then the
  // current selection, then the first available PDF
  const selected =
    docs.find(d => d.document_id === preferredId) ||
    docs.find(d => d.document_id === selectedDocumentId) ||
    docs[0] ||
    null;

  setSelectedDocumentId(selected?.document_id || "");
  setPdfInfo(selected);
}

useEffect(() => {
  loadDocuments().catch(err => {
    setError(err.message);
  });
}, []);

function handleSelectDocument(doc) {
  setSelectedDocumentId(doc.document_id);
  setPdfInfo(doc);
  setMessages([]);
}


async function handleDeleteDocument(documentId) {
  const confirmed = window.confirm(
    "Delete this PDF from the library?"
  );

  if (!confirmed) return;

  setError("");

  try {
    const response = await fetch(
      `${API_BASE_URL}/documents/${documentId}`,
      { method: "DELETE" }
    );

    if (!response.ok) {
      throw new Error("Failed to delete document");
    }

    // Reload the library after deletion
    await loadDocuments();
    setMessages([]);

  } catch (err) {
    setError(err.message);
  }
}


  return (
    <main className="chat-app">

      <h1>DocuChat AI</h1>
      <p>Ask questions about your PDF documents</p>

      {/* PDF Upload Section */}
      <section className="upload-box">
        <h3>Upload Document</h3>

        <form onSubmit={handleUpload}>
          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
            }}
          />

          <button disabled={!file || uploading}>
            {uploading ? "Processing..." : "Upload"}
          </button>
        </form>

        {pdfInfo && (
          <p className="success">
            ✓ {pdfInfo.filename} — {pdfInfo.chunks} chunks
          </p>
        )}
      </section>
            
      <section className="document-library">
        <h3>Saved Documents</h3>

        {documents.length === 0 ? (
          <p>No documents uploaded yet.</p>
        ) : (
          documents.map(doc => (
            <div
              key={doc.document_id}
              className="document-item"
            >
              <button
                type="button"
                className="document-select"
                onClick={() => handleSelectDocument(doc)}
                aria-pressed={
                  selectedDocumentId === doc.document_id
                }
              >
                📄 {doc.filename} ({doc.chunks} chunks)

                {selectedDocumentId === doc.document_id &&
                  " ✓ Selected"}
              </button>

              <button
                type="button"
                onClick={() =>
                  handleDeleteDocument(doc.document_id)
                }
              >
                Delete
              </button>
            </div>
          ))
        )}
      </section>

      
        <button onClick={() => setShowSources(prev => !prev)}>
        {showSources ? "Hide Sources" : "Show Sources"}
      </button>
      
        <button 
        disabled={messages.length === 0}
        onClick={() => {
          setMessages([])
        }}>
      Clear Chat
    </button>
      <button onClick={handleRefresh}>
    Refresh PDF Status
  </button>
      {/* Chat Messages */}
      <section className="chat-box">

        <div className="messages">
          {messages.length === 0 && (
            <p className="empty-chat">
              {selectedDocumentId
  ? "Ask a question about your selected PDF!"
  : "Upload a PDF and ask your first question!"}
            </p>
          )}

          {/* Render every message as a chat bubble */}
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`bubble ${msg.role}`}
            >
              <strong>
                {msg.role === "user" ? "You" : "AI"}
              </strong>

                    {msg.role === "bot" ? (
        <div className="markdown-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {msg.text}
          </ReactMarkdown>
        </div>
      ) : (
        <div>{msg.text}</div>
      )}

              {/* Show retrieved PDF chunk references */}
            {msg.sources?.length > 0 && showSources && (
  <div className="sources">
    <strong>Sources</strong>

          {msg.sources.map((source, index) => (
            <details key={index} name="source-chunks">
              <summary>Chunk {source.chunk}</summary>
              <p>{source.text}</p>
            </details>
          ))}
        </div>
      )}
            </div>
          ))}

          {/* Loading indicator */}
          {loading && (
            <p className="empty-chat">
              AI is thinking...
            </p>
          )}
        </div>

        {/* Message Input */}
        <form
          onSubmit={handleSubmit}
          className="input-area"
        >
          <input
            type="text"
            placeholder="Ask about your document..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={!pdfInfo || loading}
          />

          <button
            type="submit"
            disabled={!selectedDocumentId || loading || !message.trim()}
          >
            {loading? "Loading" : "Send"}
          </button>
        </form>

      </section>

      {error && <p className="error">{error}</p>}
    </main>
  );
}

// Main component
export default function App() {
  return (
    <div>
      <nav className="navbar">
        <Link to="/">Home</Link>
        <Link to="/chat">Chat</Link>
        <Link to="/about">About</Link>
      </nav>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/about" element={<About />} />
      </Routes>
    </div>
  );
}
