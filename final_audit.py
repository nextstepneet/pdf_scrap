"""
Final comprehensive audit - find ALL data being missed:
1. College name fix (truncated names)
2. What categories in CNA lines we're skipping 
3. What SOBC, D1HA, SEBCD1, etc. resolve to
4. Full list of unique cat blocks and their resolutions
"""
import sys, re
sys.path.insert(0, 'Lib/site-packages')
sys.path.insert(0, 'app')
sys.stdout.reconfigure(encoding='utf-8')

import pypdfium2 as pdfium
from extractor import _extract_quota, _FLEX_RE, _SKIP_PREFIXES, QUOTA_MAP, sort_categories

PDF_PATH = r'SellList-R1-MBBS-BDS.pdf'
_QUOTA_VALUES = set(QUOTA_MAP.values())

with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)

# ── 1. All unique cat raw blocks and their resolutions ──
cat_resolutions = {}  # raw -> result
college_names_all = {}  # code -> set of names

# ── 2. CNA category analysis ──
cna_cats_full = {}  # cat_raw -> count (cat before "Choice Not Available")
# Pattern for CNA lines
_CNA_RE = re.compile(
    r'^\s*\d+\s+\d+\s+\d+\s+\d+\s+.+?\s+[MF]\s+(.+?)\s*Choice Not Available\s*$',
    re.IGNORECASE
)

for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    if not text:
        continue
    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line:
            continue
        # Try CNA pattern first
        mc = _CNA_RE.match(line)
        if mc:
            cat_part = mc.group(1).strip()
            cna_cats_full[cat_part] = cna_cats_full.get(cat_part, 0) + 1
            continue
        # Normal data row
        if any(line.startswith(p) for p in _SKIP_PREFIXES):
            continue
        if '------' in line or '======' in line:
            continue
        m = _FLEX_RE.match(line)
        if m:
            cat_raw = m.group(2).strip()
            col_code = m.group(3)
            col_name_raw = m.group(4).strip()
            col_name = re.split(r'\s+\d{1,6}\s+\d{1,7}\s+\d{8,}', col_name_raw)[0].strip()
            college_names_all.setdefault(col_code, set()).add(col_name)
            result = _extract_quota(cat_raw)
            if cat_raw not in cat_resolutions:
                cat_resolutions[cat_raw] = result

doc.close()

print("=" * 70)
print("COMPLETE CATEGORY MAP (all unique raw blocks)")
print("=" * 70)
for raw, result in sorted(cat_resolutions.items(), key=lambda x: (x[1] or '', x[0])):
    status = '✓' if result in _QUOTA_VALUES else '✗ NOT IN MAP'
    print(f"  {status}  {raw!r:60s} -> {result!r}")

print(f"\nTotal unique raw cat blocks: {len(cat_resolutions)}")
print(f"Total unique resolved cats: {len(set(cat_resolutions.values()))}")

# ── CNA categories ──
print("\n" + "=" * 70)
print("CATEGORY PARTS IN 'CHOICE NOT AVAILABLE' LINES")
print("=" * 70)
print("(These are the caste/quota of students who got NO seat)")
print()
for cat, cnt in sorted(cna_cats_full.items(), key=lambda x: -x[1])[:40]:
    result = _extract_quota(cat) if cat else None
    print(f"  [{cnt:6d}x] cat={cat!r:40s} -> {result!r}")

# ── College names ──
print("\n" + "=" * 70)
print("COLLEGE NAMES (full list with all variants)")
print("=" * 70)
truncated = {}  # code -> (short_name, full_names)
for code, names in sorted(college_names_all.items()):
    best = max(names, key=len)
    worst = min(names, key=len)
    if len(best) > len(worst) + 2:
        truncated[code] = (worst, best, names)
    print(f"  {code}: {best!r}  (variants: {len(names)})")

if truncated:
    print(f"\n{'='*70}")
    print("COLLEGES WITH TRUNCATED NAMES (name wrapping found)")
    print(f"{'='*70}")
    for code, (short, full, all_names) in truncated.items():
        print(f"  {code}: shortest={short!r}  longest={full!r}")
