from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from xml.etree import ElementTree

from pypdf import PdfReader

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_DOCUMENT_CHARS = 20_000

_TEXT_MEDIA_TYPES = {
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".sql": "application/sql",
    ".txt": "text/plain",
}
_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True)
class DocumentText:
    filename: str
    media_type: str
    text: str
    character_count: int


class DocumentIngestError(ValueError):
    """A user-safe error raised while reading an uploaded document."""


def extract_document(filename: str, content: bytes) -> DocumentText:
    safe_filename = PurePath(filename or "document").name
    suffix = PurePath(safe_filename).suffix.casefold()
    if suffix not in {*_TEXT_MEDIA_TYPES, ".docx", ".pdf"}:
        raise DocumentIngestError(
            "Supported document formats are PDF, DOCX, TXT, Markdown, SQL, and CSV."
        )
    if len(content) > MAX_DOCUMENT_BYTES:
        raise DocumentIngestError("The uploaded document is too large; the limit is 10 MiB.")
    if not content:
        raise DocumentIngestError("The uploaded document is empty.")

    if suffix in _TEXT_MEDIA_TYPES:
        media_type = _TEXT_MEDIA_TYPES[suffix]
        raw_text = _decode_text(content)
    elif suffix == ".pdf":
        media_type = "application/pdf"
        raw_text = _extract_pdf(content)
    else:
        media_type = _DOCX_MEDIA_TYPE
        raw_text = _extract_docx(content)

    text = _normalize_text(raw_text)
    if not text:
        raise DocumentIngestError("The uploaded document is empty after text extraction.")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise DocumentIngestError(
            "The extracted document is longer than the 20,000 character limit."
        )
    return DocumentText(safe_filename, media_type, text, len(text))


def _decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentIngestError("The text document could not be read as UTF-8.") from exc


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise DocumentIngestError("Encrypted PDF documents are not supported.")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except DocumentIngestError:
        raise
    except Exception as exc:
        raise DocumentIngestError("The PDF document could not be read.") from exc


def _extract_docx(content: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            xml_bytes = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml_bytes)
    except Exception as exc:
        raise DocumentIngestError("The DOCX document could not be read.") from exc

    paragraphs: list[str] = []
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        words = [
            node.text or ""
            for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
        ]
        if words:
            paragraphs.append("".join(words))
    return "\n".join(paragraphs)


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
