"""Build page-local chunks with offsets into the normalized page text."""
import re

from .models import Chunk, DocumentPage

BOUNDARY = re.compile(r"\n\n+|(?<=[.!?…])\s+")


def make_chunk(page: DocumentPage, start: int, end: int) -> Chunk:
    fragment = page.text[start:end]
    start += len(fragment) - len(fragment.lstrip())
    end -= len(fragment) - len(fragment.rstrip())
    return Chunk(
        f"{page.document_id}:p{page.page}:{start}-{end}",
        page.document_id,
        page.source,
        page.page,
        page.text[start:end],
        {**page.metadata, "char_start": start, "char_end": end},
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if not 0 <= overlap < size:
        raise ValueError("Expected 0 <= overlap < size")
    chunks = []
    for start in range(0, len(page.text), size - overlap):
        end = min(start + size, len(page.text))
        if page.text[start:end].strip():
            chunks.append(make_chunk(page, start, end))
        if end == len(page.text):
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    text = page.text
    # Prefer paragraph breaks, then sentence endings, then whitespace for long sentences.
    paragraphs = [m.start() for m in re.finditer(r"\n\n", text)]
    sentences = [m.start() for m in BOUNDARY.finditer(text)]
    chunks = []
    start = 0
    while start < len(text):
        limit = min(start + max_size, len(text))
        end = limit
        if limit < len(text):
            minimum = start + max_size // 2
            paragraph_end = max((p for p in paragraphs if minimum < p <= limit), default=-1)
            sentence_end = max((p for p in sentences if minimum < p <= limit), default=-1)
            word_end = text.rfind(" ", minimum + 1, limit + 1)
            end = next((p for p in (paragraph_end, sentence_end, word_end) if p > start), limit)
        if text[start:end].strip():
            chunks.append(make_chunk(page, start, end))
        start = end
        while start < len(text) and text[start].isspace():
            start += 1
    return chunks
