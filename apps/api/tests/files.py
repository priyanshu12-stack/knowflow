"""Tiny synthetic upload fixtures, generated in-test (no binary files in the repo)."""

import io
import zipfile

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def pdf_bytes(text: str = "KnowFlow test page") -> bytes:
    return (
        b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n"
        + f"% {text}\n".encode()
        + b"trailer << /Root 1 0 R >>\n%%EOF\n"
    )


def docx_bytes(body: str = "KnowFlow test document") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", f"<w:document><w:body>{body}</w:body></w:document>")
    return buf.getvalue()


def zip_without_word_body() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
    return buf.getvalue()
