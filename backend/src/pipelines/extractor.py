import os
import json
import sys
import hashlib
import pdfplumber
import pytesseract
from pdf2image import convert_from_path

# Explicitly setting Tesseract path for Windows robustness
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_content(file_path):
    """
    Extracts text from a PDF file. Falls back to real OCR if text is empty.
    Returns a JSON response with full telemetry.
    """
    try:
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"File not found: {file_path}"}

        # Calculate SHA-256 Hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        file_hash = sha256_hash.hexdigest()
        file_size = os.path.getsize(file_path)

        content = ""
        extraction_method = "pdf_text"
        pages_processed = 0
        ocr_dpi = 0
        ocr_engine_version = "None"

        # Attempt standard text extraction
        with pdfplumber.open(file_path) as pdf:
            pages_processed = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n"
        
        content = content.strip()

        # Trigger OCR Fallback if no text found
        if not content:
            extraction_method = "ocr"
            ocr_dpi = 300
            try:
                ocr_engine_version = str(pytesseract.get_tesseract_version())
            except:
                ocr_engine_version = "Tesseract (Unknown Version)"

            # Convert PDF to images for OCR
            # Explicitly setting poppler_path for Windows robustness
            poppler_path = r"C:\poppler\Library\bin"
            images = convert_from_path(file_path, dpi=ocr_dpi, poppler_path=poppler_path)
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
                "ocr_used": (extraction_method == "ocr"),
                "ocr_dpi": ocr_dpi,
                "ocr_engine_version": ocr_engine_version,
                "extracted_text_length": 0
            }

        return {
            "status": "success",
            "hash": file_hash,
            "file_size_bytes": file_size,
            "pages_processed": pages_processed,
            "content": content,
            "extraction_method": extraction_method,
            "ocr_used": (extraction_method == "ocr"),
            "ocr_dpi": ocr_dpi,
            "ocr_engine_version": ocr_engine_version,
            "extracted_text_length": len(content)
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IDMS Extractor - Real OCR Mode")
    parser.add_argument("file_path", help="Path to the PDF file")
    args = parser.parse_args()

    result = extract_content(args.file_path)
    print(json.dumps(result))
