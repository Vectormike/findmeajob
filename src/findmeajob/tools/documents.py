from io import BytesIO
from pathlib import Path

import pymupdf
from docx import Document

CV_TYPES = (".pdf", ".docx", ".txt", ".md")


def pdf_text(data: bytes) -> str:
    with pymupdf.open(stream=data, filetype="pdf") as document:
        return "\n".join(page.get_text() for page in document)


def docx_text(data: bytes) -> str:
    return "\n".join(paragraph.text for paragraph in Document(BytesIO(data)).paragraphs)


def extract_text(name: str, data: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix not in CV_TYPES:
        raise ValueError("wrong file type, bestie. pdf, docx, txt, or md only.")
    if suffix == ".pdf":
        text = pdf_text(data)
    elif suffix == ".docx":
        text = docx_text(data)
    else:
        text = data.decode("utf-8", errors="replace")
    # PDFs often contain a null byte. Postgres cannot store one inside text or JSON.
    text = text.replace("\x00", "")
    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not text:
        raise ValueError("this file is giving blank. scans have no text, so drop a real pdf or a docx.")
    return text
