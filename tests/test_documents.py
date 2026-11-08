import pymupdf

from findmeajob.tools.documents import extract_text


def test_pdf_text_keeps_words():
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Built fintech workflows")
    text = extract_text("cv.pdf", document.tobytes())
    assert "fintech" in text and "workflows" in text
