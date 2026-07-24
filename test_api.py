"""Get the actual error detail from the 500 response."""
import urllib.request
import json

pdf_path = r'E:\NextStepNeet\SellList-R1-MBBS-BDS.pdf'
boundary = 'FormBoundary7MA4YWxkTrZu0gW'

with open(pdf_path, 'rb') as f:
    file_data = f.read()

part1 = (
    '--' + boundary + '\r\n'
    'Content-Disposition: form-data; name="file"; filename="SellList-R1-MBBS-BDS.pdf"\r\n'
    'Content-Type: application/pdf\r\n\r\n'
).encode()
part2 = '\r\n--' + boundary + '--\r\n'
body = part1 + file_data + part2.encode()

req = urllib.request.Request(
    'http://127.0.0.1:5000/api/upload',
    data=body,
    headers={'Content-Type': 'multipart/form-data; boundary=' + boundary},
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        print("OK:", resp.read().decode()[:500])
except urllib.error.HTTPError as e:
    raw = e.read().decode(errors='replace')
    print(f"HTTP {e.code}:")
    # Find JSON error section
    try:
        data = json.loads(raw)
        print("Error:", data.get('error'))
        print("Trace:", data.get('trace', '')[:2000])
    except Exception:
        print(raw[:3000])
except Exception as e:
    print("Exception:", e)
