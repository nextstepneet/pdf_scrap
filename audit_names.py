"""
Check all wrapped college name instances - are the data rows themselves
being matched correctly or are rows being lost?
Find: what AIR/cat is row 1633 assigned to and is it captured?
"""
import sys, re
sys.path.insert(0, 'Lib/site-packages')
sys.path.insert(0, 'app')
sys.stdout.reconfigure(encoding='utf-8')

import pypdfium2 as pdfium
from extractor import _FLEX_RE, _extract_quota, extract_cutoffs

PDF_PATH = r'SellList-R1-MBBS-BDS.pdf'

with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)

# Find all wrapped name instances and their preceding data lines
print("=== All VVPF / RAMCHANDRA wrapped lines in context ===")
wrap_targets = ["VVPF'S MED", "RAMCHANDRA INST MC", "AHILYANAGAR", "CH.SAMBHAJI"]
for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    lines = text.split('\n')
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if any(t in line for t in wrap_targets):
            m = _FLEX_RE.match(line)
            if m:
                code = m.group(3)
                cat = _extract_quota(m.group(2))
                next_l = lines[i+1].strip() if i+1 < len(lines) else ''
                print(f"  pg={pg_idx+1} code={code} cat={cat!r} name={m.group(4)!r} NEXT={next_l!r}")

doc.close()

# Now run full extract and find codes 1135 and 1365
print("\n\n=== COLLEGES 1135 and 1365 in full extract ===")
recs = extract_cutoffs(PDF_PATH)
for r in recs:
    if r['college_code'] in ('1135', '1365'):
        print(f"  {r['college_code']}: {r['college_name']!r}")
        print(f"    cats: {sorted(r['category_cutoffs'].keys())}")
        print(f"    data: {r['category_cutoffs']}")
