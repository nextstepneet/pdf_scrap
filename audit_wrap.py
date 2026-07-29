"""
Investigates:
1. College name wrapping / multi-line names
2. What lines appear around AHILYANAGAR 
3. How many data rows have wrapped names
4. What is actually being missed from YCM DC college (2134)
"""
import sys, re
sys.path.insert(0, 'Lib/site-packages')
sys.path.insert(0, 'app')
sys.stdout.reconfigure(encoding='utf-8')

import pypdfium2 as pdfium
from extractor import _FLEX_RE, _SKIP_PREFIXES, _extract_quota

PDF_PATH = r'SellList-R1-MBBS-BDS.pdf'

with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)

# Find all pages with AHILYANAGAR 
ahi_found = False
for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()

    if 'AHILYANAGAR' not in text and 'CH.SAMBHAJI' not in text:
        continue
    
    lines = text.split('\n')
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if 'AHILYANAGAR' in line or 'CH.SAMBHAJI' in line:
            print(f"\n=== PAGE {pg_idx+1}, context around line {i} ===")
            for j in range(max(0, i-3), min(len(lines), i+4)):
                marker = '>>>' if j == i else '   '
                l = lines[j].strip()
                m = _FLEX_RE.match(l)
                matched = 'MATCH' if m else 'no-match'
                print(f"  {marker} [{matched}] {l!r}")
            break  # only show first match per page
    
    if pg_idx > 50:
        # Only scan first 50 pages for context
        break

doc.close()

# Now: check what data we're missing for college 2134
print("\n\n=== DATA FROM COLLEGE 2134 (AHILYANAGAR) ===")
with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)
c2134_data = {}
c2134_rows = 0
for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line: continue
        m = _FLEX_RE.match(line)
        if m and m.group(3) == '2134':
            cat = _extract_quota(m.group(2))
            air = int(m.group(1))
            c2134_rows += 1
            if cat:
                if cat not in c2134_data or air > c2134_data[cat]:
                    c2134_data[cat] = air
doc.close()

print(f"  Rows matched for 2134: {c2134_rows}")
print(f"  Categories found: {sorted(c2134_data.keys())}")
print(f"  Full data: {c2134_data}")

# Compare with extractor full output
print("\n\n=== COMPARING WITH FULL EXTRACTOR OUTPUT ===")
from extractor import extract_cutoffs
recs = extract_cutoffs(PDF_PATH)
r2134 = next((r for r in recs if r['college_code'] == '2134'), None)
if r2134:
    print(f"  College: {r2134['college_name']}")
    print(f"  Categories: {sorted(r2134['category_cutoffs'].keys())}")
    print(f"  Full data: {r2134['category_cutoffs']}")
else:
    print("  NOT FOUND in output!")

# Also check: what does the "wrapped" line look like?
# Re-examine with a wider regex that allows optional college code
print("\n\n=== TESTING WRAPPED-NAME REGEX ===")
# A wrapped-name row might look like:
# " 123 456 RollNo AppNo CANDIDATE NAME M OBC 2134:YCM DC"
# followed by next line: "AHILYANAGAR(A'NAGAR)"
# OR the regex might catch "2134:YCM DC" without the rest of the name

_WRAPPED_RE = re.compile(
    r'^\s*\d+\s+'
    r'(\d+)\s+'
    r'\d+\s+'
    r'\d+\s+'
    r'.+?\s+'
    r'[MF]\s+'
    r'(.+?)\s+'
    r'(\d{4})\s*:\s*(.*)$'   # allows empty college name
)

with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)
wrapped_found = 0
for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    lines = text.split('\n')
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line: continue
        m_full = _FLEX_RE.match(line)
        m_wrap = _WRAPPED_RE.match(line)
        if m_wrap and not m_full:
            # Potential wrapped college name
            college_name_part = m_wrap.group(4).strip()
            next_line = lines[i+1].strip() if i+1 < len(lines) else ''
            if wrapped_found < 10:
                print(f"  WRAPPED? code={m_wrap.group(3)} cat={m_wrap.group(2)!r} name_so_far={college_name_part!r} next_line={next_line!r}")
            wrapped_found += 1
doc.close()
print(f"\n  Total potential wrapped lines: {wrapped_found}")
