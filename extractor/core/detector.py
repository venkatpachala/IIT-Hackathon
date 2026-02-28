import os
import struct


def detect_format(file_path: str) -> str:
    """
    Returns one of:
        'pdf_text'    → digital PDF with extractable text
        'pdf_scanned' → image-based PDF, needs OCR
        'docx'        → Microsoft Word document
        'xlsx'        → Microsoft Excel workbook
        'csv'         → Comma-separated values
        'txt'         → Plain text file
        'unknown'     → Cannot determine
    """
    ext = os.path.splitext(file_path)[1].lower()

    # ── CSV and TXT: purely extension-based ─────────────────
    if ext == ".csv":
        return "csv"
    if ext == ".txt":
        return "txt"

    # ── Read magic bytes (first 8 bytes of file) ─────────────
    with open(file_path, "rb") as f:
        magic = f.read(8)

    # ── DOCX / XLSX: both are ZIP files with magic PK ────────
    if magic[:2] == b"PK":
        # Distinguish DOCX vs XLSX by internal structure
        import zipfile
        try:
            with zipfile.ZipFile(file_path) as z:
                names = z.namelist()
            if any("word/" in n for n in names):
                return "docx"
            if any("xl/" in n for n in names):
                return "xlsx"
        except Exception:
            pass
        return "unknown"

    # ── PDF: magic bytes %PDF ─────────────────────────────────
    if magic[:4] == b"%PDF":
        return _classify_pdf(file_path)

    return "unknown"


def _classify_pdf(file_path: str) -> str:
    """
    Distinguishes text-based PDF from scanned PDF.
    Strategy: try pdfplumber first. If it extracts < 100 chars per page
    on average, it's likely a scanned document.
    """
    try:
        import pdfplumber
        total_chars = 0
        page_count  = 0

        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            # Sample up to first 5 pages for speed
            for page in pdf.pages[:5]:
                text = page.extract_text() or ""
                total_chars += len(text.strip())

        avg_chars_per_page = total_chars / max(page_count, 1)

        # Heuristic: < 100 chars/page = almost certainly scanned
        if avg_chars_per_page < 100:
            return "pdf_scanned"
        return "pdf_text"

    except ImportError:
        # pdfplumber not installed — fall back to extension
        print("[WARN] pdfplumber not installed. Assuming text PDF.")
        return "pdf_text"
    except Exception as e:
        print(f"[WARN] PDF classification error: {e}. Assuming text PDF.")
        return "pdf_text"