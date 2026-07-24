import os

def fix():
    with open('top.txt', 'r', encoding='utf-8') as f:
        top_lines = f.readlines()
        
    with open('bottom.txt', 'r', encoding='utf-8') as f:
        bottom_lines = f.readlines()

    # Find the _IQ_RE definition
    top_end = 0
    for i, line in enumerate(top_lines):
        if '_IQ_RE' in line:
            top_end = i + 1
            break
            
    # Include up to _IQ_RE, plus the alias dict and canonical values set
    top_part = "".join(top_lines[:top_end])
    
    middle_part = """
# D1 / D2 / D3 appear as personal-category codes for Defence candidates.
# When no explicit DEFn quota token follows, map them to their DEF quota.
_DEF_ALIAS: dict = {"D1": "DEF1", "D2": "DEF2", "D3": "DEF3"}

# Reverse lookup: canonical display value -> True (used to validate fallback results)
_QUOTA_VALUES: set = set(QUOTA_MAP.values())


def _extract_quota(cat_quota_block: str) -> Optional[str]:
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

# ─────────────────────────────────────────────────────────────────────────────
"""
    
    # We need to make sure the Public API section header doesn't get duplicated
    # bottom_lines starts at def extract_cutoffs
    
    bottom_part = "".join(bottom_lines)
    
    # Clean up garbled chars from bottom_part
    bottom_part = bottom_part.replace('s,?', '⚠️')
    bottom_part = bottom_part.replace('"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?"?', '')
    bottom_part = bottom_part.replace('# \n# Public API\n# \n', '# Public API\n# ─────────────────────────────────────────────────────────────────────────────\n')
    
    full = top_part + middle_part + bottom_part
    
    # Let's fix the remaining unicode mangles in top_part (like ?" and +')
    full = full.replace('?"', '—')
    full = full.replace('+\'', '→')
    
    with open(r'e:\NextStepNeet\app\extractor.py', 'w', encoding='utf-8') as f:
        f.write(full)

if __name__ == '__main__':
    fix()
    print("Done")
