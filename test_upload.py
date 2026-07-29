"""Quick test to verify the upload API works correctly."""
import sys
sys.path.insert(0, 'Lib/site-packages')
sys.stdout.reconfigure(encoding='utf-8')

import urllib.request
import json

boundary = b'----Boundary12345'
with open('SellList-R1-MBBS-BDS.pdf', 'rb') as f:
    pdf_data = f.read()

header = (
    b'--' + boundary + b'\r\n'
    b'Content-Disposition: form-data; name="file"; filename="test.pdf"\r\n'
    b'Content-Type: application/pdf\r\n\r\n'
)
footer = b'\r\n--' + boundary + b'--\r\n'
body = header + pdf_data + footer

req = urllib.request.Request('http://localhost:5000/api/upload', data=body, method='POST')
req.add_header('Content-Type', 'multipart/form-data; boundary=' + boundary.decode())

with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

print('Success:', data.get('success'))
print('Colleges:', data.get('total_colleges'))
print('Categories:', data.get('total_categories'))
print()
cats = data.get('categories', [])
print('Category list:')
for cat in cats:
    print(' ', cat)
print()
if 'PH' in cats:
    print('WARNING: Spurious PH found in categories!')
else:
    print('OK: Spurious PH is NOT in categories')

pwd_cats = [c for c in cats if c.startswith('PWD')]
print('PWD categories:', pwd_cats)
