import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import DIMENSIONS, QdrantStore, SQLiteStore


def vector(first=1.0, second=0.0):
    return [first, second] + [0.0] * (DIMENSIONS - 2)


def metadata(document_id="a" * 32, filename="guide.pdf"):
    return {"document_id": document_id, "filename": filename, "pages": 2,
            "characters": 80, "chunks": 2, "embedding_dimensions": DIMENSIONS}


CHUNKS = [{"text": "first page", "chunk": 1, "page": 1},
          {"text": "second page", "chunk": 2, "page": 2}]


class SQLiteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "db.sqlite3"
        self.store = SQLiteStore(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_documents_search_selection_and_reopen(self):
        self.store.add_document(metadata(), CHUNKS, [vector(), vector(0, 1)])
        self.store.add_document(metadata("b" * 32, "other.pdf"), CHUNKS, [vector(), vector()])
        reopened = SQLiteStore(self.path)
        self.assertEqual(len(reopened.list_documents()), 2)
        matches = reopened.search("a" * 32, vector(0, 1), 1)
        self.assertEqual(matches[0]["page"], 2)
        self.assertEqual(matches[0]["filename"], "guide.pdf")
        self.assertAlmostEqual(matches[0]["score"], 1.0)
        self.assertEqual(reopened.search("missing", vector()), [])

    def test_deletion_cascades_without_affecting_other_documents(self):
        self.store.add_document(metadata(), CHUNKS, [vector(), vector()])
        self.store.add_document(metadata("b" * 32), CHUNKS, [vector(), vector()])
        self.assertTrue(self.store.delete_document("a" * 32))
        self.assertFalse(self.store.delete_document("a" * 32))
        self.assertIsNone(self.store.get_document("a" * 32))
        self.assertIsNotNone(self.store.get_document("b" * 32))
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0], 2)

    def test_insert_is_atomic(self):
        bad_chunks = [CHUNKS[0], {"text": None, "chunk": 2, "page": 2}]
        with self.assertRaises(HTTPException):
            self.store.add_document(metadata(), bad_chunks, [vector(), vector()])
        self.assertEqual(self.store.list_documents(), [])
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0], 0)

    def test_bad_embeddings_rejected_before_insert(self):
        for bad in ([0.0] * DIMENSIONS, vector(float("nan")), [1.0]):
            with self.assertRaises(ValueError):
                self.store.add_document(metadata(), CHUNKS, [vector(), bad])
        self.assertEqual(self.store.list_documents(), [])


class QdrantTests(unittest.TestCase):
    def make_store(self, handler):
        return QdrantStore("https://example.qdrant.io", "test-secret", "docuchat_test",
                           transport=httpx.MockTransport(handler))

    @staticmethod
    def collection():
        return {"config": {"params": {"vectors": {"size": DIMENSIONS, "distance": "Cosine"}}},
                "payload_schema": {"type": {"data_type": "keyword"},
                                   "document_id": {"data_type": "keyword"}}}

    def test_manifest_published_after_chunks(self):
        writes = []
        def handler(request):
            if request.method == "GET":
                return httpx.Response(200, json={"result": self.collection()})
            writes.append(json.loads(request.content))
            return httpx.Response(200, json={"result": {"status": "completed"}})
        store = self.make_store(handler)
        store.add_document(metadata(), CHUNKS, [vector(), vector()])
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0]["points"][0]["payload"]["type"], "chunk")
        self.assertEqual(writes[1]["points"][0]["payload"]["type"], "document")
        self.assertEqual(writes[1]["points"][0]["payload"]["chunks"], 2)

    def test_failed_insert_cleans_up_and_sanitizes_error(self):
        paths = []
        def handler(request):
            paths.append(str(request.url))
            if request.method == "GET":
                return httpx.Response(200, json={"result": self.collection()})
            if request.method == "PUT":
                return httpx.Response(500, text="test-secret internal error")
            return httpx.Response(200, json={"result": {"status": "completed"}})
        with self.assertRaises(HTTPException) as error:
            self.make_store(handler).add_document(metadata(), CHUNKS, [vector(), vector()])
        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("test-secret", error.exception.detail)
        self.assertTrue(paths[-1].endswith("/points/delete?wait=true"))

    def test_query_filters_by_selected_document_and_chunk(self):
        body = {}
        def handler(request):
            if request.url.path.endswith("/points/query"):
                body.update(json.loads(request.content))
                return httpx.Response(200, json={"result": {"points": [{
                    "payload": {**CHUNKS[0], "filename": "guide.pdf"}, "score": 0.9}]}})
            result = self.collection() if "/points/" not in request.url.path else {
                "payload": {**metadata(), "type": "document"}}
            return httpx.Response(200, json={"result": result})
        matches = self.make_store(handler).search("a" * 32, vector())
        self.assertEqual(matches[0]["score"], 0.9)
        self.assertEqual(body["filter"]["must"], [
            {"key": "document_id", "match": {"value": "a" * 32}},
            {"key": "type", "match": {"value": "chunk"}},
        ])

    def test_collection_dimension_mismatch_fails(self):
        config = self.collection()
        config["config"]["params"]["vectors"]["size"] = 384
        store = self.make_store(lambda request: httpx.Response(200, json={"result": config}))
        with self.assertRaises(HTTPException):
            store.list_documents()

    def test_collection_creation_and_payload_indexes(self):
        calls = []
        def handler(request):
            calls.append((request.method, request.url.path, json.loads(request.content) if request.content else None))
            if request.method == "GET":
                if len(calls) == 1:
                    return httpx.Response(404, json={"status": {"error": "missing"}})
                config = self.collection()
                config["payload_schema"] = {}
                return httpx.Response(200, json={"result": config})
            if request.url.path.endswith("/scroll"):
                return httpx.Response(200, json={"result": {"points": [], "next_page_offset": None}})
            return httpx.Response(200, json={"result": True})
        self.assertEqual(self.make_store(handler).list_documents(), [])
        self.assertEqual(calls[1][2], {"vectors": {"size": DIMENSIONS, "distance": "Cosine"}})
        self.assertEqual([body["field_name"] for method, path, body in calls if path.endswith("/index")],
                         ["type", "document_id"])

    def test_list_paginates_remote_metadata_only(self):
        bodies = []
        def handler(request):
            if request.method == "GET":
                return httpx.Response(200, json={"result": self.collection()})
            body = json.loads(request.content)
            bodies.append(body)
            more = "offset" not in body
            return httpx.Response(200, json={"result": {
                "points": [{"payload": metadata("a" * 32 if more else "b" * 32)}],
                "next_page_offset": "next-manifest" if more else None}})
        self.assertEqual(len(self.make_store(handler).list_documents()), 2)
        self.assertNotIn("text", bodies[0]["with_payload"])
        self.assertEqual(bodies[1]["offset"], "next-manifest")

    def test_delete_removes_chunks_before_manifest(self):
        bodies = []
        def handler(request):
            if request.method == "GET":
                result = self.collection() if "/points/" not in request.url.path else {
                    "payload": {**metadata(), "type": "document"}}
                return httpx.Response(200, json={"result": result})
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"result": {"status": "completed"}})
        self.assertTrue(self.make_store(handler).delete_document("a" * 32))
        self.assertEqual(bodies[0]["filter"]["must"][-1], {"key": "type", "match": {"value": "chunk"}})
        self.assertIn("points", bodies[1])

    def test_render_rejects_local_and_credential_urls(self):
        with patch.dict("os.environ", {"RENDER": "true"}):
            for url in ("http://127.0.0.1:6333", "https://127.0.0.1", "https://user:pass@example.com"):
                with self.assertRaises(HTTPException):
                    QdrantStore(url, "test-secret", "collection")

    def test_absent_manifest_prevents_orphan_search(self):
        queried = []
        def handler(request):
            queried.append(request.url.path)
            if "/points/" in request.url.path:
                return httpx.Response(404, json={"status": {"error": "missing"}})
            return httpx.Response(200, json={"result": self.collection()})
        self.assertEqual(self.make_store(handler).search("a" * 32, vector()), [])
        self.assertFalse(any(path.endswith("/query") for path in queried))


if __name__ == "__main__":
    unittest.main()
