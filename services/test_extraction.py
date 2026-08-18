"""Test Phase 2 extraction with actual PDF content."""
from pathlib import Path
from PyPDF2 import PdfReader
import re

def extract_complexity_from_content(text: str) -> str:
    if not text:
        return "Unknown"
    patterns = [
        r'complexity\s+(?:[:=\s])*\s*(high|critical)',
        r'complexity\s+(?:[:=\s])*\s*(medium)',
        r'complexity\s+(?:[:=\s])*\s*(low|simple)',
    ]
    text_lower = text.lower()
    if re.search(patterns[0], text_lower, re.IGNORECASE):
        return "High"
    elif re.search(patterns[1], text_lower, re.IGNORECASE):
        return "Medium"
    elif re.search(patterns[2], text_lower, re.IGNORECASE):
        return "Low"
    return "Unknown"

def extract_landscape_from_content(text: str) -> str:
    if not text:
        return "Unknown"
    text_lower = text.lower()
    landscape_match = re.search(r'landscape\s+(?:[:=\s])*\s*([^;\n]+)', text_lower, re.IGNORECASE)
    if landscape_match:
        landscape_value = landscape_match.group(1).strip()
        if 'production' in landscape_value or 's/4hana' in landscape_value:
            return "Production"
        elif 'qa' in landscape_value or 'quality' in landscape_value or 'test' in landscape_value:
            return "QA"
        elif 'dev' in landscape_value or 'development' in landscape_value:
            return "Development"
        else:
            return landscape_value[:30] if landscape_value else "Unknown"
    if re.search(r'environment\s+(?:[:=\s])*\s*production', text_lower, re.IGNORECASE):
        return "Production"
    return "Unknown"

PDF_FOLDER = Path("data/pdfs")

print("\n" + "="*70)
print("TESTING PHASE 2 EXTRACTION")
print("="*70)

pdfs = sorted(PDF_FOLDER.glob("*.pdf"))[:5]

for pdf_path in pdfs:
    try:
        reader = PdfReader(pdf_path)
        text = reader.pages[0].extract_text() or ""

        complexity = extract_complexity_from_content(text)
        landscape = extract_landscape_from_content(text)

        print(f"\n[{pdf_path.name}]")
        print(f"  Complexity: {complexity}")
        print(f"  Landscape: {landscape}")
    except Exception as e:
        print(f"\n[ERROR] {pdf_path.name}: {e}")

print("\n" + "="*70)
print("EXTRACTION TEST COMPLETE")
print("="*70)
