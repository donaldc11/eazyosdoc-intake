"""Text extraction from PDFs and images. Never fabricates text — returns
an empty string plus an explanatory note when extraction isn't possible."""

from pathlib import Path
from typing import Tuple

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
SUPPORTED_EXTENSIONS = {".pdf", ".txt"} | IMAGE_EXTENSIONS


def extract_text(path: Path) -> Tuple[str, str]:
    """Returns (raw_text, note). `note` is empty on clean extraction, otherwise
    describes the caveat (e.g. scanned PDF, OCR unavailable)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".txt":
        return _extract_txt(path)
    if suffix in IMAGE_EXTENSIONS:
        return _extract_image(path)
    return "", f"unsupported file type: {suffix}"


def _extract_txt(path: Path) -> Tuple[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - surface any read failure as a review note
        return "", f"text file read error: {exc}"
    if not text.strip():
        return "", "text file was empty"
    return text, ""


def _extract_pdf(path: Path) -> Tuple[str, str]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - surface any parse failure as a review note
        return "", f"pdf extraction error: {exc}"

    if not text.strip():
        return "", "pdf produced no extractable text (likely scanned/image-only; OCR not attempted)"
    return text, ""


def _extract_image(path: Path) -> Tuple[str, str]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        return "", f"OCR skipped: missing dependency ({exc.name})"

    try:
        text = pytesseract.image_to_string(Image.open(path))
    except Exception as exc:  # noqa: BLE001 - e.g. tesseract binary missing
        return "", f"OCR error (is the tesseract binary installed?): {exc}"

    if not text.strip():
        return "", "OCR produced no text"
    return text, ""
