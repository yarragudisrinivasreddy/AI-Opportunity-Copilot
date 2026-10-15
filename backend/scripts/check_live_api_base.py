import json
import re
import urllib.request

cfg = json.loads(urllib.request.urlopen("https://y-srinivasreddy.web.app/api/config", timeout=30).read())
print("config", cfg)
html = urllib.request.urlopen("https://y-srinivasreddy.web.app/", timeout=30).read().decode("utf-8", "replace")
m = re.search(r'src="(/assets/[^"]+\.js)"', html)
print("bundle", m.group(1) if m else None)
if m:
    js = urllib.request.urlopen(
        "https://y-srinivasreddy.web.app" + m.group(1), timeout=30
    ).read().decode("utf-8", "replace")
    am = re.search(r"https://opportunity-copilot-api[^\"']+", js)
    print("api_base", am.group(0) if am else "MISSING")
