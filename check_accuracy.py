import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
sys.stdout.reconfigure(encoding="utf-8")

import pypdfium2 as pdfium
from extractor import _SKIP_PREFIXES, _FLEX_RE, _extract_quota

def measure_accuracy(pdf_path: str):
    total_data_rows_estimated = 0
    successfully_parsed_rows = 0
    unmatched_rows = []

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    doc = pdfium.PdfDocument(pdf_bytes)
    
    # basic regex to detect a line that starts with a number (likely a data row)
    looks_like_data_re = re.compile(r"^\s*\d+\s+\d+") 

    try:
        for pg_idx in range(len(doc)):
            page = doc[pg_idx]
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            textpage.close()
            page.close()

            if not text:
                continue

            for raw_line in text.split("\n"):
                line = raw_line.strip()

                if not line:
                    continue
                if any(line.startswith(p) for p in _SKIP_PREFIXES):
                    continue
                if "------" in line or "======" in line:
                    continue

                if looks_like_data_re.match(line):
                    if "Choice Not Available" in line or "Retained" in line or "joined" in line.lower():
                        continue
                    
                    total_data_rows_estimated += 1
                    m = _FLEX_RE.match(line)
                    if m:
                        cat_quota_raw = m.group(2).strip()
                        quota = _extract_quota(cat_quota_raw)
                        if quota:
                            successfully_parsed_rows += 1
                        else:
                            unmatched_rows.append((line, "Failed quota extraction"))
                    else:
                        unmatched_rows.append((line, "Failed regex match"))

    finally:
        doc.close()

    print(f"Total estimated data rows: {total_data_rows_estimated}")
    print(f"Successfully parsed rows: {successfully_parsed_rows}")
    
    if total_data_rows_estimated > 0:
        accuracy = (successfully_parsed_rows / total_data_rows_estimated) * 100
        print(f"Accuracy: {accuracy:.4f}%")
    
    if unmatched_rows:
        print(f"\nSample of {min(10, len(unmatched_rows))} unmatched rows:")
        for r, reason in unmatched_rows[:10]:
            print(f"[{reason}] {r}")

if __name__ == "__main__":
    measure_accuracy(r"e:\NextStepNeet\SellList-R1-MBBS-BDS.pdf")
