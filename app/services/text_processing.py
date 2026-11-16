"""Turning an uploaded file into searchable chunks. Pure functions: easy to unit-test."""
import io
import re
from dataclasses import dataclass

from pypdf import PdfReader

PDF, TEXT, MARKDOWN = "application/pdf", "text/plain", "text/markdown"
SUPPORTED_TYPES = {PDF, TEXT, MARKDOWN}

CHUNK_SIZE = 1000     # characters; ~250 tokens, small enough that one chunk is about one topic
CHUNK_OVERLAP = 150   # repeated between neighbours so a sentence cut at a boundary is still findable


class ExtractionError(Exception):
    pass


@dataclass
class Chunk:
    index: int
    page: int | None
    text: str
    codes: list[str]


def detect_type(filename: str, declared: str | None, content: bytes) -> str | None:
    """Trust the bytes over the client's Content-Type header."""
    if content.startswith(b"%PDF-"):
        return PDF
    name = filename.lower()
    if name.endswith((".md", ".markdown")):
        return MARKDOWN
    if name.endswith(".txt") or declared == TEXT:
        return TEXT
    return None


def extract_pages(content: bytes, content_type: str) -> list[tuple[int | None, str]]:
    """[(page_number, text)]: page numbers are 1-based for PDFs, None for text files."""
    if content_type == PDF:
        try:
            reader = PdfReader(io.BytesIO(content))
            return [(number, page.extract_text() or "") for number, page in enumerate(reader.pages, start=1)]
        except Exception as exc:  # pypdf raises many types for damaged files
            raise ExtractionError(f"Could not read PDF: {exc}") from exc
    return [(None, content.decode("utf-8", errors="replace"))]


# A "code" mixes letters and digits (E-47, BD-2210, ERR_0x1F, M6) or is a 3-6 digit number (1047).
_CODE_TOKEN = re.compile(r"(?<![\w-])[A-Za-z0-9][A-Za-z0-9_\-./]*[A-Za-z0-9](?![\w-])|(?<![\w-])[A-Za-z]\d(?![\w-])")


def normalize_code(token: str) -> str:
    """E-47, e47, E_47 and e-47 all become E47, so formatting differences still match exactly."""
    return re.sub(r"[-_./\s]", "", token).upper()


def extract_codes(text: str) -> list[str]:
    """Used at BOTH index time and query time: one function, so the two sides can never disagree."""
    codes = set()
    for token in _CODE_TOKEN.findall(text):
        normalized = normalize_code(token)
        has_digit, has_letter = any(c.isdigit() for c in normalized), any(c.isalpha() for c in normalized)
        if (has_digit and has_letter) or (normalized.isdigit() and 3 <= len(normalized) <= 6):
            codes.add(normalized)
    return sorted(codes)


def _split_long(paragraph: str, size: int) -> list[str]:
    """Paragraphs longer than a chunk are split at sentence ends, then at spaces."""
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
        while len(sentence) > size:                       # one enormous "sentence": cut at a space
            cut = sentence.rfind(" ", 0, size) if " " in sentence[:size] else size
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if len(current) + len(sentence) + 1 > size and current:
            pieces.append(current.strip())
            current = ""
        current += " " + sentence
    if current.strip():
        pieces.append(current.strip())
    return pieces


def chunk_pages(
    pages: list[tuple[int | None, str]], size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[Chunk]:
    """Pack paragraphs into ~size-character chunks. Chunks never span two pages, so every
    citation can name an exact page."""
    chunks: list[Chunk] = []
    for page, text in pages:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        pieces: list[str] = []
        for paragraph in paragraphs:
            pieces.extend(_split_long(" ".join(paragraph.split()), size))
        current = ""
        for piece in pieces:
            if current and len(current) + len(piece) + 1 > size:
                chunks.append(Chunk(len(chunks), page, current, extract_codes(current)))
                tail = current[-overlap:]
                tail = tail[tail.find(" ") + 1:] if " " in tail else ""      # start the overlap at a word
                current = tail if len(tail) + len(piece) + 1 <= size else ""   # carry it only if it fits
            current = f"{current} {piece}".strip()
        if current:
            chunks.append(Chunk(len(chunks), page, current, extract_codes(current)))
    return chunks
