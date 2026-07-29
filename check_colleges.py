from app.extractor import extract_cutoffs
recs = extract_cutoffs('SellList-R1-MBBS-BDS.pdf')
print(f'Total Colleges: {len(recs)}')
for r in recs[:30]:
    print(f'{r["college_code"]}: {r["college_name"]}')
