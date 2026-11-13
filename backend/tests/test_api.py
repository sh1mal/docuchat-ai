"""Offline API acceptance tests: real PDF extraction and isolated SQLite storage."""
from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

with patch.dict(os.environ, {"FRONTEND_ORIGIN": "https://docuchat-ai-frontend.onrender.com"}):
    import main
from storage import DIMENSIONS, SQLiteStore, get_store


def pdf_bytes(*pages, encrypted=False):
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                     NameObject("/Subtype"): NameObject("/Type1"),
                                     NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
            stream = DecodedStreamObject()
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream.set_data(f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("dummy-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def fake_embeddings(texts, task_type):
    return [[1.0] + [0.0] * (DIMENSIONS - 1) for _ in texts]


class APITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.directory.name) / "test.sqlite3")
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "offline-gemini-secret",
                                          "VECTOR_STORE": "sqlite", "SQLITE_PATH": self.db_path})
        self.env.start()
        get_store.cache_clear()
        self.client = TestClient(main.app)
        self.embed_patch = patch("main.embed_texts", side_effect=fake_embeddings)
        self.embed_mock = self.embed_patch.start()
        self.answer_patch = patch("main.generate_answer", side_effect=lambda question, matches:
                                  f"{matches[0]['text']} [Chunk {matches[0]['chunk']}, page {matches[0]['page']}]")
        self.answer_mock = self.answer_patch.start()

    def tearDown(self):
        self.client.close()
        self.answer_patch.stop()
        self.embed_patch.stop()
        get_store.cache_clear()
        self.env.stop()
        self.directory.cleanup()

    def upload(self, filename="alpha.pdf", content=None):
        return self.client.post("/upload",
                                files={"file": (filename, content if content is not None else pdf_bytes("Alpha is blue."),
                                                "application/pdf")})

    def test_two_document_lifecycle_and_sources(self):
        first = self.upload("alpha.pdf", pdf_bytes("Alpha is blue.", "Alpha launched in 2020."))
        second = self.upload("beta.pdf", pdf_bytes("Beta is green."))
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        first_id, second_id = first.json()["document_id"], second.json()["document_id"]
        self.assertNotEqual(first_id, second_id)
        library = self.client.get("/documents").json()
        self.assertEqual(len(library["documents"]), 2)
        self.assertEqual(library["storage"]["mode"], "sqlite")
        self.assertIn("Temporary", library["storage"]["notice"])
        self.assertEqual(len(SQLiteStore(self.db_path).list_documents()), 2)

        first_chat = self.client.post("/chat",
                                json={"message": "What is Alpha?", "document_id": first_id})
        self.assertEqual(first_chat.status_code, 200, first_chat.text)
        self.assertTrue(first_chat.json()["sources"])
        self.assertEqual({s["filename"] for s in first_chat.json()["sources"]}, {"alpha.pdf"})
        self.assertEqual({s["page"] for s in first_chat.json()["sources"]}, {1})
        self.assertEqual({s["page"] for s in first_chat.json()["other_context"]}, {2})
        self.assertEqual(first_chat.json()["citation_warning"], "")
        self.assertIn("[Chunk", first_chat.json()["reply"])
        self.assertTrue(all("Beta" not in s["text"] for s in first_chat.json()["sources"]))
        beta_search = self.client.post("/search",
                                json={"question": "What is Beta?", "document_id": second_id})
        self.assertEqual(beta_search.status_code, 200, beta_search.text)
        self.assertEqual(beta_search.json()["filename"], "beta.pdf")
        self.assertTrue(all("Beta" in s["text"] for s in beta_search.json()["matches"]))
        deleted = self.client.delete(f"/documents/{first_id}")
        self.assertEqual(deleted.status_code, 200)
        remaining = self.client.get("/documents").json()["documents"]
        self.assertEqual([d["document_id"] for d in remaining], [second_id])
        self.assertEqual(self.client.post("/chat",
                                json={"message": "Alpha?", "document_id": first_id}).status_code, 404)
        self.assertEqual(self.client.delete(f"/documents/{first_id}").status_code, 404)
        # Exactly one embedding call per question; no duplicate retrieval/API spending.
        self.assertEqual(sum(c.args[1] == "RETRIEVAL_QUERY" for c in self.embed_mock.call_args_list), 2)

    def test_public_document_lifecycle_needs_no_key(self):
        uploaded = self.upload()
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        document_id = uploaded.json()["document_id"]
        self.assertEqual(len(self.client.get("/documents").json()["documents"]), 1)
        for path, field in (("/chat", "message"), ("/search", "question")):
            response = self.client.post(path, json={field: "What is Alpha?", "document_id": document_id})
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.delete(f"/documents/{document_id}").status_code, 200)
        self.assertEqual(self.client.get("/documents").json()["documents"], [])
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_chat_rejects_unretrieved_citation_without_claiming_context_as_sources(self):
        uploaded = self.upload().json()
        self.answer_mock.side_effect = None
        self.answer_mock.return_value = "Alex [Chunk 999, page 1]"
        response = self.client.post("/chat",
                                json={"message": "Who?", "document_id": uploaded["document_id"]})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["reply"], "Alex")
        self.assertEqual(result["sources"], [])
        self.assertTrue(result["other_context"])
        self.assertIn("removed", result["citation_warning"])

    def test_oversized_upload_is_rejected_before_body_is_read(self):
        consumed = []

        def oversized_stream():
            consumed.append(True)
            yield b"x" * (7 * 1024 * 1024)

        response = self.client.post("/upload", content=oversized_stream(), headers={
            "Content-Type": "multipart/form-data; boundary=test",
            "Content-Length": str(7 * 1024 * 1024)})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(consumed, [])
        self.embed_mock.assert_not_called()

    def test_upload_body_cap_with_and_without_content_length(self):
        for explicit_length in (True, False):
            with self.subTest(explicit_length=explicit_length):
                def oversized_stream():
                    for _ in range(7):
                        yield b"x" * (1024 * 1024)
                headers = {"Content-Type": "multipart/form-data; boundary=test"}
                if explicit_length:
                    headers["Content-Length"] = str(7 * 1024 * 1024)
                with patch("main.extract_pdf") as extractor:
                    response = self.client.post("/upload", content=oversized_stream(), headers=headers)
                self.assertEqual(response.status_code, 413, response.text)
                extractor.assert_not_called()
        self.embed_mock.assert_not_called()
        self.assertEqual(self.upload().status_code, 200)

    def test_cors_deployed_origin_and_preflight(self):
        origin = "https://docuchat-ai-frontend.onrender.com"
        response = self.client.options("/chat", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers.get("access-control-allow-origin"), origin)
        self.assertNotIn("access-control-allow-credentials", response.headers)
        denied = self.client.options("/chat", headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"})
        self.assertEqual(denied.status_code, 400)
        self.assertNotIn("access-control-allow-origin", denied.headers)
        library = self.client.get("/documents", headers={"Origin": origin})
        self.assertEqual(library.status_code, 200)
        self.assertEqual(library.headers.get("access-control-allow-origin"), origin)

    def test_pdf_validation_and_limits_before_embeddings(self):
        cases = [(b"hello", 400), (b"%PDF-malformed", 400),
                 (pdf_bytes(""), 422), (pdf_bytes("secret", encrypted=True), 400),
                 (b"%PDF-" + b"a" * (5 * 1024 * 1024), 413),
                 (pdf_bytes(*([""] * 51)), 413)]
        for data, code in cases:
            with self.subTest(code=code, length=len(data)):
                response = self.upload(content=data)
                self.assertEqual(response.status_code, code, response.text)
        self.embed_mock.assert_not_called()
        self.assertEqual(get_store().list_documents(), [])

    def test_question_validation_and_unknown_document(self):
        for path, field in (("/chat", "message"), ("/search", "question")):
            for value, doc_id, code in ((" ", "a" * 32, 400), ("", "a" * 32, 422),
                                        ("x" * 2001, "a" * 32, 422),
                                        ("question", "invalid", 422),
                                        ("question", "a" * 32, 404)):
                with self.subTest(path=path, code=code):
                    response = self.client.post(path,
                                json={field: value, "document_id": doc_id})
                    self.assertEqual(response.status_code, code, response.text)
        self.embed_mock.assert_not_called()

    def test_failed_embeddings_publish_no_document(self):
        for code in (429, 502, 504):
            with self.subTest(code=code):
                self.embed_mock.side_effect = HTTPException(code, "Upstream unavailable")
                response = self.upload()
                self.assertEqual(response.status_code, code)
                self.assertEqual(get_store().list_documents(), [])
        # Failed requests release the operation slot for the next valid upload.
        self.embed_mock.side_effect = fake_embeddings
        self.assertEqual(self.upload().status_code, 200)

    def test_busy_request_is_rejected_and_slot_survives(self):
        main.operation_lock.acquire()
        try:
            response = self.client.post("/chat",
                                json={"message": "question", "document_id": "a" * 32})
            self.assertEqual(response.status_code, 429)
        finally:
            main.operation_lock.release()
        self.assertEqual(self.upload().status_code, 200)

    def test_pdf_parser_timeout_is_bounded(self):
        import subprocess
        with patch("main.subprocess.run", side_effect=subprocess.TimeoutExpired("extract", 25)):
            response = self.upload()
        self.assertEqual(response.status_code, 413)
        self.embed_mock.assert_not_called()

    def test_filename_is_sanitized(self):
        response = self.upload(filename="../../private/alpha.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["filename"], "alpha.pdf")

    def test_unbroken_unicode_chunks_stay_within_embedding_limit(self):
        text = "क" * 2000
        chunks = main.chunk_text(text)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk.encode("utf-8")) <= 1600 for chunk in chunks))

    def test_render_defaults_to_qdrant_without_silent_local_fallback(self):
        with patch.dict(os.environ, {"RENDER": "true", "QDRANT_URL": "", "QDRANT_API_KEY": ""}):
            os.environ.pop("VECTOR_STORE", None)
            get_store.cache_clear()
            response = self.client.get("/documents")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
