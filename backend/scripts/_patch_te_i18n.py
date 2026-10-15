import re
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "packs.js"
t = p.read_text(encoding="utf-8")
# te block starts at te: {
te_start = t.find("te: {")
assert te_start > 0
te_u = t.find("u: {", te_start)
te_s = t.find("}, s: {", te_u)
chunk = t[te_u:te_s]
chunk2 = re.sub(
    r'cmp_ban_p: "[^"]+"',
    'cmp_ban_p: "{n} సిమ్యులేటెడ్ ప్రొవైడర్లు మీ బ్రీఫ్\u200cకు సమాధానమిచ్�ేటెడ్ ప్రొవైడర్లు మీ బ్రీఫ్\u200cకు సమాధానమిచ్చారు."',
    chunk,
    count=1,
)
chunk2 = re.sub(
    r'flagged_d: "[^"]+"',
    'flagged_d: "{name} తనను ఎలా స్కోర్ చేయాలో మూల్యాంకనకర్తకు చెప్పే టెక్స్ట్ చేర్చింది. ఆ టెక్స్ట్\u200cను విస్మరించి, మిగిలిన విషయంపై ప్రతిపాదనను స్కోర్ చేశాం."',
    chunk2,
    count=1,
)
if "paste_details" not in chunk2:
    chunk2 = chunk2.rstrip().rstrip(",") + ', paste_details: "Add a real proposal", paste_hint: "Up to 5. {n} / 5 pasted."'
t = t[:te_u] + chunk2 + t[te_s:]
p.write_text(t, encoding="utf-8")
print("patched te u; paste_details count", t.count("paste_details"))
