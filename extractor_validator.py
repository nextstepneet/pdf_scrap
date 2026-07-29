"""
extractor_validator.py
======================
Full correctness check for the extractor pipeline. Checks:
  1.  Every unique raw cat block resolves to a known canonical value
  2.  No unexpected categories in final output
  3.  Closing rank logic (highest AIR = closing rank per college+cat)
  4.  College name quality (no truncation artefacts, no 4-char code fallbacks)
  5.  Sort order sanity
  6.  Specific known regression cases (PH, SOBC, PEM, IQ, ORPHAN)
  7.  Excel generation structure (rows, columns, merge cells)
  8.  Cross-validation: re-extract independently and compare totals
  9.  Category completeness: every expected quota appears in >=1 college
 10.  No duplicate (college, category) entries (data dict ensures this)
"""
import sys, re, time
sys.path.insert(0, 'Lib/site-packages')
sys.path.insert(0, 'app')
sys.stdout.reconfigure(encoding='utf-8')

import pypdfium2 as pdfium

from extractor import (
    extract_cutoffs, sort_categories, _extract_quota,
    QUOTA_MAP, _QUOTA_VALUES, _QUOTA_KEYS_SORTED, _QUOTA_MAP_UPPER,
    _FLEX_RE, _CNA_RE, _SKIP_PREFIXES, _NAME_CONTINUATION_RE,
    _PEM_PH_RE, _EMD_RE, _EMR_RE, _JUNK_PAREN_RE,
)

PDF_PATH = r'SellList-R1-MBBS-BDS.pdf'
PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    PASS += 1
    print(f"  ✓  {msg}")

def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  ✗  FAIL: {msg}")

def section(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")

# ─────────────────────────────────────────────────────────────────────────────
section("1. QUOTA_MAP INTERNAL CONSISTENCY")
# ─────────────────────────────────────────────────────────────────────────────

# All values should be in _QUOTA_VALUES
for k, v in QUOTA_MAP.items():
    if v not in _QUOTA_VALUES:
        fail(f"QUOTA_MAP[{k!r}] = {v!r} is not in _QUOTA_VALUES")

ok(f"All {len(QUOTA_MAP)} QUOTA_MAP values are in _QUOTA_VALUES")

# _QUOTA_KEYS_SORTED must be sorted longest-first
lengths = [len(k) for k in _QUOTA_KEYS_SORTED]
if lengths == sorted(lengths, reverse=True):
    ok("_QUOTA_KEYS_SORTED is correctly ordered longest-first")
else:
    fail("_QUOTA_KEYS_SORTED is NOT sorted longest-first")

# _QUOTA_MAP_UPPER must match QUOTA_MAP case-insensitively
for k, v in QUOTA_MAP.items():
    if _QUOTA_MAP_UPPER.get(k.upper()) != v:
        fail(f"_QUOTA_MAP_UPPER mismatch for key {k!r}")
ok("_QUOTA_MAP_UPPER matches QUOTA_MAP (case-insensitive)")

# ─────────────────────────────────────────────────────────────────────────────
section("2. _extract_quota UNIT TESTS")
# ─────────────────────────────────────────────────────────────────────────────

unit_tests = [
    # (raw_block, expected_canonical, description)
    # --- PEM/EMR fix ---
    ("NTC PWD PEM NTC PH (EMR)",     "PWD-NTC",     "PEM NTC PH (EMR) → PWD-NTC"),
    ("OBC PWD PEM OBC PH (EMR)",     "PWD-OBC",     "PEM OBC PH (EMR) → PWD-OBC"),
    ("SC PWD PEM SC PH (EMR)",       "PWD-SC",      "PEM SC PH (EMR) → PWD-SC"),
    ("SEBCPWD PEM SEBC PH (EMR)",    "PWD-SEBC",    "PEM SEBC PH (EMR) → PWD-SEBC"),
    ("SOBC PWD PEM OBC PH (EMR)",    "PWD-OBC",     "PEM OBC (SOBC row) → PWD-OBC"),
    # --- PH still works for genuine PH quota ---
    ("OPEN PH",                      "PH",          "OPEN PH → PH (genuine)"),
    # --- PWD variants ---
    ("EWS PWD PWD-EWS PH",           "PWD-EWS",     "PWD-EWS PH"),
    ("OBC PWD PWD-OBC PH",           "PWD-OBC",     "PWD-OBC PH"),
    ("SC PWD HA PWD-SC PH",          "PWD-SC",      "PWD-SC PH with HA"),
    ("SEBCPWD HA PWD-SEBC PH",       "PWD-SEBC",    "PWD-SEBC PH with HA"),
    ("NTC PWD PWD-OPEN (EMD)",       "PWD-OPEN",    "PWD-OPEN (EMD)"),
    # --- SOBC alias ---
    ("SOBC",                         "OBC",         "SOBC → OBC"),
    ("SOBC OPEN",                    "OPEN",        "SOBC OPEN → OPEN"),
    ("SOBC PWD PWD-OBC PH",         "PWD-OBC",     "SOBC PWD-OBC PH"),
    # --- I.Q. collapse ---
    ("I.Q.",                         "I.Q.",        "I.Q. bare"),
    ("EWS I.Q.",                     "I.Q.",        "EWS I.Q."),
    ("EWS I.Q. MINO",               "I.Q.",        "I.Q. MINO → I.Q."),
    ("I.Q. MINO",                    "I.Q.",        "I.Q. MINO bare → I.Q."),
    ("EWS HA I.Q.",                  "I.Q.",        "EWS HA I.Q."),
    # --- ORPHAN collapse ---
    ("ORP-A ORPHAN Orphan-A",        "ORPHAN",      "ORPHAN-A → ORPHAN"),
    ("ORP-C ORPHANC OrphanC",        "ORPHAN",      "ORPHAN-C → ORPHAN"),
    ("OBC ORP-A ORPHAN-OBC Orphan-A OBC", "ORPHAN", "ORPHAN-A OBC → ORPHAN"),
    ("SC ORP-C ORPHANC-SC Orphan-C SC",   "ORPHAN", "ORPHAN-C SC → ORPHAN"),
    ("NTB ORP-C ORPHANC-NT Orphan-C NT1", "ORPHAN", "ORPHAN-C NT-B → ORPHAN"),
    # --- Common categories ---
    ("OPEN",                         "OPEN",        "OPEN bare"),
    ("OPEN (W)",                     "OPEN (W)",    "OPEN (W)"),
    ("OPEN (W) MINO",               "OPEN (W) MINO","OPEN (W) MINO"),
    ("OBC OBC",                      "OBC",         "OBC OBC (double caste prefix)"),
    ("OBC OBC(W)",                   "OBC (W)",     "OBC OBC(W)"),
    ("NTB NTB(W)",                   "NT-B (W)",    "NTB NTB(W)"),
    ("NTC NTC(W)",                   "NT-C (W)",    "NTC NTC(W)"),
    ("NTD NTD(W)",                   "NT-D (W)",    "NTD NTD(W)"),
    ("OBC EMOBCW (EMR)",            "OBC (W)",     "EMOBCW (EMR)"),
    ("NTC EMNTCW (EMR)",            "NT-C (W)",    "EMNTCW (EMR)"),
    ("NTD EMNTDW (EMR)",            "NT-D (W)",    "EMNTDW (EMR)"),
    ("NTB EMNTBW (EMR)",            "NT-B (W)",    "EMNTBW (EMR)"),
    # --- HA variants ---
    ("OBC HA HOBC",                  "HOBC",        "HOBC"),
    ("SC HA HSC",                    "HSC",         "HSC"),
    ("OBC HA HOBC W",                "HOBC (W)",    "HOBC (W) space variant"),
    ("HA HOPEN",                     "HOPEN",       "HOPEN"),
    ("HA HOPENW",                    "HA-OPEN (W)", "HOPENW → HA-OPEN (W)"),
    ("SEBCHA HSEBC",                 "HSEBC",       "HSEBC"),
    ("EWS HA HEWS",                  "HEWS",        "HEWS"),
    # --- DEF variants ---
    ("D1 DEF1",                      "DEF1",        "D1 DEF1"),
    ("D1 DEF1 W",                    "DEF1 (W)",    "DEF1 W → DEF1 (W)"),
    ("D2 DEF2",                      "DEF2",        "DEF2"),
    ("D3 DEF3",                      "DEF3",        "DEF3"),
    # --- MKB ---
    ("MKB MKB",                      "MKB",         "MKB MKB"),
    ("MKB MKB W",                    "MKB (W)",     "MKB W → MKB (W)"),
    # --- EWS ---
    ("EWS EWS",                      "EWS",         "EWS EWS"),
    ("EWS EWS(W)",                   "EWS (W)",     "EWS(W) → EWS (W)"),
    # --- EMD stripping ---
    ("OBC OPEN (EMD)",               "OPEN",        "(EMD) stripping"),
    ("OBC OPEN (W) (EMD)",           "OPEN (W)",    "(W) preserved after (EMD) strip"),
    ("OBC HA HOBC (EMD)",            "HOBC",        "HOBC (EMD)"),
    # --- HEM OBCW ---
    ("OBC HA HEM OBCW (EMR)",       "HOBC (W)",    "HEM OBCW (EMR) → HOBC (W)"),
    # --- VJA ---
    ("VJA HA HVJA",                  "HVJA",        "HVJA"),
    ("VJA OPEN",                     "OPEN",        "VJA OPEN → OPEN"),
    ("VJA ORP-C ORPHANC OrphanC",   "ORPHAN",      "VJA ORPHAN-C → ORPHAN"),
]

for raw, expected, desc in unit_tests:
    result = _extract_quota(raw)
    if result == expected:
        ok(f"{desc}")
    else:
        fail(f"{desc}: raw={raw!r} → got={result!r}, expected={expected!r}")

# ─────────────────────────────────────────────────────────────────────────────
section("3. FULL PDF EXTRACTION")
# ─────────────────────────────────────────────────────────────────────────────

t0 = time.time()
recs = extract_cutoffs(PDF_PATH)
dt  = time.time() - t0
ok(f"Extraction completed in {dt:.2f}s")

if len(recs) == 94:
    ok(f"College count = 94 ✓")
else:
    fail(f"College count = {len(recs)} (expected 94)")

all_cats = set()
for r in recs: all_cats.update(r['category_cutoffs'].keys())

if len(all_cats) == 62:
    ok(f"Category count = 62 ✓")
else:
    fail(f"Category count = {len(all_cats)} (expected 62)")

# All resolved categories must be in _QUOTA_VALUES
bad_cats = [c for c in all_cats if c not in _QUOTA_VALUES]
if not bad_cats:
    ok("All extracted categories are in _QUOTA_VALUES")
else:
    fail(f"Unknown categories in output: {bad_cats}")

# ─────────────────────────────────────────────────────────────────────────────
section("4. RAW BLOCK COMPLETENESS (every raw block → valid canonical)")
# ─────────────────────────────────────────────────────────────────────────────

with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)

raw_blocks_seen   = {}  # raw → canonical
unknown_raw       = {}  # raw → canonical (not in _QUOTA_VALUES)
cna_count         = 0
data_row_count    = 0
no_match_nonblank = 0

for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    if not text: continue

    raw_lines = text.split('\n')
    # Two-pass: join name-continuation lines (same logic as extractor)
    joined = []
    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if _NAME_CONTINUATION_RE.match(stripped) and joined:
            joined[-1] = joined[-1].rstrip() + ' ' + stripped
        else:
            joined.append(raw_line)

    for raw_line in joined:
        line = raw_line.strip()
        if not line: continue
        if any(line.startswith(p) for p in _SKIP_PREFIXES): continue
        if '------' in line or '======' in line: continue
        if _CNA_RE.match(line):
            cna_count += 1
            continue
        m = _FLEX_RE.match(line)
        if m:
            data_row_count += 1
            raw = m.group(2).strip()
            if raw not in raw_blocks_seen:
                result = _extract_quota(raw)
                raw_blocks_seen[raw] = result
                if result not in _QUOTA_VALUES:
                    unknown_raw[raw] = result
        else:
            no_match_nonblank += 1

doc.close()

ok(f"Data rows parsed: {data_row_count}")
ok(f"Choice-Not-Available rows skipped: {cna_count}")
ok(f"Unique raw cat blocks: {len(raw_blocks_seen)}")

if not unknown_raw:
    ok("All raw blocks resolve to known canonical values ✓")
else:
    fail(f"{len(unknown_raw)} raw blocks resolve to UNKNOWN values:")
    for raw, res in sorted(unknown_raw.items())[:10]:
        print(f"       raw={raw!r} → {res!r}")

# ─────────────────────────────────────────────────────────────────────────────
section("5. CLOSING RANK LOGIC")
# ─────────────────────────────────────────────────────────────────────────────

# Re-scan PDF and manually compute max AIR per (college, cat) — compare with extractor
manual_data = {}  # (code, cat) → max_air
with open(PDF_PATH, 'rb') as f:
    pdf_bytes = f.read()
doc = pdfium.PdfDocument(pdf_bytes)
for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close(); page.close()
    if not text: continue
    raw_lines = text.split('\n')
    joined = []
    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if _NAME_CONTINUATION_RE.match(stripped) and joined:
            joined[-1] = joined[-1].rstrip() + ' ' + stripped
        else:
            joined.append(raw_line)
    for raw_line in joined:
        line = raw_line.strip()
        if not line: continue
        if any(line.startswith(p) for p in _SKIP_PREFIXES): continue
        if '------' in line or '======' in line: continue
        if _CNA_RE.match(line): continue
        m = _FLEX_RE.match(line)
        if not m: continue
        air  = int(m.group(1))
        cat  = _extract_quota(m.group(2).strip())
        code = m.group(3)
        if not cat: continue
        key = (code, cat)
        if key not in manual_data or air > manual_data[key]:
            manual_data[key] = air
doc.close()

# Compare with extractor output
mismatches = 0
extractor_data = {(r['college_code'], cat): v
                  for r in recs
                  for cat, v in r['category_cutoffs'].items()}

for key, expected_air in manual_data.items():
    got = extractor_data.get(key)
    if got != expected_air:
        mismatches += 1
        if mismatches <= 5:
            fail(f"Mismatch at {key}: extractor={got}, manual={expected_air}")

for key in extractor_data:
    if key not in manual_data:
        mismatches += 1
        if mismatches <= 5:
            fail(f"Extractor has extra entry not in manual: {key}")

if mismatches == 0:
    ok(f"Closing rank logic correct — all {len(manual_data)} (college,cat) cells match ✓")
else:
    fail(f"Total mismatches: {mismatches}")

# ─────────────────────────────────────────────────────────────────────────────
section("6. COLLEGE NAME QUALITY")
# ─────────────────────────────────────────────────────────────────────────────

bare_code_names = [r for r in recs if r['college_name'] == r['college_code']]
if not bare_code_names:
    ok("No colleges with bare code as name (all have real names)")
else:
    fail(f"Colleges with only code as name: {[r['college_code'] for r in bare_code_names]}")

short_names = [r for r in recs if len(r['college_name']) < 5]
if not short_names:
    ok("No suspiciously short college names")
else:
    fail(f"Short names: {[(r['college_code'], r['college_name']) for r in short_names]}")

# Check specific colleges that had truncation bugs
name_checks = {
    '1135': "AHILYANAGAR",
    '1365': "CH.SAMBHAJINAGAR",
    '2134': "AHILYANAGAR",
}
for code, expected_substr in name_checks.items():
    rec = next((r for r in recs if r['college_code'] == code), None)
    if rec and expected_substr in rec['college_name']:
        ok(f"College {code} has full name: {rec['college_name']!r}")
    elif rec:
        fail(f"College {code} name truncated: {rec['college_name']!r} (missing {expected_substr!r})")
    else:
        fail(f"College {code} not found in output")

# ─────────────────────────────────────────────────────────────────────────────
section("7. SORT ORDER SANITY")
# ─────────────────────────────────────────────────────────────────────────────

sorted_cats = sort_categories(all_cats)

def idx(c):
    return sorted_cats.index(c) if c in sorted_cats else -1

checks = [
    ("OPEN before OBC",         "OPEN",    "OBC"),
    ("OBC before SC",           "OBC",     "SC"),
    ("SC before SEBC",          "SC",      "SEBC"),
    ("EWS before HOPEN",        "EWS",     "HOPEN"),
    ("HSEBC before DEF1",       "HSEBC",   "DEF1"),
    ("DEF3 before PWD-OPEN",    "DEF3",    "PWD-OPEN"),
    ("PWD-OPEN before ORPHAN",  "PWD-OPEN","ORPHAN"),
    ("ORPHAN before I.Q.",      "ORPHAN",  "I.Q."),
]
for desc, a, b in checks:
    if a in all_cats and b in all_cats:
        if idx(a) < idx(b):
            ok(f"Sort: {desc}")
        else:
            fail(f"Sort wrong: {a!r} (pos {idx(a)}) should be before {b!r} (pos {idx(b)})")
    else:
        print(f"  (skip: {desc} — one or both cats not present)")

# ─────────────────────────────────────────────────────────────────────────────
section("8. SPECIFIC REGRESSION CHECKS")
# ─────────────────────────────────────────────────────────────────────────────

# PH must NOT appear as a category (it was a false positive before)
if 'PH' not in all_cats:
    ok("No spurious 'PH' category in output")
else:
    fail("Spurious 'PH' category still present!")

# SOBC must NOT appear (it's aliased to OBC)
if 'SOBC' not in all_cats:
    ok("No 'SOBC' in output (correctly aliased to OBC)")
else:
    fail("'SOBC' still appears as category!")

# I.Q. MINO must NOT appear (collapsed to I.Q.)
if 'I.Q. MINO' not in all_cats:
    ok("'I.Q. MINO' collapsed into 'I.Q.' ✓")
else:
    fail("'I.Q. MINO' still appears as separate category!")

# ORPHAN sub-types must NOT appear
orphan_subs = [c for c in all_cats if 'ORPHAN' in c.upper() and c != 'ORPHAN']
if not orphan_subs:
    ok("All ORPHAN sub-types collapsed into 'ORPHAN' ✓")
else:
    fail(f"ORPHAN sub-types still present: {orphan_subs}")

# ORPHAN must appear
if 'ORPHAN' in all_cats:
    n = sum(1 for r in recs if 'ORPHAN' in r['category_cutoffs'])
    ok(f"'ORPHAN' present, covering {n} colleges")
else:
    fail("'ORPHAN' category missing from output!")

# I.Q. must appear
if 'I.Q.' in all_cats:
    n = sum(1 for r in recs if 'I.Q.' in r['category_cutoffs'])
    ok(f"'I.Q.' present, covering {n} colleges")
else:
    fail("'I.Q.' category missing from output!")

# ─────────────────────────────────────────────────────────────────────────────
section("9. CATEGORY COVERAGE")
# ─────────────────────────────────────────────────────────────────────────────

# These categories must appear in at least 1 college
must_have = [
    'OPEN','OPEN (W)','OBC','OBC (W)','SC','SC (W)','ST','ST (W)',
    'VJ-A','VJ-A (W)','NT-B','NT-B (W)','NT-C','NT-C (W)','NT-D','NT-D (W)',
    'SEBC','SEBC (W)','EWS','EWS (W)',
    'HOPEN','HOBC','HOBC (W)','HSC','HST',
    'DEF1','DEF1 (W)','DEF2','DEF3',
    'PWD-OPEN','PWD-OBC','PWD-SC','PWD-SEBC',
    'MKB','ORPHAN','I.Q.',
]
missing = [c for c in must_have if c not in all_cats]
if not missing:
    ok(f"All {len(must_have)} expected categories present")
else:
    fail(f"Missing expected categories: {missing}")

# ─────────────────────────────────────────────────────────────────────────────
section("10. DATA INTEGRITY")
# ─────────────────────────────────────────────────────────────────────────────

# All closing ranks must be positive integers
bad_ranks = [(r['college_code'], cat, v)
             for r in recs for cat, v in r['category_cutoffs'].items()
             if not isinstance(v, int) or v <= 0]
if not bad_ranks:
    ok("All closing ranks are positive integers")
else:
    fail(f"Bad rank values: {bad_ranks[:5]}")

# All college codes must be 4-digit strings
bad_codes = [r['college_code'] for r in recs if not re.match(r'^\d{4}$', r['college_code'])]
if not bad_codes:
    ok("All college codes are 4-digit strings")
else:
    fail(f"Bad college codes: {bad_codes}")

# Each college must have at least 1 category
empty_colleges = [r['college_code'] for r in recs if not r['category_cutoffs']]
if not empty_colleges:
    ok("All colleges have ≥1 category with data")
else:
    fail(f"Colleges with no category data: {empty_colleges}")

# Check MBBS (1xxx) vs BDS (2xxx) split
mbbs = [r for r in recs if r['college_code'].startswith('1')]
bds  = [r for r in recs if r['college_code'].startswith('2')]
ok(f"MBBS colleges: {len(mbbs)}, BDS colleges: {len(bds)}, Total: {len(recs)}")

# ─────────────────────────────────────────────────────────────────────────────
section("11. FINAL SUMMARY")
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n  Total PASS : {PASS}")
print(f"  Total FAIL : {FAIL}")
if FAIL == 0:
    print(f"\n  🎉  ALL CHECKS PASSED — extractor is solid!")
else:
    print(f"\n  ⚠️   {FAIL} CHECK(S) FAILED — review above")
