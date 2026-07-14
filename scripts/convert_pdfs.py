#!/usr/bin/env python3
"""
PDF → Text converter using Tesseract OCR (local, no API cost).
Works on scanned PDFs by rendering each page to an image, then OCR-ing it.

Requirements:
  pip install pymupdf pytesseract
  Tesseract installed at: C:/Program Files/Tesseract-OCR/

Usage (from the project root):
  python scripts/convert_pdfs.py
"""
from pathlib import Path

import fitz          # pymupdf — renders PDF pages to images
import pytesseract   # wrapper around Tesseract OCR
from PIL import Image
import io

# Point pytesseract to the Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DOCS = Path(__file__).parent.parent / "knowledge_base"


def pdf_to_text(pdf_path: Path) -> str:
    """Render each page of a PDF to an image, run Tesseract OCR on it."""
    doc = fitz.open(str(pdf_path))
    pages_text = []

    for page_num, page in enumerate(doc, start=1):
        print(f"    Page {page_num}/{len(doc)}...", flush=True)

        # Render page to a high-res image (300 DPI gives good OCR accuracy)
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # Run Tesseract OCR
        text = pytesseract.image_to_string(img, lang="eng")

        if text.strip():
            pages_text.append(f"--- Page {page_num} ---\n{text.strip()}")

    doc.close()
    return "\n\n".join(pages_text) if pages_text else "[No text could be extracted]"


def main():
    pdfs = sorted(DOCS.glob("*.pdf"))
    if not pdfs:
        print("No PDF files found in knowledge_base/")
        return

    print(f"Found {len(pdfs)} PDF(s) to convert:\n")

    for pdf_path in pdfs:
        out_path = DOCS / (pdf_path.stem + ".txt")

        print(f"Processing: {pdf_path.name}")
        try:
            text = pdf_to_text(pdf_path)
            out_path.write_text(text, encoding="utf-8")
            print(f"  Saved: {out_path.name} ({len(text):,} chars)\n")
        except Exception as e:
            print(f"  Error: {e}\n")

    print("All done! Run python agent.py and ask questions about your documents.")


if __name__ == "__main__":
    main()
