import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import os

# CONFIGURATION
# If you are on Windows and added Tesseract to Path, you can skip this line.
# Otherwise, uncomment and point to your exe:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_pdf(pdf_path):
    """
    1. Tries to extract text directly (for digital PDFs).
    2. If text is empty/garbage, converts pages to images and runs OCR (for scanned PDFs).
    """
    print(f"--- Processing: {pdf_path} ---")
    
    full_text = ""
    is_scanned = False
    
    # METHOD A: Standard Extraction (Fast)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
    except Exception as e:
        print(f"Error reading PDF structure: {e}")

    # METHOD B: Check if Scanned
    # If we got less than 50 characters, it's likely an image/scan.
    if len(full_text.strip()) < 50:
        print(">>> No text found. Detected SCANNED document. Starting OCR... (This takes time)")
        is_scanned = True
        
        try:
            # Convert PDF pages to Images
            # refer to poppler_path if it's not in your System PATH
            images = convert_from_path(pdf_path) 
            
            for i, image in enumerate(images):
                print(f"   OCR-ing Page {i+1}...")
                # Extract text from image
                # lang='eng' (Add 'hin' if you installed Hindi data for Indian context)
                ocr_text = pytesseract.image_to_string(image, lang='eng')
                full_text += ocr_text + "\n"
                
        except Exception as e:
            print(f"OCR Failed. Do you have Poppler installed? Error: {e}")
            return ""

    if is_scanned:
        print(">>> OCR Complete.")
    else:
        print(">>> Native Text Extracted.")
        
    return full_text

# Simple test block
if __name__ == "__main__":
    # Create a dummy file if none exists to test the import
    print("Run main.py to test this module.")