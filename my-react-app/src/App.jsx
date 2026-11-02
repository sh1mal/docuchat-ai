import { useEffect, useRef, useState } from "react";
import { Routes, Route, Link } from "react-router";
import "./App.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_BASE_URL = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "")
).trim().replace(/\/+$/, "");
const CONFIG_ERROR = API_BASE_URL
  ? ""
  : "The demo is not connected yet. Set VITE_API_URL on the frontend service and rebuild it.";

async function requestApi(path, key, signal, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    signal,
    headers: { ...options.headers, "X-Demo-Key": key },
  });
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    const error = new Error(
      response.status === 401
        ? "The demo key was rejected. Enter the correct key to reconnect."
        : typeof data?.detail === "string"
          ? data.detail
          : `The server is unavailable (${response.status}). A free server may be waking up; try again shortly.`,
    );
    error.status = response.status;
    throw error;
  }
  if (!data || typeof data !== "object") {
    throw new Error("The server returned an unexpected response. Check the backend address or try again after it wakes up.");
  }
  return data;
}

function Home() {
  return <h1>Welcome to DocuChat AI</h1>;
}

function About() {
  return <h1>Chat with your PDF documents using RAG.</h1>;
}

function Chat() {
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [file, setFile] = useState(null);
  const [pdfInfo, setPdfInfo] = useState(null);
  const [error, setError] = useState(CONFIG_ERROR);
  const [showSources, setShowSources] = useState(true);
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [demoKeyInput, setDemoKeyInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [operation, setOperation] = useState("");
  const [storageNotice, setStorageNotice] = useState("");
  const activeKey = useRef("");
  const session = useRef(0);
  const pending = useRef(null);
  const busy = operation !== "";

  useEffect(() => () => {
    session.current += 1;
    pending.current?.abort();
    activeKey.current = "";
  }, []);

  function clearSession() {
    session.current += 1;
    pending.current?.abort();
    pending.current = null;
    activeKey.current = "";
    setConnected(false);
    setDemoKeyInput("");
    setMessages([]);
    setMessage("");
    setFile(null);
    setDocuments([]);
    setStorageNotice("");
    setSelectedDocumentId("");
    setPdfInfo(null);
    setOperation("");
  }

  function applyDocuments(library, preferredId = selectedDocumentId) {
    const { documents: docs, storage } = library;
    if (!Array.isArray(docs)) throw new Error("The server returned an invalid document list.");
    const selected = docs.find(d => d.document_id === preferredId) || docs[0] || null;
    setDocuments(docs);
    setStorageNotice(storage?.mode === "sqlite"
      ? "Temporary demo storage: reupload PDFs after Render restarts."
      : typeof storage?.notice === "string"
        ? storage.notice
        : "Document retention depends on the configured storage service.");
    setSelectedDocumentId(selected?.document_id || "");
    setPdfInfo(selected);
  }

  async function runOperation(name, action, apply) {
    if (pending.current || !API_BASE_URL) return;
    const controller = new AbortController();
    const version = session.current;
    pending.current = controller;
    setOperation(name);
    setError("");
    const timer = setTimeout(() => controller.abort("timeout"), 120000);
    try {
      const result = await action(controller.signal);
      if (session.current === version) apply(result);
    } catch (err) {
      if (session.current !== version) return;
      const errorMessage = controller.signal.aborted
        ? "The request timed out. The free server may be starting; wait a moment and retry."
        : err instanceof TypeError
          ? "Could not reach the backend. It may be waking up; retry shortly. Check the API address and CORS settings if this continues."
          : err.message || "The request failed. Please try again.";
      if (err.status === 401) clearSession();
      setError(errorMessage);
    } finally {
      clearTimeout(timer);
      if (session.current === version) {
        pending.current = null;
        setOperation("");
      }
    }
  }

  async function handleConnect(event) {
    event.preventDefault();
    const key = demoKeyInput.trim();
    if (!key) return;
    await runOperation("connecting", signal => requestApi("/documents", key, signal), data => {
      applyDocuments(data, "");
      activeKey.current = key;
      setConnected(true);
      setDemoKeyInput("");
    });
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!file || !connected || pending.current) return;
    if (file.size > 5 * 1024 * 1024) {
      setError("PDF uploads must be 5 MB or smaller.");
      return;
    }
    const body = new FormData();
    body.append("file", file);
    const key = activeKey.current;
    await runOperation("uploading", async signal => {
      const uploaded = await requestApi("/upload", key, signal, { method: "POST", body });
      const library = await requestApi("/documents", key, signal);
      return { uploaded, library };
    }, ({ uploaded, library }) => {
      applyDocuments(library, uploaded.document_id);
      setMessages([]);
      setMessage("");
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const question = message.trim();
    if (!question || !connected || !selectedDocumentId || pending.current) return;
    setMessages(prev => [...prev, { role: "user", text: question }]);
    setMessage("");
    await runOperation("chatting", signal => requestApi("/chat", activeKey.current, signal, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: question, document_id: selectedDocumentId }),
    }), data => {
      if (typeof data.reply !== "string") throw new Error("The server returned an invalid answer.");
      setMessages(prev => [...prev, {
        role: "bot", text: data.reply,
        sources: Array.isArray(data.sources) ? data.sources : [],
        otherContext: Array.isArray(data.other_context) ? data.other_context : [],
        citationWarning: typeof data.citation_warning === "string" ? data.citation_warning : "",
      }]);
    });
  }

  async function handleRefresh() {
    if (!connected) return;
    await runOperation("refreshing", signal => requestApi("/documents", activeKey.current, signal), data => {
      applyDocuments(data);
      if (!data.documents.some(doc => doc.document_id === selectedDocumentId)) setMessages([]);
    });
  }

  function handleSelectDocument(doc) {
    if (pending.current) return;
    setSelectedDocumentId(doc.document_id);
    setPdfInfo(doc);
    setMessages([]);
    setMessage("");
  }

  async function handleDeleteDocument(documentId) {
    if (!connected || pending.current || !window.confirm("Delete this PDF from the shared demo library?")) return;
    const key = activeKey.current;
    await runOperation("deleting", async signal => {
      await requestApi(`/documents/${encodeURIComponent(documentId)}`, key, signal, { method: "DELETE" });
      return requestApi("/documents", key, signal);
    }, data => {
      applyDocuments(data);
      setMessages([]);
      setMessage("");
    });
  }

  return (
    <main className="chat-app">
      <h1>DocuChat AI</h1>
      <p>Ask questions about your PDF documents</p>

      <section className="demo-access" aria-labelledby="demo-access-heading">
        <h3 id="demo-access-heading">Demo access</h3>
        {connected ? (
          <div className="access-row">
            <span className="success">Connected to the shared demo library</span>
            <button type="button" onClick={() => { clearSession(); setError(CONFIG_ERROR); }}>Lock demo</button>
          </div>
        ) : (
          <form onSubmit={handleConnect}>
            <label htmlFor="demo-key">Demo key</label>
            <input id="demo-key" type="password" autoComplete="off" value={demoKeyInput}
              onChange={event => setDemoKeyInput(event.target.value)} disabled={busy || !API_BASE_URL} required />
            <button disabled={busy || !demoKeyInput.trim() || !API_BASE_URL}>
              {operation === "connecting" ? "Connecting..." : "Unlock demo"}
            </button>
          </form>
        )}
        <p className="access-note">The key stays in this page's memory. Everyone with the key shares this library. Use sample PDFs only; extracted text is sent to the configured AI and storage services.</p>
        <p className="access-note">The free server can take a minute to wake up.</p>
        {storageNotice && <p className="access-note" role="status">{storageNotice}</p>}
      </section>

      {error && <p className="error" role="alert">{error}</p>}

      <section className="upload-box">
        <h3>Upload Document</h3>
        <form onSubmit={handleUpload}>
          <input key={connected ? "unlocked" : "locked"} type="file" accept=".pdf,application/pdf" aria-label="PDF to upload"
            disabled={!connected || busy} onChange={event => setFile(event.target.files?.[0] ?? null)} />
          <button disabled={!connected || !file || busy}>{operation === "uploading" ? "Processing..." : "Upload"}</button>
        </form>
        {pdfInfo && <p className="success">✓ {pdfInfo.filename} — {pdfInfo.chunks} chunks</p>}
      </section>

      <section className="document-library">
        <h3>Saved Documents</h3>
        {documents.length === 0 ? <p>{connected ? "No documents uploaded yet." : "Unlock the demo to view documents."}</p> : documents.map(doc => (
          <div key={doc.document_id} className="document-item">
            <button type="button" className="document-select" disabled={busy}
              onClick={() => handleSelectDocument(doc)} aria-pressed={selectedDocumentId === doc.document_id}>
              📄 {doc.filename} ({doc.chunks} chunks){selectedDocumentId === doc.document_id && " ✓ Selected"}
            </button>
            <button type="button" disabled={busy} onClick={() => handleDeleteDocument(doc.document_id)}>Delete</button>
          </div>
        ))}
      </section>

      <button onClick={() => setShowSources(prev => !prev)}>{showSources ? "Hide Sources" : "Show Sources"}</button>
      <button disabled={busy || messages.length === 0} onClick={() => setMessages([])}>Clear Chat</button>
      <button disabled={!connected || busy} onClick={handleRefresh}>{operation === "refreshing" ? "Refreshing..." : "Refresh PDF Status"}</button>

      <section className="chat-box">
        <div className="messages" aria-live="polite" aria-busy={operation === "chatting"}>
          {messages.length === 0 && <p className="empty-chat">{selectedDocumentId ? "Ask a question about your selected PDF!" : "Unlock the demo, then upload or select a PDF."}</p>}
          {messages.map((msg, index) => (
            <div key={index} className={`bubble ${msg.role}`}>
              <strong>{msg.role === "user" ? "You" : "AI"}</strong>
              {msg.role === "bot" ? <div className="markdown-content"><ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown></div> : <div>{msg.text}</div>}
              {msg.citationWarning && <p className="access-note" role="status">{msg.citationWarning}</p>}
              {msg.sources?.length > 0 && showSources && (
                <div className="sources">
                  <strong>Sources</strong>
                  {msg.sources.map((source, sourceIndex) => (
                    <details key={sourceIndex}>
                      <summary>Chunk {source.chunk}{source.page ? ` · Page ${source.page}` : ""}</summary>
                      <p>{source.text}</p>
                    </details>
                  ))}
                </div>
              )}
              {msg.otherContext?.length > 0 && showSources && (
                <details className="sources">
                  <summary>Other retrieved context ({msg.otherContext.length})</summary>
                  <p className="access-note">These excerpts were retrieved but were not cited in this answer.</p>
                  {msg.otherContext.map((source, sourceIndex) => (
                    <details key={sourceIndex}>
                      <summary>Chunk {source.chunk}{source.page ? ` · Page ${source.page}` : ""}</summary>
                      <p>{source.text}</p>
                    </details>
                  ))}
                </details>
              )}
            </div>
          ))}
          {operation === "chatting" && <p className="empty-chat">AI is thinking...</p>}
        </div>
        <form onSubmit={handleSubmit} className="input-area">
          <input type="text" aria-label="Question about selected PDF" placeholder="Ask about your document..." value={message}
            onChange={event => setMessage(event.target.value)} disabled={!connected || !pdfInfo || busy} maxLength={4000} />
          <button type="submit" disabled={!connected || !selectedDocumentId || busy || !message.trim()}>{operation === "chatting" ? "Loading..." : "Send"}</button>
        </form>
      </section>
    </main>
  );
}

export default function App() {
  return (
    <div>
      <nav className="navbar"><Link to="/">Home</Link><Link to="/chat">Chat</Link><Link to="/about">About</Link></nav>
      <Routes><Route path="/" element={<Home />} /><Route path="/chat" element={<Chat />} /><Route path="/about" element={<About />} /></Routes>
    </div>
  );
}
