"""
extractors/pdf_scanned.py
Handles IMAGE-based / scanned PDFs using OCR (pytesseract + pdf2image).

Install:
    pip install pytesseract pdf2image Pillow

System dependencies (run once):
    sudo apt-get install tesseract-ocr poppler-utils

For Hindi / bilingual Indian documents:
    sudo apt-get install tesseract-ocr-hin
    Then set lang='eng+hin' in the pytesseract call below.
"""


def extract_pdf_scanned(file_path: str) -> list:
    """
    Converts each PDF page to a high-res image, runs OCR on each image.
    Returns same format as extract_pdf_text for full pipeline compatibility.

    Returns:
        List of dicts — one per page — each with keys:
        page, text, source, type, method, has_tables, ocr_confidence
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise ImportError(
            "pdf2image not installed.\n"
            "Run: pip install pdf2image\n"
            "Also run: sudo apt-get install poppler-utils"
        )

    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError(
            "pytesseract or Pillow not installed.\n"
            "Run: pip install pytesseract Pillow\n"
            "Also run: sudo apt-get install tesseract-ocr"
        )

    source  = file_path.split("/")[-1]
    results = []

    print(f"      [OCR] Converting PDF pages to images at 300 DPI...")
    # dpi=300 balances accuracy vs speed. Use 400 for very small text.
    images = convert_from_path(file_path, dpi=300)
    print(f"      [OCR] Running Tesseract OCR on {len(images)} page(s)...")

    for i, image in enumerate(images, start=1):
        # Pre-process image to improve OCR accuracy
        image = _preprocess_image(image)

        # Run OCR
        # Use lang="eng+hin" for bilingual Hindi+English documents
        text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 6"   # PSM 6 = uniform block of text
        )

        # Get confidence score for this page
        confidence = _get_ocr_confidence(image)

        results.append({
            "page":           i,
            "text":           text.strip(),
            "source":         source,
            "type":           "pdf_scanned",
            "method":         "tesseract_ocr",
            "has_tables":     False,   # Table detection on scans needs extra work
            "ocr_confidence": confidence,
        })
        print(f"      [OCR] Page {i}/{len(images)} — confidence: {confidence}%")

    return results


def _preprocess_image(image):
    """
    Pre-processes image before OCR to improve accuracy.
    Steps: grayscale → sharpen → boost contrast.
    """
    from PIL import ImageEnhance, ImageFilter

    image = image.convert("L")                  # Convert to grayscale
    image = image.filter(ImageFilter.SHARPEN)   # Sharpen edges
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)               # Boost contrast 2x

    return image


def _get_ocr_confidence(image) -> int:
    """
    Returns average Tesseract confidence score for the page (0–100).
    Returns -1 if confidence scoring fails.
    """
    try:
        import pytesseract
        data = pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT,
            config="--psm 6"
        )
        confidences = [
            int(c) for c in data["conf"]
            if str(c).isdigit() and int(c) > 0
        ]
        if confidences:
            return round(sum(confidences) / len(confidences))
    except Exception:
        pass
    return -1