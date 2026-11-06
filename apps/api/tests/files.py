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


def text_pdf_bytes(pages: list[str]) -> bytes:
    """A small but valid multi-page PDF with a real text layer (Helvetica), built by hand."""
    objects: list[bytes] = []
    n = len(pages)
    font_id = 3 + 2 * n
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    for i, text in enumerate(pages):
        ops = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
        for line in text.split("\n"):
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({safe}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    out += f"startxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def real_docx_bytes() -> bytes:
    """A genuine Word document with headings, body text and a table (via python-docx)."""
    import docx

    document = docx.Document()
    document.add_heading("Employee Handbook", level=1)
    document.add_paragraph("Welcome to the company.")
    document.add_heading("Leave", level=2)
    document.add_paragraph("Employees receive 24 days of paid annual leave.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Type", "Days"
    table.cell(1, 0).text, table.cell(1, 1).text = "Sick", "10"
    document.add_heading("Travel", level=2)
    document.add_paragraph("Book travel through the portal at least 14 days ahead.")
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()
