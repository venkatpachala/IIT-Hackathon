import os
from src.ingest_unstructured import extract_text_from_pdf

# file path
pdf_path = os.path.join("data_input", "test_doc.pdf")

# Check if file exists
if not os.path.exists(pdf_path):
    print(f"ERROR: Please put a PDF file at {pdf_path}")
else:
    # Run extraction
    extracted_text = extract_text_from_pdf(pdf_path)
    
    # Print first 500 characters to verify
    print("\n--- EXTRACTED OUTPUT (PREVIEW) ---")
    print(extracted_text[:1000])
    print("----------------------------------")
