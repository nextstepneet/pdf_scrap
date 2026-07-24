import re
with open(r'e:\NextStepNeet\app\extractor.py', 'rb') as f:
    text = f.read().decode('utf-8', errors='replace')

text = text.replace('+\'', '→')
text = text.replace('"?"? ', '── ')
text = text.replace('?"', '—')
text = text.replace('s,?', '⚠️')

with open(r'e:\NextStepNeet\app\extractor.py', 'w', encoding='utf-8') as f:
    f.write(text)
