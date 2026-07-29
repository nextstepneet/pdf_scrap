"""
Deep audit of the PDF extractor.
Scans every line, shows ALL unique raw cat blocks, what they resolve to,
what lines the regex SKIPS, and what lines don't match the regex at all.
"""
import sys, re
sys.path.insert(0, 'Lib/site-packages')
sys.path.insert(0, 'app')
sys.stdout.reconfigure(encoding='utf-8')

import pypdfium2 as pdfium
from extractor import (
    _extract_quota, _FLEX_RE, _SKIP_PREFIXES, QUOTA_MAP,
    _EMD_RE, _JUNK_PAREN_RE, _HA_WORD_RE, _NOSPACE_W_RE, _MULTI_SPACE_RE,
)

PDF_PATH = r'SellList-R1-MBBS-BDS.pdf'
_QUOTA_VALUES = set(QUOTA_MAP.values())

with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)

# Collect data
matched_lines = {}       # raw_cat -> (result, count)
skipped_lines = {}       # line -> count  (matched skip prefix)
no_match_lines = {}      # line -> count  (not matched by regex, not skipped, not blank)
college_names  = {}      # code -> set of name fragments
total_pages    = len(doc)
total_lines    = 0
blank_lines    = 0
header_lines   = 0
data_lines     = 0
skip_lines_ct  = 0
no_match_ct    = 0

# "Choice Not Available" tracker
choice_na_pages = []
choice_na_college_codes = set()

# Track all unique full raw lines that contain "choice not available"
choice_na_raw_lines = {}

for pg_idx in range(total_pages):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close()
    page.close()

    if not text:
        continue

    for raw_line in text.split('\n'):
        total_lines += 1
        line = raw_line.strip()

        if not line:
            blank_lines += 1
            continue

        # Check "Choice Not Available"
        if 'choice not available' in line.lower():
            choice_na_pages.append(pg_idx + 1)
            choice_na_raw_lines[line] = choice_na_raw_lines.get(line, 0) + 1

        # Check skip prefixes
        if any(line.startswith(p) for p in _SKIP_PREFIXES):
            header_lines += 1
            skipped_lines[line[:100]] = skipped_lines.get(line[:100], 0) + 1
            continue

        if '------' in line or '======' in line:
            skip_lines_ct += 1
            continue

        m = _FLEX_RE.match(line)
        if m:
            data_lines += 1
            air           = int(m.group(1))
            cat_raw       = m.group(2).strip()
            col_code      = m.group(3)
            col_name_raw  = m.group(4).strip()
            # Truncate name at merged next-row
            col_name = re.split(r'\s+\d{1,6}\s+\d{1,7}\s+\d{8,}', col_name_raw)[0].strip()
            college_names.setdefault(col_code, set()).add(col_name)

            result = _extract_quota(cat_raw)
            key = cat_raw
            if key not in matched_lines:
                matched_lines[key] = [result, 0]
            matched_lines[key][1] += 1
        else:
            no_match_ct += 1
            no_match_lines[line[:120]] = no_match_lines.get(line[:120], 0) + 1

doc.close()

# ─── Report ─────────────────────────────────────────────────────────────────
print(f"{'='*70}")
print(f"PDF DEEP AUDIT REPORT")
print(f"{'='*70}")
print(f"Total pages   : {total_pages}")
print(f"Total lines   : {total_lines}")
print(f"  Blank       : {blank_lines}")
print(f"  Header/skip : {header_lines}")
print(f"  Separator   : {skip_lines_ct}")
print(f"  Data (regex): {data_lines}")
print(f"  No-match    : {no_match_ct}")
print()

# ─── Categories summary ───────────────────────────────────────────────────────
all_results = {}
for raw, (res, cnt) in matched_lines.items():
    all_results.setdefault(res, {'count': 0, 'raws': set()})
    all_results[res]['count'] += cnt
    all_results[res]['raws'].add(raw)

print(f"{'='*70}")
print(f"RESOLVED CATEGORIES ({len(all_results)} unique)")
print(f"{'='*70}")
for res in sorted(all_results.keys(), key=lambda x: x or ''):
    info = all_results[res]
    in_map = '✓' if res in _QUOTA_VALUES else '✗ NOT IN MAP'
    print(f"  {in_map}  {res!r}  (rows: {info['count']})")
    # Show raw variants if multiple
    raws = sorted(info['raws'])
    if len(raws) > 1 or (raws and list(raws)[0] != res):
        for r in raws[:5]:
            print(f"        raw: {r!r}")

print()

# ─── Lines NOT matched by regex ───────────────────────────────────────────────
print(f"{'='*70}")
print(f"LINES NOT MATCHED BY REGEX ({no_match_ct} total, {len(no_match_lines)} unique)")
print(f"{'='*70}")
# Show first 60 unique non-matched lines
for line, cnt in sorted(no_match_lines.items(), key=lambda x: -x[1])[:60]:
    print(f"  [{cnt:4d}x] {line!r}")

print()

# ─── Choice Not Available ─────────────────────────────────────────────────────
print(f"{'='*70}")
print(f"CHOICE NOT AVAILABLE")
print(f"{'='*70}")
print(f"  Total occurrences: {len(choice_na_pages)}")
print(f"  Unique page numbers: {sorted(set(choice_na_pages))[:20]}")
print()
print("  Unique raw lines:")
for line, cnt in sorted(choice_na_raw_lines.items(), key=lambda x: -x[1])[:30]:
    print(f"  [{cnt:4d}x] {line!r}")

print()

# ─── Colleges ────────────────────────────────────────────────────────────────
print(f"{'='*70}")
print(f"COLLEGES ({len(college_names)} found)")
print(f"{'='*70}")
for code in sorted(college_names.keys()):
    names = sorted(college_names[code], key=len, reverse=True)
    best  = names[0]
    print(f"  {code}: {best!r}  ({len(names)} name variants)")
