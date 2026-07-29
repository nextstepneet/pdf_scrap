"""
extractor.py  —  Maharashtra NEET CAP Round PDF Cutoff Extractor
=================================================================
Extracts college-wise closing AIR ranks per quota/category from the
State Common Eligibility List (SCEL) PDF published by DMER/DGHS.

Design principles
-----------------
* Two-pass, page-by-page text extraction via pypdfium2.
  Pass 1: collect lines → join wrapped college-name continuation lines.
  Pass 2: parse joined lines with _FLEX_RE.
* All normalisation happens in _extract_quota(); the regex pipeline is
  strictly ordered so no step can silently destroy another step's work.
* QUOTA_MAP keys are stored in their canonical, space-normalised form
  (e.g. "NTB (W)" not "NTB(W)") so the lookup is unambiguous.
* Unknown categories are collected and printed for easy discovery of
  new PDF variants.
"""

import re
from collections import defaultdict
from typing import Optional
import pypdfium2 as pdfium
import gc

# ==============================================================================
# Canonical quota map
# ------------------------------------------------------------------------------
# Keys are the EXACT string that _extract_quota() will try to look up after
# all normalisation steps (upper-cased, space-before-(W) inserted, HA stripped,
# EMD / junk stripped).
# Values are the display strings shown in the UI / Excel.
#
# Ordering: longest keys first (enforced at runtime via _QUOTA_KEYS_SORTED).
# ==============================================================================
QUOTA_MAP: dict[str, str] = {

    # ── OPEN / General ─────────────────────────────────────────────────────────
    "OPEN (W) MINO":   "OPEN (W) MINO",
    "OPEN MINO":       "OPEN MINO",
    "OPEN (W)":        "OPEN (W)",
    "OPENW":           "OPEN (W)",    # compact PDF variant (no space, no parens)
    "OPEN":            "OPEN",

    # ── OBC ────────────────────────────────────────────────────────────────────
    "OBC (W)":         "OBC (W)",
    "OBCW":            "OBC (W)",
    "OBC":             "OBC",
    "SOBC":            "OBC",         # "State OBC" — alias used in some PDF rows

    # ── SC / ST ────────────────────────────────────────────────────────────────
    "SC (W)":          "SC (W)",
    "SCW":             "SC (W)",
    "SC":              "SC",
    "ST (W)":          "ST (W)",
    "STW":             "ST (W)",
    "ST":              "ST",

    # ── NT / VJ-A (Nomadic Tribes) ─────────────────────────────────────────────
    # VJ-A  (same as NT-A in Maharashtra)
    "VJ-A (W)":        "VJ-A (W)",
    "VJAW":            "VJ-A (W)",
    "VJA (W)":         "VJ-A (W)",    # VJA(W) → VJA (W) after _NOSPACE_W_RE
    "NTA (W)":         "VJ-A (W)",    # NTA W → NTA (W) after space normalisation
    "VJ-A":            "VJ-A",
    "VJA":             "VJ-A",
    "NT-A (W)":        "VJ-A (W)",
    "NT-A":            "NT-A",
    "NTA":             "NT-A",
    "VJ":              "VJ-A",

    # NT-B
    "NT-B (W)":        "NT-B (W)",
    "NTBW":            "NT-B (W)",
    "NTB (W)":         "NT-B (W)",    # space variant (PDF sometimes has space)
    "NT-B":            "NT-B",
    "NTB":             "NT-B",

    # NT-C
    "NT-C (W)":        "NT-C (W)",
    "NTCW":            "NT-C (W)",
    "NTC (W)":         "NT-C (W)",
    "NT-C":            "NT-C",
    "NTC":             "NT-C",

    # NT-D
    "NT-D (W)":        "NT-D (W)",
    "NTDW":            "NT-D (W)",
    "NTD (W)":         "NT-D (W)",
    "NT-D":            "NT-D",
    "NTD":             "NT-D",

    # ── SEBC / SBC / EWS ───────────────────────────────────────────────────────
    "SEBC (W)":        "SEBC (W)",
    "SEBCW":           "SEBC (W)",
    "SEBC":            "SEBC",
    "SBC (W)":         "SBC (W)",
    "SBCW":            "SBC (W)",
    "SBC":             "SBC",
    "EWS (W)":         "EWS (W)",
    "EWSW":            "EWS (W)",
    "EWS":             "EWS",

    # ── Home-address (HA) variants ─────────────────────────────────────────────
    # Note: bare "HA" prefix is stripped before lookup; these entries handle
    # the compact all-in-one tokens that appear in the PDF.
    "HA-OPEN (W)":     "HA-OPEN (W)",
    "HOPENW":          "HA-OPEN (W)",
    "HOPEN":           "HOPEN",
    "HOBC (W)":        "HOBC (W)",
    "HOBCW":           "HOBC (W)",
    "HOBC (W) MINO":   "HOBC (W) MINO",
    "HOBC":            "HOBC",
    "HSC (W)":         "HSC (W)",
    "HSCW":            "HSC (W)",
    "HSC":             "HSC",
    "HST (W)":         "HST (W)",
    "HSTW":            "HST (W)",
    "HST":             "HST",
    "HNTA (W)":        "HNTA (W)",
    "HNTB (W)":        "HNTB (W)",
    "HNTC (W)":        "HNTC (W)",
    "HNTD (W)":        "HNTD (W)",
    "HVJA (W)":        "HVJA (W)",
    "HVJAW":           "HVJA (W)",
    "HNTA":            "HNTA",
    "HNTB":            "HNTB",
    "HNTC":            "HNTC",
    "HNTD":            "HNTD",
    "HVJA":            "HVJA",
    "HEWS (W)":        "HEWS (W)",
    "HEWS":            "HEWS",
    "HSBC (W)":        "HSBC (W)",
    "HSBC":            "HSBC",
    "HSEBC (W)":       "HSEBC (W)",
    "HSEBC":           "HSEBC",
    # multi-word HA variants
    "HNTA W":          "HNTA (W)",
    "HNTB W":          "HNTB (W)",
    "HNTC W":          "HNTC (W)",
    "HNTD W":          "HNTD (W)",
    "HVJA W":          "HVJA (W)",
    "HOBC W":          "HOBC (W)",
    "HEWS W":          "HEWS (W)",
    "HSBC W":          "HSBC (W)",
    "HSEBC W":         "HSEBC (W)",

    # ── EMD prefix (Early Merit Declaration) ────────────────────────────────────
    # These appear as "EMNTBW", "EMOBCW" etc. — the EM prefix is stripped by
    # _JUNK_RE downstream; we keep them as direct lookups for safety.
    "EMOPEN":          "OPEN",
    "EMOBC":           "OBC",
    "EMNTBW":          "NT-B (W)",
    "EMNTCW":          "NT-C (W)",
    "EMNTDW":          "NT-D (W)",
    "EMVJAW":          "VJ-A (W)",
    "EMOBCW":          "OBC (W)",
    "EMSCW":           "SC (W)",
    "EMSEBCW":         "SEBC (W)",
    "EMOPNW":          "OPEN (W)",
    "EMNTA":           "NT-A",
    "EMNTB":           "NT-B",
    "EMNTC":           "NT-C",
    "EMNTD":           "NT-D",
    "EMVJA":           "VJ-A",
    "EMSC":            "SC",
    "EMST":            "ST",
    "EMSBC":           "SBC",
    "EMSEBC":          "SEBC",
    "EMEWS":           "EWS",
    "EMHA":            "HA",
    "HEMOBCW":         "HOBC (W)",
    "HEM OBCW":        "HOBC (W)",

    # ── DEF (Defence) ──────────────────────────────────────────────────────────
    "DEF1 (W)":        "DEF1 (W)",
    "DEF2 (W)":        "DEF2 (W)",
    "DEF3 (W)":        "DEF3 (W)",
    "DEF1 W":          "DEF1 (W)",
    "DEF2 W":          "DEF2 (W)",
    "DEF3 W":          "DEF3 (W)",
    "D1 (W)":          "DEF1 (W)",
    "D2 (W)":          "DEF2 (W)",
    "D3 (W)":          "DEF3 (W)",
    "DEF1":            "DEF1",
    "DEF2":            "DEF2",
    "DEF3":            "DEF3",
    "D1":              "DEF1",
    "D2":              "DEF2",
    "D3":              "DEF3",
    "DEF":             "DEF",

    # ── PH / PWD ───────────────────────────────────────────────────────────────
    "PH (W)":          "PH (W)",
    "PH":              "PH",
    "PWD-OPEN":        "PWD-OPEN",
    "PWD-OPEN PH":     "PWD-OPEN",
    "PWD-OBC":         "PWD-OBC",
    "PWD-OBC PH":      "PWD-OBC",
    "PWD-SC":          "PWD-SC",
    "PWD-SC PH":       "PWD-SC",
    "PWD-ST":          "PWD-ST",
    "PWD-ST PH":       "PWD-ST",
    "PWD-VJA":         "PWD-VJA",
    "PWD-VJA PH":      "PWD-VJA",
    "PWD-NTB":         "PWD-NTB",
    "PWD-NTB PH":      "PWD-NTB",
    "PWD-NTC":         "PWD-NTC",
    "PWD-NTC PH":      "PWD-NTC",
    "PWD-NTD":         "PWD-NTD",
    "PWD-NTD PH":      "PWD-NTD",
    "PWD-SEBC":        "PWD-SEBC",
    "PWD-SEBC PH":     "PWD-SEBC",
    "PWD-EWS":         "PWD-EWS",
    "PWD-EWS PH":      "PWD-EWS",
    "PWD-SBC":         "PWD-SBC",
    "PWD-SBC PH":      "PWD-SBC",

    # ── PEM (Physically Enabled Merit) variants — EMR/EMD suffix ───────────────
    # Pattern in PDF: "<CASTE> PWD PEM <CASTE> PH (EMR)"
    # After (EMR) and (EMD) stripping → "<CASTE> PWD PEM <CASTE> PH"
    # We normalise PEM <CASTE> PH → PWD-<CASTE> via _PEM_RE below.
    # Direct entries for safety:
    "PEM OPEN PH":     "PWD-OPEN",
    "PEM OBC PH":      "PWD-OBC",
    "PEM SC PH":       "PWD-SC",
    "PEM ST PH":       "PWD-ST",
    "PEM NTC PH":      "PWD-NTC",
    "PEM NTB PH":      "PWD-NTB",
    "PEM NTD PH":      "PWD-NTD",
    "PEM VJA PH":      "PWD-VJA",
    "PEM SEBC PH":     "PWD-SEBC",
    "PEM EWS PH":      "PWD-EWS",
    "PEM SBC PH":      "PWD-SBC",

    # ── NRI ────────────────────────────────────────────────────────────────────
    "NRI":             "NRI",

    # ── MKB ────────────────────────────────────────────────────────────────────
    "MKB (W)":         "MKB (W)",
    "MKB W":           "MKB (W)",
    "MKB":             "MKB",

    # ── Orphan ─────────────────────────────────────────────────────────────────
    # All sub-types (ORPHAN-A, ORPHAN-C, with caste suffixes) collapse to the
    # single canonical value "ORPHAN" so they appear as one column in the output.
    # The worst (highest) AIR across all orphan sub-types is stored per college.
    "ORPHAN-A OBC":    "ORPHAN",
    "ORPHAN-C OBC":    "ORPHAN",
    "ORPHAN-C SC":     "ORPHAN",
    "ORPHAN-C ST":     "ORPHAN",
    "ORPHAN-C SEBC":   "ORPHAN",
    "ORPHAN-A NT2":    "ORPHAN",
    "ORPHAN-C NT1":    "ORPHAN",
    "ORPHAN-C NT2":    "ORPHAN",
    "ORPHAN-C VJ":     "ORPHAN",
    "ORPHAN-A":        "ORPHAN",
    "ORPHAN-C":        "ORPHAN",
    "ORPHANC":         "ORPHAN",
    "ORPHAN":          "ORPHAN",

    # ── I.Q. (Institutional Quota) ─────────────────────────────────────────────
    # MINO sub-type collapses into the single "I.Q." column.
    "I.Q. MINO":       "I.Q.",
    "I.Q.":            "I.Q.",

    # ── NTA W alias (space-separated variant of NTA(W) / VJ-A(W)) ─────────────
    "NTA W":           "VJ-A (W)",
}

# Pre-sort keys longest-first so the endswith() scan always matches the most
# specific key (e.g. "NT-B (W)" before "NT-B").
_QUOTA_KEYS_SORTED: list[str] = sorted(QUOTA_MAP.keys(), key=len, reverse=True)

# Case-insensitive upper lookup cache (rebuilt once at import time)
_QUOTA_MAP_UPPER: dict[str, str] = {k.upper(): v for k, v in QUOTA_MAP.items()}

# Set of all valid canonical values (for unknown-category detection)
_QUOTA_VALUES: set[str] = set(QUOTA_MAP.values())

# ==============================================================================
# Lines to skip in the PDF (header / footer / legend lines)
# ==============================================================================
_SKIP_PREFIXES = (
    "GOVERNMENT", "State Common", "Admissions to Health",
    "PROVISIONAL", "Note:", "Printed On", "Sr. AIR",
    "No. Roll", "Last Date", "Admitting", "This Provisional",
    "Candidate should", "This seat", "be confirmed", "stipulated",
    "Legends",
    # "Choice Not Available" and "I.Q." removed from skip list —
    # they appear mid-line in data rows (not as line prefixes) so
    # the prefix-check would never fire on real data rows anyway,
    # but keeping them would mask bugs if the PDF changes format.
)

# ==============================================================================
# Compiled regexes
# ==============================================================================

# Main data-row pattern (flexible whitespace, handles multi-word college names)
# Groups: (1) AIR  (2) cat+quota block  (3) college code  (4) college name
_FLEX_RE = re.compile(
    r"^\s*\d+\s+"          # Sr. No.  (discarded)
    r"(\d+)\s+"            # (1) AIR rank
    r"\d+\s+"              # Roll No. (discarded)
    r"\d+\s+"              # App No.  (discarded)
    r".+?\s+"              # Candidate name (discarded, non-greedy)
    r"[MF]\s+"             # Gender   (discarded)
    r"(.+?)\s+"            # (2) Category/Quota block  ← key capture
    r"(\d{4})\s*:\s*(.+)$" # (3) College code  (4) College name
)

# "Choice Not Available" row — no college code, candidate made no choices
# Groups: (1) AIR  — we use this to detect and skip these rows early
_CNA_RE = re.compile(
    r"^\s*\d+\s+\d+\s+\d+\s+\d+\s+.+?\s+[MF]\s+.*?Choice\s+Not\s+Available\s*$",
    re.IGNORECASE,
)

# Strip trailing (EMD) marker — must run FIRST before any other cleaning
_EMD_RE = re.compile(r"\s*\(EMD\)\s*$", re.IGNORECASE)

# Strip trailing (EMR) marker (Early Merit Result) — same idea as (EMD)
_EMR_RE = re.compile(r"\s*\(EMR\)\s*$", re.IGNORECASE)

# Strip parenthesised noise EXCEPT (W) — e.g. (PH), (NRI), (OBC) qualifiers
# that appear as suffixes and are NOT the women's quota marker.
# Negative lookahead (?!W\)) protects "(W)".
_JUNK_PAREN_RE = re.compile(r"\((?!W\b)[^)]{1,20}\)", re.IGNORECASE)

# Bare "HA" word standing alone (home-address prefix before the actual quota).
# Must NOT match "HA" that is part of "HOPEN", "HOBC" etc.
_HA_WORD_RE = re.compile(r"(?<!\w)HA(?!\w)", re.IGNORECASE)

# Insert a space between a word-character and "(W)" when the PDF omits it.
# e.g. "NTB(W)" → "NTB (W)",  "SEBC(W)" → "SEBC (W)"
# Must run AFTER junk-stripping (so only standalone (W) remains).
_NOSPACE_W_RE = re.compile(r"(\w)\(W\)", re.IGNORECASE)

# I.Q. line detector
_IQ_RE = re.compile(r"^.*?\bI\.Q\.\b(\s*MINO)?\s*$", re.IGNORECASE)

# Collapse multiple internal spaces to one
_MULTI_SPACE_RE = re.compile(r" {2,}")

# PEM <CASTE> PH pattern: rewrite to PWD-<CASTE>
# Matches things like "PWD PEM NTC PH", "OBC PWD PEM OBC PH" etc.
# Capture group 1 = caste token (OPEN/OBC/SC/ST/NTC/NTB/NTD/VJA/SEBC/EWS/SBC)
_PEM_PH_RE = re.compile(
    r"\bPEM\s+(OPEN|OBC|SC|ST|NTC|NTB|NTD|VJA|VJ-A|SEBC|SBC|EWS)\s+PH\b",
    re.IGNORECASE,
)

# Map from PEM caste token → canonical PWD-xxx key
_PEM_CASTE_MAP: dict[str, str] = {
    "OPEN":  "PWD-OPEN",
    "OBC":   "PWD-OBC",
    "SC":    "PWD-SC",
    "ST":    "PWD-ST",
    "NTC":   "PWD-NTC",
    "NTB":   "PWD-NTB",
    "NTD":   "PWD-NTD",
    "VJA":   "PWD-VJA",
    "VJ-A":  "PWD-VJA",
    "SEBC":  "PWD-SEBC",
    "SBC":   "PWD-SBC",
    "EWS":   "PWD-EWS",
}

# Continuation-line patterns: a line that is ONLY a city/suffix appended to a
# truncated college name from the previous line.  These two are the only known
# cases in the current PDF; add more if new PDFs show similar wrapping.
_NAME_CONTINUATION_RE = re.compile(
    r"^("
    r"AHILYANAGAR\(A'NAGAR\)"    # YCM DC / VVPF suffix
    r"|CH\.SAMBHAJINAGAR"        # RAMCHANDRA INST MC / GMC suffix
    r")\s*$",
    re.IGNORECASE,
)

# Regex to detect lines that start with a new data-row (so we don't accidentally
# merge them as name continuations).
_STARTS_WITH_ROW_RE = re.compile(r"^\s*\d+\s+\d+\s+\d+\s+\d+\s+\S")

# ==============================================================================
# Core normalisation pipeline
# ==============================================================================

def _extract_quota(raw_block: str) -> Optional[str]:
    """
    Normalise the raw category/quota string from one PDF row and return the
    canonical quota name, or None if the block is empty / unrecognised.

    Pipeline (strict order):
      1. Strip leading/trailing whitespace.
      2. Strip trailing (EMD) / (EMR) markers.
      3. Strip parenthesised junk (but NOT "(W)").
      3b. PEM-PH fast path: rewrite "PEM <CASTE> PH" → "PWD-<CASTE>".
      4. Handle I.Q. lines explicitly.
      5. Strip standalone "HA" prefix (home-address indicator).
      6. Insert space before "(W)" when missing: TOKEN(W) → TOKEN (W).
      7. Collapse multi-spaces, strip again.
      8. Longest-key lookup against QUOTA_MAP (case-insensitive).
      9. Fallback: token-by-token scan from right.
     10. Last resort: return last token as-is.
    """
    s = raw_block.strip()
    if not s:
        return None

    # Step 2 – strip (EMD) and (EMR) trailing markers
    s = _EMD_RE.sub("", s).strip()
    s = _EMR_RE.sub("", s).strip()
    if not s:
        return None

    # Step 3 – strip junk parentheses (keep (W))
    s = _JUNK_PAREN_RE.sub("", s).strip()
    if not s:
        return None

    # Step 3b – PEM <CASTE> PH → PWD-<CASTE>
    # Handles blocks like: "NTC PWD PEM NTC PH", "OBC PWD PEM OBC PH" etc.
    m_pem = _PEM_PH_RE.search(s)
    if m_pem:
        caste = m_pem.group(1).upper()
        return _PEM_CASTE_MAP.get(caste, "PWD-" + caste)

    # Step 4 – I.Q. fast path
    m_iq = _IQ_RE.match(s)
    if m_iq:
        return "I.Q. MINO" if m_iq.group(1) else "I.Q."

    # Step 5 – strip bare "HA" prefix (standalone word only)
    s_no_ha = _HA_WORD_RE.sub("", s).strip()
    s = s_no_ha if s_no_ha else s  # keep original if stripping left nothing

    # Step 6 – insert space before (W): TOKEN(W) → TOKEN (W)
    s = _NOSPACE_W_RE.sub(r"\1 (W)", s)

    # Step 7 – collapse any doubled spaces
    s = _MULTI_SPACE_RE.sub(" ", s).strip()
    if not s:
        return None

    s_up = s.upper()

    # Step 8 – longest-key match against the full normalised string
    # We pad with spaces so partial suffix matches don't fire.
    padded = " " + s_up + " "
    for key in _QUOTA_KEYS_SORTED:
        if padded.endswith(" " + key.upper() + " "):
            return QUOTA_MAP[key]

    # Step 9 – token-by-token fallback (right-to-left), combining last two tokens
    # first (handles "NT-B (W)" split as ["NT-B", "(W)"] → join → "NT-B (W)")
    parts = s_up.split()
    if len(parts) >= 2:
        two = " ".join(parts[-2:])
        if two in _QUOTA_MAP_UPPER:
            return _QUOTA_MAP_UPPER[two]
    for token in reversed(parts):
        if token in _QUOTA_MAP_UPPER:
            return _QUOTA_MAP_UPPER[token]

    # Step 10 – unknown: return last token so caller can log it
    return parts[-1] if parts else None


# ==============================================================================
# Category sort order for display
# ==============================================================================

# Weights for the first word of a canonical category name.
# Lower = shown first.
_SORT_ORDER: dict[str, int] = {
    "OPEN":    1,
    "OBC":     2,
    "SC":      3,
    "ST":      4,
    "VJ-A":    5,  "VJ":   5,
    "NT-A":    5,  "NTA":  5,
    "NT-B":    6,  "NTB":  6,
    "NT-C":    7,  "NTC":  7,
    "NT-D":    8,  "NTD":  8,
    "SEBC":    9,
    "SBC":     10,
    "EWS":     11,
    "HA-OPEN": 20, "HOPEN":20,
    "HOBC":    21,
    "HSC":     22,
    "HST":     23,
    "HNTA":    24, "HVJA": 24,
    "HNTB":    25,
    "HNTC":    26,
    "HNTD":    27,
    "HEWS":    28,
    "HSBC":    29,
    "HSEBC":   30,
    "DEF1":    40, "DEF2": 41, "DEF3": 42,
    "DEF":     43,
    "PH":      44,
    "PWD":     45,
    "MKB":     46,
    "NRI":     47,
    "ORPHAN":  48,
    "I.Q.":    49,
}


def sort_categories(cats) -> list[str]:
    """
    Sort category names in a meaningful display order:
    OPEN → OBC → SC/ST → NT/VJ → EWS/SEBC → HA → DEF → others.
    Within each group, (W) variants follow non-(W), and plain < (W) < MINO.
    """
    def _key(c: str):
        c_up = c.upper()
        weight = 99
        for prefix, w in _SORT_ORDER.items():
            if c_up.startswith(prefix):
                weight = w
                break
        # Secondary: non-W < W < MINO
        if "(W) MINO" in c_up:
            secondary = 2
        elif "(W)" in c_up:
            secondary = 1
        else:
            secondary = 0
        return (weight, secondary, c)

    return sorted(cats, key=_key)


# ==============================================================================
# Main extraction function
# ==============================================================================

def extract_cutoffs(pdf_path: str, progress_cb=None) -> list[dict]:
    """
    Parse the Maharashtra NEET CAP SCEL PDF and return a list of records:

        [
          {
            "college_code":     "1101",
            "college_name":     "GMC MUMBAI",
            "category_cutoffs": {"OPEN": 4699, "NT-B": 25503, ...},
          },
          ...
        ]

    The cutoff stored per (college, category) is the **highest (worst) AIR**
    seen for that combination, i.e. the closing/last rank.

    Two-pass approach per page:
      Pass 1 – collect raw lines and join "name continuation" lines (e.g.
               "AHILYANAGAR(A'NAGAR)") that appear on the next line after a
               truncated college name in the data row.
      Pass 2 – parse each (possibly joined) line with _FLEX_RE.
    """
    # college_code → {quota → max_air}
    data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # college_code → college_name
    names: dict[str, str] = {}
    # quotas that didn't resolve to a known canonical value
    unknown_cats: set[str] = set()

    # First get total pages
    tmp_doc = pdfium.PdfDocument(pdf_path)
    total_pages = len(tmp_doc)
    tmp_doc.close()

    chunk_size = 50
    for chunk_start in range(0, total_pages, chunk_size):
        chunk_end = min(chunk_start + chunk_size, total_pages)
        doc = pdfium.PdfDocument(pdf_path)
        try:
            for pg_idx in range(chunk_start, chunk_end):
                if progress_cb and pg_idx % 5 == 0:
                    progress_cb(pg_idx, total_pages)
                    
                page     = doc[pg_idx]
                textpage = page.get_textpage()
                text     = textpage.get_text_range()
                textpage.close()
                page.close()

                if not text:
                    continue

                raw_lines = text.split("\n")

                # ── Pass 1: join name-continuation lines ──────────────────────────
                joined: list[str] = []
                for raw_line in raw_lines:
                    stripped = raw_line.strip()
                    if _NAME_CONTINUATION_RE.match(stripped) and joined:
                        joined[-1] = joined[-1].rstrip() + " " + stripped
                    else:
                        joined.append(raw_line)

                # ── Pass 2: parse joined lines ────────────────────────────────────
                for raw_line in joined:
                    line = raw_line.strip()

                    # Fast skip: blank lines
                    if not line:
                        continue

                    # Skip header / footer / legend boilerplate
                    if any(line.startswith(p) for p in _SKIP_PREFIXES):
                        continue

                    # Skip separator lines
                    if "------" in line or "======" in line:
                        continue

                    # Skip "Choice Not Available" rows — these candidates made no
                    # college choices so there is no college code to record.
                    if _CNA_RE.match(line):
                        continue

                    m = _FLEX_RE.match(line)
                    if not m:
                        continue

                    air           = int(m.group(1))
                    cat_quota_raw = m.group(2).strip()
                    col_code      = m.group(3)

                    # If PDF text merged with the next row, cut it off at the
                    # next Sr. No. pattern  (Sr\d+ AIR Roll AppNo)
                    raw_name = m.group(4).strip()
                    col_name = re.split(r"\s+\d{1,6}\s+\d{1,7}\s+\d{8,}", raw_name)[0].strip()

                    # Prefer longest / most complete college name seen, but cap at
                    # 120 chars to avoid merging glitches
                    if col_code not in names or (
                        len(col_name) > len(names[col_code]) and len(col_name) < 120
                    ):
                        names[col_code] = col_name

                    quota = _extract_quota(cat_quota_raw)
                    if not quota:
                        continue

                    # Closing rank = highest (worst) AIR seen for this cell
                    if air > data[col_code][quota]:
                        data[col_code][quota] = air

                    if quota not in _QUOTA_VALUES:
                        unknown_cats.add(f"{quota!r} (raw={cat_quota_raw!r})")

        finally:
            doc.close()

    records = [
        {
            "college_code":     code,
            "college_name":     names.get(code, code),
            "category_cutoffs": dict(cat_dict),
        }
        for code, cat_dict in sorted(data.items())
    ]

    if unknown_cats:
        print("[extractor] ⚠️  Unknown/new categories found:")
        for u in sorted(unknown_cats):
            print(f"             {u}")

    return records


# ==============================================================================
# CLI / debug entry point
# ==============================================================================
if __name__ == "__main__":
    import time, sys
    sys.stdout.reconfigure(encoding="utf-8")

    pdf = r"e:\NextStepNeet\SellList-R1-MBBS-BDS.pdf"
    t0 = time.time()
    recs = extract_cutoffs(pdf)
    dt = time.time() - t0

    cats: set[str] = set()
    for r in recs:
        cats.update(r["category_cutoffs"].keys())

    print(f"Done in {dt:.2f}s.  Colleges: {len(recs)},  Categories: {len(cats)}")
    print(sort_categories(cats))

    # Show college name check
    print("\nCollege names:")
    for r in recs:
        print(f"  {r['college_code']}: {r['college_name']!r}")