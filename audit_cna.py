"""
Scan specific patterns:
1. Choice Not Available lines - what's the exact format?
2. College name overflow lines - what does data look like around them?
3. Are there data rows being skipped due to college name wrapping?
"""
import sys, re
sys.path.insert(0, 'Lib/site-packages')
sys.path.insert(0, 'app')
sys.stdout.reconfigure(encoding='utf-8')

import pypdfium2 as pdfium

PDF_PATH = r'SellList-R1-MBBS-BDS.pdf'

with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)

# Find pages with 'Choice Not Available'
cna_pages = []
for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    if text and 'Choice Not Available' in text:
        cna_pages.append(pg_idx)
    if len(cna_pages) >= 3:
        break

print("=== Pages with 'Choice Not Available' — showing first 3 pages raw text ===")
for pg_idx in cna_pages[:2]:
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    print(f"\n--- PAGE {pg_idx+1} ---")
    lines = text.split('\n')
    # Find context around CNA lines
    for i, line in enumerate(lines):
        if 'Choice Not Available' in line or 'AHILYANAGAR' in line or 'CH.SAMBHAJI' in line:
            start = max(0, i-2)
            end   = min(len(lines), i+3)
            for j in range(start, end):
                marker = '>>>' if j == i else '   '
                print(f"  {marker} L{j:3d}: {lines[j]!r}")
            print()
    if len([l for l in lines if 'Choice Not Available' in l]) > 5:
        print(f"  (+ more CNA lines on this page)")
        break

# Now look at what a CNA line looks like exactly
print("\n\n=== CHOICE NOT AVAILABLE LINE ANATOMY ===")
# Find 3 representative CNA lines
sample_cna = []
for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    for line in text.split('\n'):
        line = line.strip()
        if 'Choice Not Available' in line and len(sample_cna) < 10:
            sample_cna.append(line)
    if len(sample_cna) >= 10:
        break

# Try to parse them with a CNA-specific regex
_CNA_RE = re.compile(
    r'^\s*(\d+)\s+'          # (1) Sr. No
    r'(\d+)\s+'              # (2) AIR rank
    r'\d+\s+'                # Roll No
    r'\d+\s+'                # App No
    r'.+?\s+'                # Name
    r'([MF])\s+'             # (3) Gender
    r'(.*)$'                 # (4) rest (cat+college or "Choice Not Available")
)

for line in sample_cna:
    m = _CNA_RE.match(line)
    if m:
        print(f"  Sr={m.group(1)} AIR={m.group(2)} Gender={m.group(3)} Rest={m.group(4)!r}")
    else:
        print(f"  NO MATCH: {line!r}")

doc.close()

# Now check: how many CNA lines have category info before "Choice Not Available"?
print("\n\n=== CNA LINES WITH CATEGORY INFO ===")
cna_with_cat = {}
with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)
for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    for line in text.split('\n'):
        line = line.strip()
        if 'Choice Not Available' not in line:
            continue
        # Try to extract cat before "Choice Not Available"
        m = re.match(r'^\s*\d+\s+\d+\s+\d+\s+\d+\s+.+?\s+[MF]\s+(.+?)\s*Choice Not Available\s*$', line, re.IGNORECASE)
        if m:
            cat_part = m.group(1).strip()
            if cat_part:
                cna_with_cat[cat_part] = cna_with_cat.get(cat_part, 0) + 1
doc.close()

print(f"  Total unique cat parts before CNA: {len(cna_with_cat)}")
for cat, cnt in sorted(cna_with_cat.items(), key=lambda x: -x[1])[:20]:
    print(f"  [{cnt:5d}x] cat={cat!r}")
