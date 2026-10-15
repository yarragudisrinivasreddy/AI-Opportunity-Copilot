import json, sys
from pathlib import Path
sys.path.insert(0, str(Path("backend")))
from app.core import injection
attacks = json.loads(Path("backend/eval/data/attacks_dev.json").read_text(encoding="utf-8"))["attacks"]
missed = [a["id"] for a in attacks if not injection.scan("We deliver in 8 weeks. " + a["text"]).detected]
# Apex seed text
seeds = list(Path("backend/app/fixtures").rglob("*.json"))
apex_hits = []
for p in seeds:
    t = p.read_text(encoding="utf-8", errors="replace")
    if "apex" in t.lower() or "p_apexml" in t:
        # find proposal texts
        pass
print(json.dumps({"attacks_total": len(attacks), "missed": missed, "recall": f"{len(attacks)-len(missed)}/{len(attacks)}"}))
# scan seeded apex proposal if present
from app.fixtures import loader
props = loader.seeded_proposals()
for pid, text in props.items() if isinstance(props, dict) else []:
    pass
