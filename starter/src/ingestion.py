"""Load and normalize PDF pages without losing paragraph breaks."""
import logging
from pathlib import Path
import re
import unicodedata

from pypdf import PdfReader

from .models import DocumentPage

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = re.split(r"\n(?:[^\S\n]*\n)+", text)
    cleaned = (" ".join(paragraph.split()) for paragraph in paragraphs)
    return "\n\n".join(paragraph for paragraph in cleaned if paragraph)


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    pages = []
    for number, page in enumerate(PdfReader(path).pages, 1):
        try:
            text = normalize_text(page.extract_text() or "")
        except Exception:
            logger.exception("Extraction failed for %s, PDF page %d", source, number)
            text = ""
        if not text:
            logger.warning("No usable text in %s, PDF page %d", source, number)
        pages.append(DocumentPage(document_id, source, number, text))
    return pages
