"""PDF Document Processing module using PyMuPDF (fitz) with fallback to pypdf."""

from __future__ import annotations

import io
from fastapi import HTTPException

# Prefer PyMuPDF
HAS_PYMUPDF = False
try:
    import pymupdf  # type: ignore
    HAS_PYMUPDF = True
except ImportError:
    try:
        import fitz  # type: ignore
        HAS_PYMUPDF = True
    except ImportError:
        HAS_PYMUPDF = False

# Fallback pypdf
HAS_PYPDF = False
try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract selectable text from a PDF document.

    Rejects empty or scanned PDFs and extracts cleanly formatted text.
    """
    if not HAS_PYMUPDF and not HAS_PYPDF:
        raise HTTPException(status_code=500, detail="No PDF processing library is installed.")

    extracted_pages: list[str] = []

    if HAS_PYMUPDF:
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    extracted_pages.append(text)
            doc.close()
        except Exception as exc:
            # Fall back to pypdf if PyMuPDF encountered an unexpected issue
            if not HAS_PYPDF:
                raise HTTPException(status_code=422, detail=f"Could not read PDF with PyMuPDF: {exc}")
            extracted_pages = []

    if not extracted_pages and HAS_PYPDF:
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                text = page.extract_text() or ""
                if text.strip():
                    extracted_pages.append(text)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}")

    full_text = "\n".join(extracted_pages).strip()
    if not full_text:
        raise HTTPException(
            status_code=422,
            detail="This PDF has no selectable text. Scanned or image-only PDFs are not supported in this synthetic demo."
        )

    return full_text

