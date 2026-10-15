from pathlib import Path

p = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "packs.js"
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
out = []
patched = False
for line in lines:
    if (not patched) and 'vis_h: "చూడండి"' in line and "vis_example_cap" not in line:
        a = 'vis_btn: "కాన్సెప్ట్ చిత్రం చూపండి",'
        b = 'vis_btn: "కాన్సెప్ట్ చిత్రం చూపండి", vis_btn_example: "ఉదాహరణ చిత్రం చూపండి",'
        line = line.replace(a, b, 1)
        line = line.replace(
            "vis_busy:",
            'vis_example_badge: "ఉదాహరణ", vis_example_cap: "AI రూపొందించిన ఉదాహరణ చిత్రం", vis_busy:',
            1,
        )
        patched = True
    out.append(line)
if not patched:
    raise SystemExit("already patched or missing")
p.write_text("".join(out), encoding="utf-8")
print("ok")
