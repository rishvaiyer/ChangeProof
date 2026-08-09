from __future__ import annotations

import io
import zipfile

import pytest
from reportlab.pdfgen import canvas

from changeproof.document_ingest import DocumentIngestError, extract_document


def _pdf_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()


def _docx_bytes(text: str) -> bytes:
    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>
</w:document>'''
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("filename", "content", "expected"),
    [
        (
            "requirements.txt",
            b"Compare invoices\nCheck settlements",
            "Compare invoices\nCheck settlements",
        ),
        ("requirements.md", b"# Rules\n- Compare invoices", "# Rules\n- Compare invoices"),
        (
            "query.sql",
            b"SELECT * FROM finance.ar_transactions;",
            "SELECT * FROM finance.ar_transactions;",
        ),
        (
            "rules.csv",
            b"rule,domain\ncompare invoices,Finance",
            "rule,domain\ncompare invoices,Finance",
        ),
    ],
)
def test_extract_document_preserves_text_formats(
    filename: str, content: bytes, expected: str
) -> None:
    document = extract_document(filename, content)

    assert document.filename == filename
    assert document.text == expected
    assert document.character_count == len(expected)


def test_extract_document_reads_pdf_text() -> None:
    document = extract_document("incident.pdf", _pdf_bytes("Compare invoices"))

    assert "Compare invoices" in document.text
    assert document.media_type == "application/pdf"


def test_extract_document_reads_docx_text() -> None:
    document = extract_document("incident.docx", _docx_bytes("Compare settlements"))

    assert document.text == "Compare settlements"
    assert document.media_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("incident.exe", b"not supported", "Supported document formats"),
        ("incident.txt", b"", "empty"),
        ("incident.txt", b"x" * 20_001, "20,000"),
        ("incident.txt", b"x" * (10 * 1024 * 1024 + 1), "too large"),
    ],
)
def test_extract_document_rejects_unsafe_or_empty_inputs(
    filename: str, content: bytes, message: str
) -> None:
    with pytest.raises(DocumentIngestError, match=message):
        extract_document(filename, content)


def test_extract_document_rejects_invalid_pdf() -> None:
    with pytest.raises(DocumentIngestError, match="could not be read"):
        extract_document("incident.pdf", b"not a pdf")
