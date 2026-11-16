"""Pure functions behind indexing: code extraction, chunking, type detection, PDF text."""
import pytest

from app.services.text_processing import (
    PDF,
    TEXT,
    ExtractionError,
    chunk_pages,
    detect_type,
    extract_codes,
    extract_pages,
)
from tests.conftest import make_pdf


@pytest.mark.parametrize("text, codes", [
    ("Error E-47 indicates a spindle encoder fault", ["E47"]),
    ("what does e47 mean?", ["E47"]),                      # same code however it is typed
    ("E_47 and e-47", ["E47"]),
    ("Replace belt BD-2210 every 6 months", ["BD2210"]),   # "6" alone is not a code
    ("Alarm ERR_0x1F on the servo drive", ["ERR0X1F"]),
    ("Code 1047 overload", ["1047"]),
    ("Serviced on 2026-11-16", []),                       # dates are not codes
    ("The spindle vibrates", []),
])
def test_extract_codes(text, codes):
    assert extract_codes(text) == codes


def test_chunks_respect_size_pages_and_overlap():
    body = "\n\n".join(f"Paragraph {i}. " + "The spindle encoder reports shaft position. " * 10 for i in range(6))
    chunks = chunk_pages([(1, body), (2, "Page two mentions E-12.")])
    assert all(len(c.text) <= 1000 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert chunks[-1].page == 2 and chunks[-1].codes == ["E12"]      # chunks never span pages
    assert chunks[0].text[-40:][:20] in chunks[1].text                 # neighbours overlap


def test_one_giant_line_is_still_split():
    chunks = chunk_pages([(None, "word " * 1000)])
    assert len(chunks) >= 5 and all(len(c.text) <= 1000 for c in chunks)


def test_detect_type_trusts_bytes_over_header():
    assert detect_type("manual.txt", "text/plain", b"%PDF-1.4 ...") == PDF   # it IS a PDF
    assert detect_type("notes.txt", None, b"hello") == TEXT
    assert detect_type("notes.md", None, b"# hi") == "text/markdown"
    assert detect_type("tool.exe", "application/octet-stream", b"MZ") is None


def test_pdf_text_extraction_keeps_page_numbers():
    pages = extract_pages(make_pdf(["Spindle error E-47", "Coolant pump P-3"]), PDF)
    assert [p for p, _ in pages] == [1, 2] and "E-47" in pages[0][1]


def test_broken_pdf_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract_pages(b"%PDF-1.4 this is not really a pdf", PDF)
