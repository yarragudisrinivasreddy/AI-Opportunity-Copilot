"""Fix corrupted Telugu cmp_ban_p in packs.js (ASCII-only source)."""
from __future__ import annotations

import re
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "packs.js"
text = p.read_text(encoding="utf-8")

# ప్రతిపాదనల న్యాయమైన పోలిక
te_h = "\u0c2a\u0c4d\u0c30\u0c24\u0c3f\u0c2a\u0c3e\u0c26\u0c28\u0c32 \u0c28\u0c4d\u0c2f\u0c3e\u0c2f\u0c2e\u0c48\u0c28 \u0c2a\u0c4b\u0c32\u0c3f\u0c15"
# {n} సిమ్యులేటెడ్ ప్రొవైడర్లు మీ బ్రీఫ్‌కు సమాధానమిచ్చారు.
te_ban = (
    "{n} \u0c38\u0c3f\u0c2e\u0c4d\u0c2f\u0c41\u0c32\u0c47\u0c1f\u0c46\u0c21\u0c4d "
    "\u0c2a\u0c4d\u0c30\u0c4a\u0c35\u0c48\u0c21\u0c30\u0c4d\u0c32\u0c41 "
    "\u0c2e\u0c40 \u0c2c\u0c4d\u0c30\u0c40\u0c2b\u0c4d\u200c\u0c15\u0c41 "
    "\u0c38\u0c2e\u0c3e\u0c27\u0c3e\u0c28\u0c2e\u0c3f\u0c1a\u0c4d\u0c1a\u0c3e\u0c30\u0c41."
)
# నిజమైన ప్రతిపాదన జోడించండి
te_paste = "\u0c28\u0c3f\u0c1c\u0c2e\u0c48\u0c28 \u0c2a\u0c4d\u0c30\u0c24\u0c3f\u0c2a\u0c3e\u0c26\u0c28 \u0c1c\u0c4b\u0c21\u0c3f\u0c02\u0c1a\u0c02\u0c21\u0c3f"
# గరిష్టం 5. {n} / 5 జోడించారు.
te_hint = "\u0c17\u0c30\u0c3f\u0c37\u0c4d\u0c1f\u0c02 5. {n} / 5 \u0c1c\u0c4b\u0c21\u0c3f\u0c02\u0c1a\u0c3e\u0c30\u0c41."

pat = rf'(cmp_ban_h: "{re.escape(te_h)}", )cmp_ban_p: "[^"]+", cmp_h:'
new, n = re.subn(pat, rf'\1cmp_ban_p: "{te_ban}", cmp_h:', text, count=1)
if n != 1:
    raise SystemExit(f"expected 1 TE banner replace, got {n}")
new = new.replace(
    'paste_details: "Add a real proposal", paste_hint: "Up to 5. {n} / 5 pasted."',
    f'paste_details: "{te_paste}", paste_hint: "{te_hint}"',
    1,
)
p.write_text(new, encoding="utf-8")
print("patched TE cmp_ban_p and paste_details")
