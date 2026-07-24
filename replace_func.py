import re

with open(r'e:\NextStepNeet\app\extractor.py', 'rb') as f:
    text = f.read().decode('utf-8', errors='replace')

# The correct extract_quota function code
new_func = """def _extract_quota(cat_quota_block: str) -> Optional[str]:
    \"\"\"
    Solid 7-step quota extraction from the raw cat+quota block.
    
    PDF block format (between Gender and ColCode):
      PersonalCat  [D1|D2|D3]  [HA]  [QuotaCode]
    \"\"\"
    raw = cat_quota_block.strip()

    # ── Step 1: strip trailing (EMD) annotation ───────────────────────────────
    raw = _EMD_RE.sub("", raw).strip()

    # ── Step 2: strip other parenthetical noise — preserve (W) ───────────────
    raw = _JUNK_RE.sub("", raw).strip()

    if not raw:
        return None

    # ── Step 3: I.Q. fast-path ──────────────────────────────────────────────
    # The PDF ALWAYS encodes I.Q. rows as: PersonalCat [HA] [Dx] I.Q. [MINO]
    m_iq = _IQ_RE.match(raw)
    if m_iq:
        return "I.Q. MINO" if m_iq.group(1) else "I.Q."

    # ── Step 4: strip bare "HA" (home-address personal-category flag) ─────────
    raw_clean = _HA_STRIP_RE.sub("", raw).strip() or raw

    # ── Step 5: greedy suffix match against known QUOTA_MAP keys ─────────────
    raw_up = raw_clean.upper()
    padded = " " + raw_up + " "
    for key in _QUOTA_KEYS_SORTED:
        if padded.endswith(" " + key.upper() + " "):
            return QUOTA_MAP[key]

    # ── Step 6: D1 / D2 / D3 alias — last token is a DEF personal-cat code ───
    parts = raw_clean.split()
    if parts and parts[-1].upper() in _DEF_ALIAS:
        return _DEF_ALIAS[parts[-1].upper()]

    # ── Step 7: right-to-left token scan ───────────────────────────────────
    _qmap_upper = {k.upper(): v for k, v in QUOTA_MAP.items()}
    for token in reversed(parts):
        val = _qmap_upper.get(token.upper())
        if val is not None:
            return val

    # ── Step 8: absolute fallback — return last raw token (logged as unknown) ─
    return parts[-1] if parts else None
"""

# Use regex to find and replace the current def _extract_quota
pattern = re.compile(r"def _extract_quota\(cat_quota_block: str\).*?# ──+[\s\n]*# Public API", re.DOTALL)
if pattern.search(text):
    text = pattern.sub(new_func + "\n\n# ─────────────────────────────────────────────────────────────────────────────\n# Public API", text)
else:
    print("Could not find the function to replace using regex!")

# Clean up any leftover corrupted characters in the rest of the file
text = text.replace('+\'', '→')
text = text.replace('\"?\"? ', '── ')
text = text.replace('?\"', '—')
text = text.replace('s,?', '⚠️')
text = text.replace('', '')

with open(r'e:\NextStepNeet\app\extractor.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Replacement complete.")
