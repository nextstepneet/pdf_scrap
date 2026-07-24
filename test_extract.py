"""
Test / validation script — runs the real extractor against the PDF
and prints a summary of all colleges and categories found.
Run from the project root:
  cmd /c "set PYTHONPATH=E:/NextStepNeet/Lib/site-packages && C:/Python314/python.exe test_extract.py"
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
sys.stdout.reconfigure(encoding="utf-8")

from extractor import extract_cutoffs

PDF_PATH = r"e:\NextStepNeet\SellList-R1-MBBS-BDS.pdf"
print(f"Starting extraction: {PDF_PATH}\n")

t0 = time.time()
records = extract_cutoffs(PDF_PATH)
dt = time.time() - t0

all_cats = set()
for r in records:
    all_cats.update(r["category_cutoffs"].keys())

print(f"✅ Done in {dt:.2f}s")
print(f"✅ Total colleges  : {len(records)}")
print(f"✅ Total categories: {len(all_cats)}")
print(f"   {sorted(all_cats)}\n")

print("── First 3 colleges (all categories) ──")
for r in records[:3]:
    print(f"\n  [{r['college_code']}] {r['college_name']}")
    for cat, rank in sorted(r["category_cutoffs"].items()):
        print(f"       {cat:<22} → AIR {rank:,}")

print("\n── Colleges that have NT-C (W) cutoff ──")
for r in records:
    v = r["category_cutoffs"].get("NT-C (W)")
    if v:
        print(f"  [{r['college_code']}] {r['college_name']:<45}  NT-C (W) → AIR {v:,}")

print("\n── Colleges that have OBC (W) cutoff ──")
for r in records:
    v = r["category_cutoffs"].get("OBC (W)")
    if v:
        print(f"  [{r['college_code']}] {r['college_name']:<45}  OBC (W) → AIR {v:,}")

print("\n── Colleges with SEBC (W) cutoff ──")
for r in records:
    v = r["category_cutoffs"].get("SEBC (W)")
    if v:
        print(f"  [{r['college_code']}] {r['college_name']:<45}  SEBC (W) → AIR {v:,}")
