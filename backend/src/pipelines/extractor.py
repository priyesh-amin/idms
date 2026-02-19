import os
import json
import argparse
import hashlib
import shutil

import pdfplumber
import pytesseract
from pdf2image import convert_from_path


def configure_tesseract():
    """Configure tesseract path for Windows if needed; Linux uses PATH."""
    explicit = os.environ.get("TESSERACT_CMD", "").strip()
    if explicit:
        pytesseract.pytesseract.tesseract_cmd = explicit
        return

    if os.name == "nt":
        windows_default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(windows_default):
            pytesseract.pytesseract.tesseract_cmd = windows_default


def detect_poppler_path():
    """Use explicit POPPLER_PATH if provided, else rely on system PATH."""
    explicit = os.environ.get("POPPLER_PATH", "").strip()
    if explicit:
        return explicit

    if os.name == "nt":
        windows_default = r"C:\poppler\Library\bin"
        if os.path.exists(windows_default):
            return windows_default
    return None


def sha256_file(file_path):
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(4096), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_content(file_path):
    try:
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"File not found: {file_path}"}

        configure_tesseract()
        poppler_path = detect_poppler_path()

        file_hash = sha256_file(file_path)
        file_size = os.path.getsize(file_path)

        content = ""
        extraction_method = "pdf_text"
        pages_processed = 0
        ocr_dpi = 0
        ocr_engine_version = "None"

        with pdfplumber.open(file_path) as pdf:
            pages_processed = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n"

        content = content.strip()

        if not content:
            extraction_method = "ocr"
            ocr_dpi = int(os.environ.get("IDMS_OCR_DPI", "300"))
            try:
                ocr_engine_version = str(pytesseract.get_tesseract_version())
            except Exception:
                ocr_engine_version = "Tesseract (Unknown Version)"

            kwargs = {"dpi": ocr_dpi}
            if poppler_path:
                kwargs["poppler_path"] = poppler_path

            images = convert_from_path(file_path, **kwargs)
            pages_processed = len(images)
            for img in images:
                content += pytesseract.image_to_string(img) + "\n"

            content = content.strip()

        if not content:
            return {
                "status": "error",
                "message": "Extraction failed: No text found via PDF stripping or OCR.",
                "hash": file_hash,
                "file_size_bytes": file_size,
                "pages_processed": pages_processed,
                "extraction_method": extraction_method,
                "ocr_used": extraction_method == "ocr",
                "ocr_dpi": ocr_dpi,
                "ocr_engine_version": ocr_engine_version,
                "extracted_text_length": 0,
            }

        return {
            "status": "success",
            "hash": file_hash,
            "file_size_bytes": file_size,
            "pages_processed": pages_processed,
            "content": content,
            "extraction_method": extraction_method,
            "ocr_used": extraction_method == "ocr",
            "ocr_dpi": ocr_dpi,
            "ocr_engine_version": ocr_engine_version,
            "extracted_text_length": len(content),
        }

    except Exception as exc:
        return {"status": "error", "message": str(exc)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IDMS Extractor")
    parser.add_argument("file_path", help="Path to the PDF file")
    args = parser.parse_args()

    result = extract_content(args.file_path)
    print(json.dumps(result))
