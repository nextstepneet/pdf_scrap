"""Debug: find exact raw blocks for the two problem patterns."""
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

PDF = r"e:\NextStepNeet\SellList-R1-MBBS-BDS.pdf"
with open(PDF, "rb") as f:
    pdf_bytes = f.read()

doc = pdfium.PdfDocument(pdf_bytes)

problem_blocks = {}
choice_na_lines = []

for pg in range(len(doc)):
    page = doc[pg]
    tp   = page.get_textpage()
    text = tp.get_text_range()
    tp.close(); page.close()
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # Issue 2: Choice Not Available
        if "choice not available" in line.lower() or "choice not" in line.lower():
            choice_na_lines.append(line[:120])
        # Issue 1: SEBC(W) blocks - look for (W) with no space before paren
        m = _FLEX_RE.match(line)
        if m:
            blk = m.group(2).strip()
            if "(W)" in blk and " (W)" not in blk:
                key = blk[:50]
                if key not in problem_blocks:
                    problem_blocks[key] = []
                problem_blocks[key].append(line[:100])

doc.close()

print("=== Blocks with (W) but NO space before paren ===")
for blk, examples in sorted(problem_blocks.items()):
    print(f"  {blk!r}  ({len(examples)}x)  e.g.: {examples[0][:80]}")

print(f"\n=== Choice Not Available lines ({len(choice_na_lines)}) ===")
for l in choice_na_lines[:10]:
    print(f"  {l}")
