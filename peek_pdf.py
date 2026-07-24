"""Quick test script to peek at PDF structure."""
import pdfplumber
import sys

pdf_path = r"e:\NextStepNeet\SellList-R1-MBBS-BDS.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    
    for page_num in range(min(3, len(pdf.pages))):
        page = pdf.pages[page_num]
        print(f"\n{'='*80}")
        print(f"PAGE {page_num+1}")
        print(f"{'='*80}")
        
        # Try tables
        tables = page.extract_tables()
        print(f"  Tables found: {len(tables)}")
        for ti, table in enumerate(tables):
            print(f"\n  Table {ti+1} ({len(table)} rows):")
            for ri, row in enumerate(table[:5]):
                print(f"    Row {ri}: {row}")
        
        # Raw text
        text = page.extract_text()
        if text:
            lines = text.split('\n')[:20]
            print(f"\n  Text (first 20 lines):")
            for line in lines:
                print(f"    {repr(line)}")
