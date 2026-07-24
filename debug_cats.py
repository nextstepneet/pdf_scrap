"""
Debug script: shows every raw cat_quota_block that produced an
unrecognised / fallback category label, so we know exactly what
PDF tokens to add to QUOTA_MAP.
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
sys.stdout.reconfigure(encoding="utf-8")

import pypdfium2 as pdfium
from extractor import QUOTA_MAP, _QUOTA_KEYS_SORTED, _EMD_RE, _JUNK_RE, _FLEX_RE, _SKIP

PDF_PATH = r"e:\NextStepNeet\SellList-R1-MBBS-BDS.pdf"

# ── replicate _extract_quota but return (canonical, raw, used_fallback) ──
def _extract_quota_debug(cat_quota_block):
    raw = cat_quota_block.strip()
    raw = _EMD_RE.sub("", raw).strip()
    raw_up = raw.upper()
    padded = " " + raw_up + " "

    best_pos = -1
    quota_found = None
    for key in _QUOTA_KEYS_SORTED:
        key_up = key.upper()
        pos = padded.rfind(" " + key_up + " ")
        if pos != -1 and pos > best_pos:
            best_pos = pos
            quota_found = QUOTA_MAP[key]

    if quota_found:
        return quota_found, raw, False   # recognised

    # Fallback
    cleaned = _JUNK_RE.sub("", raw).strip()
    if cleaned:
        parts = cleaned.split()
        label = " ".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        return label, raw, True          # fallback / unknown

    return None, raw, True

# ── scan PDF ────────────────────────────────────────────────────────────────
with open(PDF_PATH, "rb") as f:
    pdf_bytes = f.read()

doc = pdfium.PdfDocument(pdf_bytes)

fallback_map = {}   # label -> set of raw blocks that produced it
canonical_map = {}  # label -> set of raw blocks (recognised)

for pg_idx in range(len(doc)):
    page     = doc[pg_idx]
    textpage = page.get_textpage()
    text     = textpage.get_text_range()
    textpage.close()
    page.close()

    if not text:
        continue
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith(_SKIP):
            continue
        if "------" in line or "======" in line:
            continue
        m = _FLEX_RE.match(line)
        if not m:
            continue
        cat_quota_raw = m.group(2).strip()
        label, raw, is_fallback = _extract_quota_debug(cat_quota_raw)
        if label:
            if is_fallback:
                fallback_map.setdefault(label, set()).add(raw)
            else:
                canonical_map.setdefault(label, set()).add(raw)

doc.close()

print("=" * 70)
print("FALLBACK (unrecognised) categories — need to add to QUOTA_MAP")
print("=" * 70)
for label in sorted(fallback_map):
    examples = sorted(fallback_map[label])[:5]
    print(f"\n  Label : '{label}'")
    for ex in examples:
        print(f"    raw : '{ex}'")

print("\n" + "=" * 70)
print("All RECOGNISED canonical categories found in PDF")
print("=" * 70)
print("  " + ", ".join(sorted(canonical_map.keys())))
