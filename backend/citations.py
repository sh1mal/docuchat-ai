"""Validate citation identifiers against retrieved context, not factual support."""
import re

MARKER = re.compile(r"\[Chunk\b[^\]\n]*\]", re.IGNORECASE)
REFERENCE = re.compile(r"Chunk\s+([0-9]+)(?:\s*,\s*page\s+([0-9]+))?\s*", re.IGNORECASE)
SEPARATOR = re.compile(r"\s*(?:[,;]|\band\b)\s*(?=Chunk\b)", re.IGNORECASE)


def cited_response(reply, matches):
    available = {str(match["chunk"]): match for match in matches}
    cited = []
    seen = set()
    invalid = False

    def validate(marker):
        nonlocal invalid
        # Gemini sometimes puts several complete references in one bracket.
        # Parse the entire marker before accepting any of it; never infer IDs
        # from arbitrary text or promote uncited retrieval results to sources.
        references = [REFERENCE.fullmatch(part.strip())
                      for part in SEPARATOR.split(marker.group()[1:-1])]
        if not all(references):
            invalid = True
            return ""
        normalized = []
        for reference in references:
            chunk_id = reference[1].lstrip("0") or "0"
            match = available.get(chunk_id)
            page = reference[2]
            if match and (page is None or (page.lstrip("0") or "0") == str(match["page"])):
                if chunk_id not in seen:
                    seen.add(chunk_id)
                    cited.append(match)
                normalized.append(f"[Chunk {match['chunk']}, page {match['page']}]")
            else:
                invalid = True
        return " ".join(normalized)

    reply = MARKER.sub(validate, reply).strip()
    warning = ""
    if invalid:
        warning = "Some source references could not be verified and were removed. Check the excerpts before relying on this answer."
    elif not cited:
        warning = "This answer has no verified source references. You can inspect the retrieved context below."
    if not reply:
        reply = "No answer with usable source references was returned. Please try rephrasing your question."
    return {"reply": reply, "sources": cited,
            "other_context": [match for match in matches if str(match["chunk"]) not in seen],
            "citation_warning": warning}
