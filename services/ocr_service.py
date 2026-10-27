"""Optional, resource-bounded OCR for image uploads and scanned PDFs.

OCR is opt-in through installed runtime dependencies. This module never downloads
models or invokes OCR unless called; callers must enforce upload limits first.
"""
from __future__ import annotations

import io
import os
import time

import config

MAX_IMAGE_PIXELS = int(os.getenv("SMART_BETHG_OCR_MAX_IMAGE_PIXELS", "16000000"))
OCR_TIMEOUT_SECONDS = max(1, int(os.getenv("SMART_BETHG_OCR_TIMEOUT_SECONDS", "12")))
OCR_MAX_PAGES = max(1, min(int(os.getenv("SMART_BETHG_OCR_MAX_PAGES", "5")), 10))
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}


class OCRUnavailable(RuntimeError):
    """OCR runtime dependencies are missing or OCR is not supported."""


class OCRLimitExceeded(RuntimeError):
    """OCR input exceeds configured resource limits."""


def _ocr_image(image, started):
    # Validate cheap, deterministic bounds before checking optional runtime
    # dependencies so the limits are always enforced and independently testable.
    width, height = image.size
    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
        raise OCRLimitExceeded("Image dimensions exceed the configured OCR pixel limit.")
    remaining = OCR_TIMEOUT_SECONDS - (time.monotonic() - started)
    if remaining <= 0:
        raise OCRLimitExceeded("OCR exceeded the configured time limit.")

    try:
        import pytesseract
    except ImportError as exc:
        raise OCRUnavailable("OCR is unavailable. Install the optional OCR dependencies.") from exc

    try:
        return pytesseract.image_to_string(image, timeout=max(1, int(remaining)))
    except RuntimeError as exc:
        raise OCRLimitExceeded("OCR exceeded the configured time limit.") from exc


def extract_image_text(content: bytes) -> str:
    """OCR one supported raster image, enforcing byte-independent pixel/time limits."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise OCRUnavailable("OCR is unavailable. Install the optional OCR dependencies.") from exc
    started = time.monotonic()
    try:
        with Image.open(io.BytesIO(content)) as source:
            source.verify()
        with Image.open(io.BytesIO(content)) as source:
            image = source.convert("RGB")
            return _ocr_image(image, started)[:config.MAX_EXTRACTED_TEXT_CHARS]
    except (OCRUnavailable, OCRLimitExceeded):
        raise
    except Exception as exc:
        raise ValueError("Could not read this image for OCR.") from exc


def extract_scanned_pdf_text(content: bytes, max_pages: int) -> str:
    """OCR a bounded number of PDF pages; requires optional pdf2image/Pillow/Tesseract."""
    try:
        from pdf2image import convert_from_bytes
        from pypdf import PdfReader
    except ImportError as exc:
        raise OCRUnavailable("Scanned-PDF OCR is unavailable. Install the optional OCR dependencies.") from exc
    started = time.monotonic()
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        page_count = min(len(reader.pages), max(1, min(max_pages, OCR_MAX_PAGES)))
        if page_count <= 0:
            return ""
        images = convert_from_bytes(
            content, first_page=1, last_page=page_count, dpi=150,
            timeout=OCR_TIMEOUT_SECONDS,
        )
        pieces = []
        total = 0
        for image in images:
            piece = _ocr_image(image, started)
            remaining = config.MAX_EXTRACTED_TEXT_CHARS - total
            if remaining <= 0:
                break
            pieces.append(piece[:remaining])
            total += min(len(piece), remaining)
            if total >= config.MAX_EXTRACTED_TEXT_CHARS:
                break
        if len(reader.pages) > page_count:
            pieces.append("\n[Smart BethG stopped OCR at the configured page limit.]")
        return "\n".join(pieces)
    except (OCRUnavailable, OCRLimitExceeded):
        raise
    except Exception as exc:
        raise ValueError("Could not OCR this PDF. Check that it is valid and that PDF rasterization is configured.") from exc
