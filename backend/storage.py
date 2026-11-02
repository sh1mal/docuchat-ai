"""Small vector stores: SQLite for demos, optional Qdrant for remote storage.

SQLite files on Render Free are ephemeral. Qdrant retains chunk text and metadata
outside Render; its own free-tier inactivity/deletion policy still applies.
"""
from contextlib import contextmanager
from functools import lru_cache
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

import httpx
from fastapi import HTTPException

DIMENSIONS = 768
MODEL = "gemini-embedding-001"
METADATA_KEYS = (
    "document_id", "filename", "pages", "characters", "chunks",
    "embedding_dimensions", "embedding_model",
)


def _unavailable():
    return HTTPException(503, "Document storage unavailable. Check server configuration and try again.")


def _vector(values):
    if len(values) != DIMENSIONS:
        raise ValueError("Unexpected embedding dimensions")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise ValueError("Invalid embedding")
    if not any(result):
        raise ValueError("Empty embedding")
    return result


def _prepare(metadata, chunks, vectors):
    if not chunks or len(chunks) != len(vectors):
        raise ValueError("Chunks and embeddings must align")
    metadata = {key: metadata[key] for key in METADATA_KEYS if key in metadata}
    if not metadata.get("document_id") or not metadata.get("filename"):
        raise ValueError("Document metadata is incomplete")
    if metadata.get("embedding_dimensions", DIMENSIONS) != DIMENSIONS:
        raise ValueError("Unexpected embedding dimensions")
    metadata["embedding_dimensions"] = DIMENSIONS
    metadata["embedding_model"] = MODEL
    metadata["chunks"] = len(chunks)
    return metadata, [_vector(vector) for vector in vectors]


class SQLiteStore:
    def __init__(self, path):
        self.path = str(path)
        try:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.executescript("""
                    CREATE TABLE IF NOT EXISTS documents (
                        document_id TEXT PRIMARY KEY, metadata TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS chunks (
                        id INTEGER PRIMARY KEY,
                        document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                        text TEXT NOT NULL, chunk INTEGER NOT NULL, page INTEGER NOT NULL,
                        vector TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
                """)
        except (OSError, sqlite3.Error):
            raise _unavailable() from None

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                yield connection
        finally:
            connection.close()

    def list_documents(self):
        try:
            with self._connect() as connection:
                return [json.loads(row[0]) for row in connection.execute(
                    "SELECT metadata FROM documents ORDER BY rowid DESC"
                )]
        except (sqlite3.Error, ValueError):
            raise _unavailable() from None

    def get_document(self, document_id):
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT metadata FROM documents WHERE document_id=?", (document_id,)
                ).fetchone()
            return json.loads(row[0]) if row else None
        except (sqlite3.Error, ValueError):
            raise _unavailable() from None

    def add_document(self, metadata, chunks, vectors):
        metadata, vectors = _prepare(metadata, chunks, vectors)
        try:
            with self._connect() as connection:
                connection.execute("INSERT INTO documents VALUES (?, ?)", (
                    metadata["document_id"], json.dumps(metadata, allow_nan=False)
                ))
                connection.executemany(
                    "INSERT INTO chunks(document_id,text,chunk,page,vector) VALUES(?,?,?,?,?)",
                    [(metadata["document_id"], chunk["text"], chunk["chunk"], chunk["page"],
                      json.dumps(vector, allow_nan=False)) for chunk, vector in zip(chunks, vectors)],
                )
        except sqlite3.Error:
            raise _unavailable() from None

    def search(self, document_id, vector, limit=3):
        vector = _vector(vector)
        metadata = self.get_document(document_id)
        if not metadata:
            return []
        query_norm = math.sqrt(sum(value * value for value in vector))
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT text,chunk,page,vector FROM chunks WHERE document_id=?", (document_id,)
                ).fetchall()
            matches = []
            for text, chunk, page, stored in rows:
                candidate = json.loads(stored)
                norm = math.sqrt(sum(value * value for value in candidate))
                score = sum(a * b for a, b in zip(vector, candidate)) / (query_norm * norm)
                matches.append({"text": text, "chunk": chunk, "page": page,
                                "filename": metadata["filename"], "score": max(-1.0, min(1.0, score))})
            return sorted(matches, key=lambda item: item["score"], reverse=True)[:limit]
        except (sqlite3.Error, ValueError, ZeroDivisionError, TypeError):
            raise _unavailable() from None

    def delete_document(self, document_id):
        try:
            with self._connect() as connection:
                result = connection.execute("DELETE FROM documents WHERE document_id=?", (document_id,))
                return bool(result.rowcount)
        except sqlite3.Error:
            raise _unavailable() from None


class QdrantStore:
    def __init__(self, url, api_key, collection, transport=None):
        try:
            parsed = urlsplit(url)
        except ValueError:
            raise _unavailable() from None
        hostname = parsed.hostname or ""
        try:
            private_host = not ipaddress.ip_address(hostname).is_global
        except ValueError:
            private_host = hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local")
        local_http = os.getenv("RENDER") != "true" and private_host and parsed.scheme == "http"
        if (not hostname or (parsed.scheme != "https" and not local_http)
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"} or not api_key
                or (os.getenv("RENDER") == "true" and private_host)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", collection)):
            raise _unavailable()
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.collection = collection
        self.transport = transport
        self.ready = False

    def _request(self, method, path, body=None, allow_missing=False, allow_conflict=False):
        try:
            with httpx.Client(timeout=30, trust_env=False, follow_redirects=False,
                              transport=self.transport) as client:
                response = client.request(method, self.url + path,
                                          headers={"api-key": self.api_key}, json=body)
            if allow_missing and response.status_code == 404:
                return None
            if allow_conflict and response.status_code == 409:
                return None
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or "result" not in data:
                raise ValueError("Unexpected storage response")
            return data["result"]
        except (httpx.HTTPError, ValueError, TypeError):
            raise _unavailable() from None

    @property
    def _base(self):
        return f"/collections/{self.collection}"

    def _ensure(self):
        if self.ready:
            return
        config = self._request("GET", self._base, allow_missing=True)
        if config is None:
            self._request("PUT", self._base, {"vectors": {"size": DIMENSIONS, "distance": "Cosine"}},
                          allow_conflict=True)
            config = self._request("GET", self._base)
        try:
            vectors = config["config"]["params"]["vectors"]
            if vectors.get("size") != DIMENSIONS or vectors.get("distance", "").lower() != "cosine":
                raise ValueError("Embedding collection mismatch")
            for field in ("type", "document_id"):
                if field not in config.get("payload_schema", {}):
                    self._request("PUT", self._base + "/index?wait=true",
                                  {"field_name": field, "field_schema": "keyword"})
        except (KeyError, TypeError, AttributeError, ValueError):
            raise _unavailable() from None
        self.ready = True

    @staticmethod
    def _manifest_id(document_id):
        return str(uuid5(NAMESPACE_URL, "docuchat:document:" + document_id))

    @staticmethod
    def _filter(document_id, kind=None):
        must = [{"key": "document_id", "match": {"value": document_id}}]
        if kind:
            must.append({"key": "type", "match": {"value": kind}})
        return {"must": must}

    def list_documents(self):
        self._ensure()
        body = {"filter": {"must": [{"key": "type", "match": {"value": "document"}}]},
                "limit": 100, "with_payload": list(METADATA_KEYS), "with_vector": False}
        documents = []
        try:
            while True:
                result = self._request("POST", self._base + "/points/scroll", body)
                documents.extend(point["payload"] for point in result["points"])
                if not result.get("next_page_offset"):
                    return documents
                body["offset"] = result["next_page_offset"]
                if len(documents) > 2000:
                    raise ValueError("Document library exceeds demo limits")
        except (KeyError, TypeError, ValueError):
            raise _unavailable() from None

    def get_document(self, document_id):
        self._ensure()
        result = self._request("GET", self._base + "/points/" + self._manifest_id(document_id),
                               allow_missing=True)
        if result is None:
            return None
        try:
            payload = result["payload"]
            if payload["type"] != "document" or payload["document_id"] != document_id:
                raise ValueError("Unexpected document manifest")
            return {key: payload[key] for key in METADATA_KEYS if key in payload}
        except (KeyError, TypeError, ValueError):
            raise _unavailable() from None

    def add_document(self, metadata, chunks, vectors):
        metadata, vectors = _prepare(metadata, chunks, vectors)
        self._ensure()
        document_id = metadata["document_id"]
        try:
            for start in range(0, len(chunks), 32):
                points = []
                for index in range(start, min(start + 32, len(chunks))):
                    chunk = chunks[index]
                    points.append({"id": str(uuid5(NAMESPACE_URL, f"docuchat:{document_id}:{index}")),
                                   "vector": vectors[index],
                                   "payload": {"type": "chunk", "document_id": document_id,
                                               "filename": metadata["filename"], "text": chunk["text"],
                                               "chunk": chunk["chunk"], "page": chunk["page"]}})
                self._request("PUT", self._base + "/points?wait=true", {"points": points})
            # Publish only after all chunks have been acknowledged. The nonzero
            # manifest vector is excluded from all retrieval searches by type.
            self._request("PUT", self._base + "/points?wait=true", {"points": [{
                "id": self._manifest_id(document_id), "vector": [1.0] + [0.0] * (DIMENSIONS - 1),
                "payload": {**metadata, "type": "document"},
            }]})
        except Exception:
            # Best effort cleanup. A failed upload has no visible manifest, so
            # list/search cannot expose any orphan chunks if cleanup also fails.
            try:
                self._request("POST", self._base + "/points/delete?wait=true",
                              {"filter": self._filter(document_id)})
            except HTTPException:
                pass
            raise

    def search(self, document_id, vector, limit=3):
        vector = _vector(vector)
        metadata = self.get_document(document_id)
        if not metadata:
            return []
        result = self._request("POST", self._base + "/points/query", {
            "query": vector, "filter": self._filter(document_id, "chunk"),
            "limit": limit, "with_payload": ["text", "chunk", "page", "filename"], "with_vector": False,
        })
        try:
            return [{**point["payload"], "score": point["score"]} for point in result["points"]]
        except (KeyError, TypeError):
            raise _unavailable() from None

    def delete_document(self, document_id):
        if not self.get_document(document_id):
            return False
        # Preserve the manifest if chunk deletion fails, allowing a safe retry.
        self._request("POST", self._base + "/points/delete?wait=true",
                      {"filter": self._filter(document_id, "chunk")})
        self._request("POST", self._base + "/points/delete?wait=true",
                      {"points": [self._manifest_id(document_id)]})
        return True


@lru_cache(maxsize=1)
def get_store():
    default_kind = "qdrant" if os.getenv("RENDER") == "true" else "sqlite"
    kind = os.getenv("VECTOR_STORE", default_kind).strip().lower()
    if kind == "sqlite":
        default = Path(__file__).resolve().parent / "data" / "docuchat.sqlite3"
        return SQLiteStore(os.getenv("SQLITE_PATH", str(default)))
    if kind == "qdrant":
        return QdrantStore(os.getenv("QDRANT_URL", ""), os.getenv("QDRANT_API_KEY", ""),
                           os.getenv("QDRANT_COLLECTION", "docuchat_gemini_768"))
    raise _unavailable()
