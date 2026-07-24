"""
Debug: show every raw cat+quota block that produces an I.Q.-related quota,
so we can see what the PDF actually has vs what we're inferring.
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
sys.stdout.reconfigure(encoding="utf-8")

import pypdfium2 as pdfium

_FLEX_RE = re.compile(
    r"^\s*\d+\s+"
    r"(\d+)\s+"
    r"\d+\s+"
    r"\d+\s+"
    r".+?\s+"
    r"[MF]\s+"
    r"(.+?)\s+"
    r"(\d{4})\s*:\s*(.+)$"
)
_EMD_RE   = re.compile(r"\s*\(EMD\)\s*$", re.IGNORECASE)
_JUNK_RE  = re.compile(r"\((?!W\))[^)]+\)", re.IGNORECASE)

PDF = r"e:\NextStepNeet\SellList-R1-MBBS-BDS.pdf"

with open(PDF, "rb") as f:
    pdf_bytes = f.read()

doc = pdfium.PdfDocument(pdf_bytes)
seen = {}   # raw_block -> list of (air, college)

for pg in range(len(doc)):
    page = doc[pg]
    tp   = page.get_textpage()
    text = tp.get_text_range()
    tp.close(); page.close()
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        m = _FLEX_RE.match(line)
        if not m:
            continue
        air  = m.group(1)
        blk  = m.group(2).strip()
        col  = m.group(3)
        name = m.group(4).strip()[:30]
        blk_clean = _EMD_RE.sub("", blk).strip()
        blk_clean = _JUNK_RE.sub("", blk_clean).strip()
        if "I.Q" in blk_clean.upper():
            key = blk_clean
            if key not in seen:
                seen[key] = []
            seen[key].append(f"AIR {air}  {col}:{name}")

doc.close()

print(f"\nAll unique cat+quota blocks containing I.Q. ({len(seen)} distinct):\n")
for blk, examples in sorted(seen.items()):
    print(f"  Block: {blk!r:<30}  ({len(examples)} rows)  e.g. {examples[0]}")
