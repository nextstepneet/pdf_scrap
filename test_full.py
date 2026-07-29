import sys
sys.path.insert(0, 'Lib/site-packages')
sys.path.insert(0, 'app')
sys.stdout.reconfigure(encoding='utf-8')
from extractor import extract_cutoffs, sort_categories, _extract_quota

print("=== Running full extraction test ===")
recs = extract_cutoffs('SellList-R1-MBBS-BDS.pdf')
cats = set()
for r in recs:
    cats.update(r['category_cutoffs'].keys())
sorted_cats = sort_categories(cats)

print(f'Colleges: {len(recs)}')
print(f'Categories: {len(sorted_cats)}')
print()
print('ALL Categories in order:')
for c in sorted_cats:
    print(' ', c)

# College name check
print()
print('Key college names (should have full city names):')
for r in recs:
    if r['college_code'] in ('1135', '1365', '2134', '1101'):
        print(f"  {r['college_code']}: {r['college_name']!r}")

# PH check
if 'PH' in cats:
    print()
    print('FAIL: Spurious PH still present!')
else:
    print()
    print('PASS: No spurious PH category')

# SOBC check
sobc_found = [(r['college_code'], c) for r in recs for c in r['category_cutoffs'] if 'SOBC' in c.upper()]
if sobc_found:
    print(f'FAIL: SOBC still in results: {sobc_found[:5]}')
else:
    print('PASS: No SOBC in category outputs')

# Specific unit tests
print()
print("=== Unit tests for _extract_quota ===")
test_cases = [
    ('NTC PWD PEM NTC PH (EMR)', 'PWD-NTC'),
    ('OBC PWD PEM OBC PH (EMR)', 'PWD-OBC'),
    ('SC PWD PEM SC PH (EMR)',   'PWD-SC'),
    ('SEBCPWD PEM SEBC PH (EMR)', 'PWD-SEBC'),
    ('SOBC PWD PEM OBC PH (EMR)', 'PWD-OBC'),
    ('OPEN PH', 'PH'),
    ('EWS PWD PWD-EWS PH', 'PWD-EWS'),
    ('OBC PWD PWD-OBC PH', 'PWD-OBC'),
    ('PWD PWD-OPEN PH', 'PWD-OPEN'),
    ('SOBC OPEN', 'OPEN'),
    ('SOBC', 'OBC'),
    ('SEBCHA HSEBC', 'HSEBC'),
    ('OBC HA HOBC', 'HOBC'),
    ('EWS EWS', 'EWS'),
    ('NTB NTB(W)', 'NT-B (W)'),
    ('OBC EMOBCW (EMR)', 'OBC (W)'),
    ('OBC OBC(W)', 'OBC (W)'),
    ('D1 OPEN (W)', 'OPEN (W)'),
    ('OBC HA HEM OBCW (EMR)', 'HOBC (W)'),
    ('EWS HA I.Q.', 'I.Q.'),
    ('EWS I.Q. MINO', 'I.Q. MINO'),
]

all_pass = True
for raw, expected in test_cases:
    result = _extract_quota(raw)
    ok = result == expected
    if not ok:
        all_pass = False
    marker = 'PASS' if ok else 'FAIL'
    print(f"  [{marker}] {raw!r:45s} -> got={result!r}  expected={expected!r}")

print()
if all_pass:
    print('ALL UNIT TESTS PASSED!')
else:
    print('SOME UNIT TESTS FAILED!')
