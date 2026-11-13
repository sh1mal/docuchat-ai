import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import samples from "./data/samples.json";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_BASE_URL = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "")
).trim().replace(/\/+$/, "");
const CONFIG_ERROR = API_BASE_URL
  ? ""
  : "The demo is not connected yet. Set VITE_API_URL on the frontend service and rebuild it.";

async function requestApi(path, signal, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    signal,
  });
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    const error = new Error(
      typeof data?.detail === "string"
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

function Icon({ name, size = 20, ...props }) {
  const paths = {
    file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h5",
    upload: "M12 16V3 M7 8l5-5 5 5 M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4",
    arrow: "M12 19V5 M5 12l7-7 7 7",
    refresh: "M20 7v5h-5 M4 17v-5h5 M6 7a7 7 0 0 1 12-2l2 7 M4 12l2 7a7 7 0 0 0 12-2",
    trash: "M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7",
    sparkle: "M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z",
    check: "M5 12l4 4L19 6",
    book: "M12 6v15 M12 6C9 3 5 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 2z",
    moon: "M21 12.8A9 9 0 0 1 11.2 3a9 9 0 1 0 9.8 9.8Z",
    sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1.5 1.5 M17.5 17.5L19 19 M5 19l1.5-1.5 M17.5 6.5L19 5",
    chevron: "M8 5l7 7-7 7",
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d={paths[name] || paths.file} /></svg>;
}

function Chat() {
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem("docuchat-theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch { /* Theme switching still works when storage is unavailable. */ }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#171c19" : "#ffffff");
    try { localStorage.setItem("docuchat-theme", theme); } catch { /* Storage is optional. */ }
  }, [theme]);
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [file, setFile] = useState(null);
  const [pdfInfo, setPdfInfo] = useState(null);
  const [error, setError] = useState(CONFIG_ERROR);
  const [showSources, setShowSources] = useState(true);
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [operation, setOperation] = useState(API_BASE_URL ? "connecting" : "");
  const [storageNotice, setStorageNotice] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef(null);
  const questionInput = useRef(null);
  const messagesEnd = useRef(null);
  const session = useRef(0);
  const pending = useRef(null);
  const busy = operation !== "";

  const applyDocuments = useCallback((library, preferredId = "") => {
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
  }, []);

  useEffect(() => {
    if (!API_BASE_URL) return;
    const controller = new AbortController();
    pending.current = controller;
    const timer = setTimeout(() => controller.abort(), 120000);
    requestApi("/documents", controller.signal)
      .then(data => {
        if (!controller.signal.aborted) applyDocuments(data);
      })
      .catch(err => {
        if (pending.current === controller) {
          setError(controller.signal.aborted
            ? "The server took too long to respond. Use Refresh library to retry."
            : `${err.message} Use Refresh library to retry.`);
        }
      })
      .finally(() => {
        clearTimeout(timer);
        if (pending.current === controller) {
          pending.current = null;
          setOperation("");
        }
      });
    return () => {
      session.current += 1;
      pending.current = null;
      controller.abort();
      clearTimeout(timer);
    };
  }, [applyDocuments]);

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
      setError(errorMessage);
    } finally {
      clearTimeout(timer);
      if (session.current === version) {
        pending.current = null;
        setOperation("");
      }
    }
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!file || !API_BASE_URL || pending.current) return;
    if (file.size > 5 * 1024 * 1024) {
      setError("PDF uploads must be 5 MB or smaller.");
      return;
    }
    const body = new FormData();
    body.append("file", file);
    await runOperation("uploading", async signal => {
      const uploaded = await requestApi("/upload", signal, { method: "POST", body });
      const library = await requestApi("/documents", signal);
      return { uploaded, library };
    }, ({ uploaded, library }) => {
      applyDocuments(library, uploaded.document_id);
      setMessages([]);
      setMessage("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
    });
  }

  async function handleUseSample(sample) {
    if (pending.current || !API_BASE_URL) return;
    const existing = documents.find(doc => doc.filename === sample.filename);
    if (existing) {
      handleSelectDocument(existing);
      setError("");
      return;
    }
    await runOperation("uploading", async signal => {
      const response = await fetch(sample.url, { signal });
      if (!response.ok) throw new Error("Could not load the sample PDF. Please retry.");
      const blob = await response.blob();
      const body = new FormData();
      body.append("file", blob, sample.filename);
      const uploaded = await requestApi("/upload", signal, { method: "POST", body });
      const library = await requestApi("/documents", signal);
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
    if (!question || !API_BASE_URL || !selectedDocumentId || pending.current) return;
    setMessages(prev => [...prev, { role: "user", text: question }]);
    setMessage("");
    await runOperation("chatting", signal => requestApi("/chat", signal, {
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
    if (!API_BASE_URL) return;
    await runOperation("refreshing", signal => requestApi("/documents", signal), data => {
      applyDocuments(data, selectedDocumentId);
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
    if (!API_BASE_URL || pending.current || !window.confirm("Delete this PDF from the shared demo library?")) return;
    await runOperation("deleting", async signal => {
      await requestApi(`/documents/${encodeURIComponent(documentId)}`, signal, { method: "DELETE" });
      return requestApi("/documents", signal);
    }, data => {
      applyDocuments(data, selectedDocumentId);
      setMessages([]);
      setMessage("");
    });
  }

  useEffect(() => {
    if (messages.length > 0) messagesEnd.current?.scrollIntoView({ block: "nearest" });
  }, [messages, operation]);

  function chooseFile(selected) {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF document.");
      return;
    }
    if (selected.size > 5 * 1024 * 1024) {
      setError("PDF uploads must be 5 MB or smaller.");
      return;
    }
    setError("");
    setFile(selected);
  }

  const selectedSample = samples.find(sample => sample.filename === pdfInfo?.filename);

  return (
    <div className="workspace">
      <aside className="sidebar" aria-label="Document library">
        <a className="brand" href="/" aria-label="DocuChat workspace"><span className="brand-mark"><Icon name="book" size={23} /></span><span>DocuChat AI</span></a>

        <form className="upload-form" onSubmit={handleUpload}>
          <label className={`upload-zone ${dragging ? "dragging" : ""} ${busy || !API_BASE_URL ? "disabled" : ""}`}
            onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={event => { event.preventDefault(); setDragging(false); if (!busy && API_BASE_URL) chooseFile(event.dataTransfer.files[0]); }}>
            <input ref={fileInput} className="file-input" type="file" accept=".pdf,application/pdf" aria-label="Choose a PDF"
              disabled={!API_BASE_URL || busy} onChange={event => chooseFile(event.target.files?.[0])} />
            <strong>{file ? file.name : "Upload PDF"}</strong>
            <span>{file ? `${(file.size / 1024).toFixed(0)} KB · Ready to upload` : "Drop a file or click to browse"}</span>
            <small>Text PDFs · 5 MB max</small>
          </label>
          {file && <button className="upload-submit" disabled={busy || !API_BASE_URL}><Icon name="upload" size={16} />{operation === "uploading" ? "Uploading…" : "Upload document"}</button>}
        </form>
        <section className="sample-library" aria-label="Sample PDFs">
          <h2>Samples <span>10 pages each</span></h2>
          {samples.map(sample => <div className="sample-item" key={sample.id}>
            <a href={sample.url} download={sample.filename} title={`Download ${sample.title} PDF`}>{sample.title}</a>
            <button type="button" disabled={busy || !API_BASE_URL} onClick={() => handleUseSample(sample)} aria-label={`Use ${sample.title} sample`}>Use</button>
          </div>)}
        </section>
        <div className="library-heading"><h2>Documents <span>{documents.length}</span></h2><button className="icon-button" onClick={handleRefresh} disabled={busy || !API_BASE_URL} aria-label="Refresh library" title="Refresh library"><Icon name="refresh" size={17} /></button></div>
        <div className="document-list" aria-busy={operation === "connecting" || operation === "refreshing"}>
          {documents.length === 0 ? <div className="library-empty"><p>{operation === "connecting" ? "Loading documents…" : "No documents uploaded."}</p></div> : documents.map(doc => (
            <div className={`document-item ${selectedDocumentId === doc.document_id ? "selected" : ""}`} key={doc.document_id}>
              <button className="document-select" disabled={busy} onClick={() => handleSelectDocument(doc)} aria-pressed={selectedDocumentId === doc.document_id}>
                <span className="document-icon"><Icon name="file" size={19} /></span><span className="document-name"><strong>{doc.filename}</strong><small>{doc.pages ? `${doc.pages} pages · ` : ""}{doc.chunks} excerpts</small></span>
              </button>
              <button className="icon-button delete-button" disabled={busy} onClick={() => handleDeleteDocument(doc.document_id)} aria-label={`Delete ${doc.filename}`} title="Delete document"><Icon name="trash" size={15} /></button>
            </div>
          ))}
        </div>
        <p className="sidebar-footer">Shared library. Use sample PDFs only.</p>
      </aside>

      <main className="main-panel">
        <header className="workspace-header"><div><h1>{pdfInfo ? pdfInfo.filename : "PDF chat"}</h1>{busy && <span className="operation-status" role="status">{operation === "connecting" ? "Connecting… The server may take a minute to start." : operation === "uploading" ? "Processing PDF…" : operation === "chatting" ? "Generating answer…" : "Updating library…"}</span>}</div><div className="header-actions"><button className="theme-toggle" type="button" aria-label="Dark mode" aria-pressed={theme === "dark"} title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} onClick={() => setTheme(previous => previous === "dark" ? "light" : "dark")}><Icon name={theme === "dark" ? "sun" : "moon"} size={17} /><span className="sr-only">Dark mode</span></button><button className="text-button" aria-pressed={showSources} onClick={() => setShowSources(prev => !prev)}>Sources {showSources ? "on" : "off"}</button><button className="text-button" disabled={busy || messages.length === 0} onClick={() => setMessages([])}>Clear chat</button></div></header>
        {error && <div className="error" role="alert"><span>{error}</span></div>}
        <section className="conversation" aria-label="Chat with your document">
          <div className="messages" aria-live="polite" aria-busy={operation === "chatting"}>
            {messages.length === 0 && <div className="empty-chat"><Icon name="file" size={27} /><h2>{pdfInfo ? "Ask a question" : "Chat with a PDF"}</h2><p>{pdfInfo ? "Answers include references to your document." : "Upload a PDF, then ask a question."}</p></div>}
            {messages.map((msg, index) => <article key={index} className={`message ${msg.role}`}>
              <span className={`avatar ${msg.role}`}>{msg.role === "user" ? "Y" : <Icon name="sparkle" size={17} />}</span>
              <div className="message-body"><span className="message-author">{msg.role === "user" ? "You" : "DocuChat"}</span>
                {msg.role === "bot" ? <div className="markdown-content"><ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown></div> : <p className="user-text">{msg.text}</p>}
                {msg.citationWarning && <p className="citation-warning" role="status">{msg.citationWarning}</p>}
                {msg.sources?.length > 0 && showSources && <div className="sources"><span className="sources-label"><Icon name="check" size={13} /> Cited excerpts · {msg.sources.length}</span>{msg.sources.map((source, sourceIndex) => <details key={sourceIndex}><summary>{source.filename || pdfInfo?.filename} <span>Page {source.page} · Excerpt {source.chunk}</span></summary><p>{source.text}</p></details>)}</div>}
                {msg.otherContext?.length > 0 && showSources && <details className="other-context"><summary>Other retrieved context ({msg.otherContext.length})</summary><p>These excerpts were retrieved but were not cited in this answer.</p>{msg.otherContext.map((source, sourceIndex) => <details key={sourceIndex}><summary>Page {source.page} · Excerpt {source.chunk}</summary><p>{source.text}</p></details>)}</details>}
              </div>
            </article>)}
            {operation === "chatting" && <div className="thinking" role="status"><Icon name="sparkle" size={17} /><span>Generating answer…</span><span className="thinking-dots">•••</span></div>}
            <div ref={messagesEnd} />
          </div>
          <div className="composer-area"><form onSubmit={handleSubmit} className="composer"><label className="sr-only" htmlFor="question">Question about selected PDF</label><input ref={questionInput} id="question" type="text" placeholder={pdfInfo ? (selectedSample?.question || "e.g. What are the main points of this document?") : "Upload a PDF or choose a sample…"} value={message} onChange={event => setMessage(event.target.value)} disabled={!API_BASE_URL || !pdfInfo || busy} maxLength={2000} /><button aria-label="Send question" type="submit" disabled={!API_BASE_URL || !selectedDocumentId || busy || !message.trim()}><Icon name="arrow" size={20} /></button></form><div className="composer-caption"><span>Answers from your document. Always check the sources.</span></div></div>
        </section>
        <footer className="workspace-footer"><span>Gemini · PDF Q&A</span><details className="about-details"><summary>Project info</summary><div><h2>About DocuChat</h2><p>A React and FastAPI RAG application using Gemini and document search. Expand sources to check page references; answers may be incorrect.</p><p>All visitors can read and delete uploaded documents. Text is sent to Google and the configured storage service. Original PDFs and chat history are not saved. Scanned PDFs need OCR.</p>{storageNotice && <p>{storageNotice}</p>}</div></details></footer>
      </main>
    </div>
  );
}

export default function App() {
  return <Chat />;
}
