"""Scan PDF content to debug metadata extraction."""
import sys
from pathlib import Path
from PyPDF2 import PdfReader
import re

PDF_FOLDER = Path("data/pdfs")

def scan_pdf(pdf_path):
    """Read PDF and show content analysis."""
    print("\n" + "="*70)
    print(f"SCANNING: {pdf_path.name}")
    print("="*70)

    try:
        reader = PdfReader(pdf_path)
        if len(reader.pages) == 0:
            print("[ERROR] No pages found")
            return

        # Get first page text
        page = reader.pages[0]
        text = page.extract_text() or ""

        print(f"\nFirst 300 characters (RAW):")
        print("-" * 70)
        print(repr(text[:300]))  # Show with special chars visible

        print(f"\n\nFirst 500 characters (READABLE):")
        print("-" * 70)
        print(text[:500])

        print(f"\n\nFull first page text:")
        print("-" * 70)
        print(text[:1500])

        # Analyze what we're looking for
        print("\n\n" + "="*70)
        print("METADATA SEARCH ANALYSIS")
        print("="*70)

        # Look for common patterns
        patterns = {
            "Complexity": [
                r'complexity\s*[:=]',
                r'Complexity',
                r'COMPLEXITY',
                r'complex'
            ],
            "Landscape": [
                r'landscape\s*[:=]',
                r'Landscape',
                r'LANDSCAPE',
                r'environment\s*[:=]',
                r'Environment'
            ],
            "Version": [
                r'version\s*[:=]',
                r'Version',
                r'VERSION',
                r'v\d+\.\d+'
            ],
            "WRICEF/ID": [
                r'WRICEF',
                r'wricef',
                r'ID\s*[:=]'
            ]
        }

        for field, patterns_list in patterns.items():
            print(f"\n[{field}]")
            found = False
            for pattern in patterns_list:
                match = re.search(pattern, text[:1000], re.IGNORECASE)
                if match:
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 100)
                    print(f"  FOUND: {pattern}")
                    print(f"  Context: ...{text[start:end]}...")
                    found = True
                    break
            if not found:
                print(f"  NOT FOUND")

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")


if __name__ == "__main__":
    if not PDF_FOLDER.exists():
        print(f"[ERROR] Folder not found: {PDF_FOLDER}")
        sys.exit(1)

    # Get all PDFs
    pdfs = sorted(PDF_FOLDER.glob("*.pdf"))
    if not pdfs:
        print("[ERROR] No PDFs found")
        sys.exit(1)

    print(f"\nFound {len(pdfs)} PDFs")
    print("Scanning first 3 PDFs for content analysis...\n")

    # Scan first 3 PDFs
    for pdf_path in pdfs[:3]:
        scan_pdf(pdf_path)

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print("\nFrom this scan, we can see:")
    print("1. What actual patterns exist in PDFs")
    print("2. Whether Complexity/Landscape fields exist")
    print("3. How to adjust regex patterns")
