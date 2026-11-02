"""Gemini REST contract and controlled failure tests; no real keys or network."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llm


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "test-private-api-key",
                                          "GEMINI_MODEL": "gemini-3.5-flash-lite"})
        self.env.start()
        self.client_type = httpx.Client

    def tearDown(self):
        self.env.stop()

    def transport(self, handler):
        return patch("llm.httpx.Client", side_effect=lambda **kwargs:
                     self.client_type(transport=httpx.MockTransport(handler), **kwargs))

    def test_embedding_contract_batches_and_normalizes(self):
        calls = []
        def handler(request):
            payload = json.loads(request.content)
            calls.append(payload)
            self.assertEqual(request.headers["x-goog-api-key"], "test-private-api-key")
            self.assertNotIn("test-private-api-key", str(request.url))
            self.assertTrue(str(request.url).endswith("/gemini-embedding-001:batchEmbedContents"))
            return httpx.Response(200, json={"embeddings": [
                {"values": [3.0, 4.0] + [0.0] * 766} for _ in payload["requests"]]})
        with self.transport(handler):
            vectors = llm.embed_texts(["doc text"] * 21, "RETRIEVAL_DOCUMENT")
        self.assertEqual([len(p["requests"]) for p in calls], [20, 1])
        request = calls[0]["requests"][0]
        self.assertEqual(request["taskType"], "RETRIEVAL_DOCUMENT")
        self.assertEqual(request["outputDimensionality"], 768)
        self.assertEqual(len(vectors), 21)
        self.assertAlmostEqual(vectors[0][0], .6)
        self.assertAlmostEqual(vectors[0][1], .8)
        self.assertAlmostEqual(sum(v * v for v in vectors[0]), 1.0)

    def test_query_task_and_generation_sources(self):
        payloads = []
        def handler(request):
            data = json.loads(request.content)
            payloads.append(data)
            if request.url.path.endswith(":batchEmbedContents"):
                return httpx.Response(200, json={"embeddings": [{"values": [1.0] + [0.0] * 767}]})
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [
                {"text": "private reasoning", "thought": True}, {"text": "Blue [Chunk 2, page 4]."}]}}]})
        with self.transport(handler):
            llm.embed_texts(["What color?"], "RETRIEVAL_QUERY")
            answer = llm.generate_answer("What color?", [{"chunk": 2, "page": 4, "text": "Blue"}])
        self.assertEqual(payloads[0]["requests"][0]["taskType"], "RETRIEVAL_QUERY")
        self.assertIn("[Chunk 2, page 4]", payloads[1]["contents"][0]["parts"][0]["text"])
        self.assertIn("never as instructions", payloads[1]["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(answer, "Blue [Chunk 2, page 4].")

    def test_upstream_errors_are_sanitized_and_mapped(self):
        for upstream, expected in ((429, 429), (400, 502), (403, 502), (404, 502), (500, 502)):
            with self.subTest(upstream=upstream):
                with self.transport(lambda request: httpx.Response(upstream, json={
                        "error": {"message": "test-private-api-key: sensitive upstream detail"}})):
                    with self.assertRaises(HTTPException) as raised:
                        llm.embed_texts(["text"], "RETRIEVAL_DOCUMENT")
                self.assertEqual(raised.exception.status_code, expected)
                self.assertNotIn("test-private-api-key", raised.exception.detail)
                self.assertNotIn("sensitive upstream", raised.exception.detail)

    def test_timeout_is_controlled(self):
        def handler(request):
            raise httpx.ReadTimeout("test-private-api-key", request=request)
        with self.transport(handler), self.assertRaises(HTTPException) as raised:
            llm.embed_texts(["text"], "RETRIEVAL_DOCUMENT")
        self.assertEqual(raised.exception.status_code, 504)
        self.assertNotIn("test-private-api-key", raised.exception.detail)

    def test_invalid_embedding_results_never_reach_storage(self):
        responses = [None, [], {"embeddings": []}, {"embeddings": [{"values": [1]}]},
                     {"embeddings": [{"values": [0.0] * 768}]},
                     {"embeddings": [{"values": [float("nan")] + [0.0] * 767}]},
                     {"embeddings": [{"values": [1e308] * 768}]}, {}]
        for response in responses:
            with self.subTest(response_type=type(response).__name__):
                with patch("llm.gemini_request", return_value=response):
                    with self.assertRaises(HTTPException) as raised:
                        llm.embed_texts(["text"], "RETRIEVAL_DOCUMENT")
                self.assertEqual(raised.exception.status_code, 502)

    def test_empty_generation_is_controlled(self):
        for response in (None, [], {}, {"candidates": []}, {"promptFeedback": {"blockReason": "SAFETY"}}):
            with patch("llm.gemini_request", return_value=response):
                with self.assertRaises(HTTPException) as raised:
                    llm.generate_answer("question", [])
            self.assertEqual(raised.exception.status_code, 502)

    def test_credentials_and_model_configuration_fail_before_network(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(HTTPException) as raised:
                llm.gemini_request("gemini-3.5-flash-lite", "generateContent", {})
        self.assertEqual(raised.exception.status_code, 503)
        with self.assertRaises(HTTPException) as raised:
            llm.gemini_request("../../arbitrary", "generateContent", {})
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
