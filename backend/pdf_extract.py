"""Isolated PDF extraction worker; receives bytes on stdin, emits bounded JSON."""
from io import BytesIO
import json
import sys

if sys.platform == "linux":
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (192 * 1024 * 1024, 192 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))

from pypdf import PdfReader


def main():
    reader = PdfReader(BytesIO(sys.stdin.buffer.read(5 * 1024 * 1024 + 1)))
    if reader.is_encrypted:
        raise ValueError("Encrypted")
    if len(reader.pages) > 50:
        print("LIMIT:Maximum 50 pages per demo PDF", end="")
        return 1
    pages = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        total += len(text)
        if total > 200000:
            print("LIMIT:Maximum 200,000 extracted characters per PDF", end="")
            return 1
        pages.append(text)
    print(json.dumps({"pages": pages}), end="")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(1)
