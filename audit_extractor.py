import sys, time
sys.path.insert(0, 'E:/NextStepNeet/Lib/site-packages')
sys.path.insert(0, 'E:/NextStepNeet/app')
from extractor import extract_cutoffs, _extract_quota

TESTS = [
    ('NTB(W)',          'NT-B (W)'),
    ('NTB (W)',         'NT-B (W)'),
    ('NTBW',            'NT-B (W)'),
    ('NTC(W)',          'NT-C (W)'),
    ('NTD(W)',          'NT-D (W)'),
    ('VJA(W)',          'VJ-A (W)'),
    ('OPEN (W)',        'OPEN (W)'),
    ('OPEN(W)',         'OPEN (W)'),
    ('OPENW',           'OPEN (W)'),
    ('OBC (W)',         'OBC (W)'),
    ('OBC(W)',          'OBC (W)'),
    ('OBCW',            'OBC (W)'),
    ('SC(W)',           'SC (W)'),
    ('ST(W)',           'ST (W)'),
    ('SEBC(W)',         'SEBC (W)'),
    ('SBC(W)',          'SBC (W)'),
    ('EWS(W)',          'EWS (W)'),
    ('NTB',             'NT-B'),
    ('NTA',             'NT-A'),
    ('NTA W',           'VJ-A (W)'),
    ('HOPEN',           'HOPEN'),
    ('HOPENW',          'HA-OPEN (W)'),
    ('EMNTBW',          'NT-B (W)'),
    ('EMOBCW',          'OBC (W)'),
    ('EMNTCW',          'NT-C (W)'),
    ('DEF1 W',          'DEF1 (W)'),
    ('D1',              'DEF1'),
    ('D1 (W)',          'DEF1 (W)'),
    ('OBC (W) (EMD)',   'OBC (W)'),
    ('NTB(W) (EMD)',    'NT-B (W)'),
    ('MKB W',           'MKB (W)'),
    ('OPEN MINO',       'OPEN MINO'),
    ('HNTB W',          'HNTB (W)'),
    ('HA NTB (W)',      'NT-B (W)'),
    ('HA OPEN (W)',     'OPEN (W)'),
    ('HNTB',            'HNTB'),
    ('HNTC W',          'HNTC (W)'),
    ('HEWS W',          'HEWS (W)'),
    ('HOBCW',           'HOBC (W)'),
]

print('=' * 70)
print('UNIT TESTS')
print('=' * 70)
passed = 0
failed = []
for inp, expected in TESTS:
    got = _extract_quota(inp)
    ok = got == expected
    if ok:
        passed += 1
    else:
        failed.append((inp, expected, got))
    status = 'PASS' if ok else 'FAIL'
    print(f'  [{status}] {inp!r:30s}  expected={expected!r:20s}  got={got!r}')

print(f'\nResults: {passed}/{len(TESTS)} passed')
if failed:
    print('\nFAILED:')
    for inp, exp, got in failed:
        print(f'  {inp!r} -> expected {exp!r}, got {got!r}')

print()
print('=' * 70)
print('FULL PDF EXTRACTION')
print('=' * 70)
t0 = time.time()
recs = extract_cutoffs(r'e:\NextStepNeet\SellList-R1-MBBS-BDS.pdf')
dt = time.time() - t0

cats = set()
for r in recs:
    cats.update(r['category_cutoffs'].keys())

print(f'Done in {dt:.1f}s | Colleges:{len(recs)} | Categories:{len(cats)}')
print('\nALL CATEGORIES FOUND:')
for c in sorted(cats):
    print(f'  {c!r}')

print('\nGMC MUMBAI (1101) CUTOFFS:')
for r in recs:
    if r['college_code'] == '1101':
        for k, v in sorted(r['category_cutoffs'].items()):
            print(f'  {k}: {v}')
