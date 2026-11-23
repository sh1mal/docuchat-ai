"""Citation visibility must follow validated references, not retrieval rank."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from citations import cited_response


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.matches = [
            {"chunk": 1, "page": 1, "text": "Applicant: Alex"},
            {"chunk": 4, "page": 1, "text": "IT support experience"},
            {"chunk": 5, "page": 2, "text": "Education"},
        ]

    def test_only_cited_chunk_is_a_source(self):
        result = cited_response("Alex [Chunk 1, page 1]", self.matches)
        self.assertEqual(result["sources"], self.matches[:1])
        self.assertEqual(result["other_context"], self.matches[1:])
        self.assertEqual(result["citation_warning"], "")

    def test_sources_follow_citation_order_without_duplicates(self):
        result = cited_response("[Chunk 5, page 2] [Chunk 1, page 1] [Chunk 5, page 2]", self.matches)
        self.assertEqual([s["chunk"] for s in result["sources"]], [5, 1])
        self.assertEqual(result["other_context"], [self.matches[1]])

    def test_invented_unretrieved_and_wrong_page_references_are_removed(self):
        for marker in ("[Chunk 99, page 1]", "[Chunk 2, page 1]", "[Chunk 1, page 2]",
                       "[Chunk 1, page unknown]", "[Chunk 1, page 1; unrelated text]"):
            with self.subTest(marker=marker):
                result = cited_response("An answer " + marker, self.matches)
                self.assertEqual(result["reply"], "An answer")
                self.assertEqual(result["sources"], [])
                self.assertEqual(result["other_context"], self.matches)
                self.assertIn("removed", result["citation_warning"])

    def test_valid_citations_survive_alongside_invalid_ones(self):
        result = cited_response("Alex [Chunk 1, page 1] [Chunk 99, page 1]", self.matches)
        self.assertEqual(result["reply"], "Alex [Chunk 1, page 1]")
        self.assertEqual(result["sources"], self.matches[:1])
        self.assertTrue(result["citation_warning"])

    def test_live_grouped_citation_is_normalized(self):
        matches = [{"chunk": 6, "page": 3, "text": "Remote work policy"},
                   {"chunk": 5, "page": 3, "text": "Up to three days per week"},
                   {"chunk": 8, "page": 4, "text": "Leave policy"}]
        result = cited_response(
            "Up to three days per week [Chunk 5, page 3 , Chunk 6, page 3].", matches)
        self.assertEqual(result["reply"],
                         "Up to three days per week [Chunk 5, page 3] [Chunk 6, page 3].")
        self.assertEqual(result["sources"], [matches[1], matches[0]])
        self.assertEqual(result["other_context"], [matches[2]])
        self.assertEqual(result["citation_warning"], "")

    def test_grouped_citation_separators_and_repeated_sources(self):
        for separator in (", ", "; ", " and "):
            with self.subTest(separator=separator):
                result = cited_response(
                    "[chunk 001, page 01" + separator + "Chunk 4, page 1] [Chunk 1]",
                    self.matches)
                self.assertEqual(result["sources"], self.matches[:2])
                self.assertEqual(result["citation_warning"], "")

    def test_live_wrapped_reference_is_not_silently_left_unverified(self):
        result = cited_response("Answer [Chunk 5, page 2\n] [Chunk 1,\npage 1]", self.matches)
        self.assertEqual(result["reply"], "Answer [Chunk 5, page 2] [Chunk 1, page 1]")
        self.assertEqual(result["sources"], [self.matches[2], self.matches[0]])
        self.assertEqual(result["citation_warning"], "")
        invalid = cited_response("Answer [Chunk 99, page 2\n]", self.matches)
        self.assertEqual(invalid["sources"], [])
        self.assertEqual(invalid["reply"], "Answer")
        self.assertIn("removed", invalid["citation_warning"])

    def test_grouped_citations_still_reject_wrong_pages_and_unknown_chunks(self):
        for invalid in ("Chunk 99, page 1", "Chunk 2, page 1", "Chunk 4, page 2"):
            with self.subTest(invalid=invalid):
                result = cited_response("Alex [Chunk 1, page 1, " + invalid + "]", self.matches)
                self.assertEqual(result["reply"], "Alex [Chunk 1, page 1]")
                self.assertEqual(result["sources"], self.matches[:1])
                self.assertEqual(result["other_context"], self.matches[1:])
                self.assertIn("removed", result["citation_warning"])

    def test_malformed_group_is_not_partially_accepted(self):
        for marker in ("[Chunk 1, page 1, Chunk 4, page unknown]",
                       "[Chunk 1, page 1, arbitrary 4]",
                       "[Chunk 1, page 1; Chunk 4, page 1 extra text]"):
            with self.subTest(marker=marker):
                result = cited_response("Answer " + marker, self.matches)
                self.assertEqual(result["sources"], [])
                self.assertEqual(result["reply"], "Answer")
                self.assertIn("removed", result["citation_warning"])

    def test_missing_citations_never_promote_context_to_sources(self):
        result = cited_response("The answer is not in the excerpts.", self.matches)
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["other_context"], self.matches)
        self.assertIn("no verified source references", result["citation_warning"])

    def test_bare_chunk_reference_is_resolved_to_its_actual_page(self):
        result = cited_response("Education [chunk 005]", self.matches)
        self.assertEqual(result["reply"], "Education [Chunk 5, page 2]")
        self.assertEqual(result["sources"], [self.matches[2]])

    def test_huge_numeric_reference_does_not_crash(self):
        result = cited_response("Answer [Chunk " + "9" * 5000 + ", page 1]", self.matches)
        self.assertEqual(result["sources"], [])
        self.assertTrue(result["citation_warning"])

    def test_only_invalid_reference_returns_readable_fallback(self):
        result = cited_response("[Chunk 999, page 1]", self.matches)
        self.assertIn("rephrasing", result["reply"])
        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
