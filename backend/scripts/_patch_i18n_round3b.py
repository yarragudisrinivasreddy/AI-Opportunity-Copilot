# -*- coding: utf-8 -*-
from pathlib import Path
import re
P = Path(r"frontend/src/i18n/packs.js")
t = P.read_text(encoding="utf-8")

def once(old, new):
    global t
    if new.split("advisory_b")[0] in t and "advisory_b" in new and "advisory_b" in t[t.find(old[:40]) if old[:40] in t else 0:]:
        pass
    if new in t:
        return True
    if old not in t:
        print("MISSING", repr(old[:100]))
        return False
    t = t.replace(old, new, 1)
    return True

ok = True
ok &= once(
    'flagged_d: "{name} included text telling the evaluator how to score it. That text was ignored and the proposal was scored on its remaining content.", sim: "Simulated", flag_steer: "Flagged: tried to steer the scoring"',
    'flagged_d: "{name} included text telling the evaluator how to score it. That text was ignored and the proposal was scored on its remaining content.", advisory_b: "Possible instruction-like text. ", advisory_d: "{name} may include wording that looks like an instruction to the AI. It was not hard-flagged; ranking is unchanged.", sim: "Simulated", flag_steer: "Flagged: tried to steer the scoring", flag_advisory: "Possible instruction-like text"',
)
# Hindi - read exact from file
hi_m = re.search(r'flagged_d: "\{name\} [^"]+", sim: "\u0938\u093f\u092e\u094d\u092f\u0941\u0932\u0947\u091f\u0947\u0921", flag_steer: "[^"]+"', t)
print("hi_m", bool(hi_m))
if hi_m and "advisory_b" not in hi_m.group(0):
    old = hi_m.group(0)
    new = old.replace(
        ', sim: "',
        ', advisory_b: "\u0938\u0902\u092d\u0935\u0924\u0903 \u0928\u093f\u0930\u094d\u0926\u0947\u0936 \u091c\u0948\u0938\u093e \u091f\u0947\u0915\u094d\u0938\u094d\u091f\u0964 ", advisory_d: "{name} \u092e\u0947\u0902 AI \u0915\u094b \u0928\u093f\u0930\u094d\u0926\u0947\u0936 \u0926\u0947\u0928\u0947 \u091c\u0948\u0938\u093e \u0936\u092c\u094d\u0926 \u0932\u0917 \u0938\u0915\u0924\u093e \u0939\u0948\u0964 \u0907\u0938\u0947 \u0939\u093e\u0930\u094d\u0921-\u092b\u093c\u094d\u0932\u0948\u0917 \u0928\u0939\u0940\u0902 \u0915\u093f\u092f\u093e \u0917\u092f\u093e; \u0930\u0948\u0902\u0915\u093f\u0902\u0917 \u0935\u0939\u0940 \u0939\u0948\u0964", sim: "',
        1,
    ) + ', flag_advisory: "\u0938\u0902\u092d\u0935\u0924\u0903 \u0928\u093f\u0930\u094d\u0926\u0947\u0936 \u091c\u0948\u0938\u093e \u091f\u0947\u0915\u094d\u0938\u094d\u091f"'
    # simpler approach below
    pass

# Use line-based surgery for te/hi busy and cmp lines
lines = t.splitlines(keepends=True)
out = []
for line in lines:
    if 'busy_p: "\u0c38\u0c3e\u0c27\u0c3e\u0c30\u0c23\u0c02\u0c17\u0c3e \u0c12\u0c15 \u0c28\u0c3f\u0c2e\u0c3f\u0c37\u0c02 \u0c32\u0c4b\u0c2a\u0c47 \u0c2a\u0c21\u0c41\u0c24\u0c41\u0c02\u0c26\u0c3f.' in line or (
        'busy_p:' in line and '\u0c38\u0c3e\u0c27\u0c3e\u0c30\u0c23\u0c02\u0c17\u0c3e' in line and '~17' not in line and '\u0c12\u0c15 \u0c28\u0c3f\u0c2e\u0c3f\u0c37\u0c02' in line
    ):
        line = re.sub(
            r'busy_p: "[^"]+"',
            'busy_p: "' + '\u0c38\u0c3e\u0c27\u0c3e\u0c30\u0c23 \u0c35\u0c47\u0c1a\u0c3f: \u0c2a\u0c4d\u0c30\u0c15\u0c4d\u0c30\u0c3f\u0c2f \u0c2e\u0c4d\u0c2f\u0c3e\u0c2a\u0c4d ~17\u0c38\u0c46, \u0c05\u0c35\u0c15\u0c3e\u0c36\u0c3e\u0c32\u0c41 ~28\u0c38\u0c46, \u0c2a\u0c4d\u0c30\u0c24\u0c3f\u0c2a\u0c3e\u0c26\u0c28\u0c32 \u0c2a\u0c4b\u0c32\u0c3f\u0c15 ~20\u201330\u0c38\u0c46. \u0c0f\u0c26\u0c48\u0c28\u0c3e \u0c35\u0c3f\u0c2b\u0c32\u0c2e\u0c48\u0c24\u0c47 \u0c2e\u0c40 \u0c1f\u0c46\u0c15\u0c4d\u0c38\u0c4d\u0c1f\u0c4d \u0c08 \u0c2a\u0c47\u0c1c\u0c40\u0c32\u0c4b\u0c28\u0c47 \u0c09\u0c02\u0c1f\u0c41\u0c02\u0c26\u0c3f.' + '"',
            line,
            count=1,
        )
    if 'vis_example_cap:' in line and 'vis_live_example_cap' not in line and '\u0c09\u0c26\u0c3e\u0c39\u0c30\u0c23' in line:
        line = line.replace(
            'vis_example_cap:',
            'vis_example_cap:',
        )
        line = line.replace(
            '", vis_busy:',
            '", vis_live_example_cap: "' + '\u0c09\u0c26\u0c3e\u0c39\u0c30\u0c23 \u0c1a\u0c3f\u0c24\u0c4d\u0c30\u0c02 (\u0c2e\u0c40 \u0c2a\u0c4d\u0c30\u0c15\u0c4d\u0c30\u0c3f\u0c2f \u0c28\u0c41\u0c02\u0c1a\u0c3f \u0c30\u0c42\u0c2a\u0c4a\u0c02\u0c26\u0c3f\u0c02\u0c1a\u0c2c\u0c21\u0c32\u0c47\u0c26\u0c41)' + '", vis_busy:',
            1,
        )
    # EN advisory
    if 'flagged_d: "{name} included text' in line and 'advisory_b' not in line:
        line = line.replace(
            '", sim: "Simulated", flag_steer: "Flagged: tried to steer the scoring"',
            '", advisory_b: "Possible instruction-like text. ", advisory_d: "{name} may include wording that looks like an instruction to the AI. It was not hard-flagged; ranking is unchanged.", sim: "Simulated", flag_steer: "Flagged: tried to steer the scoring", flag_advisory: "Possible instruction-like text"',
            1,
        )
    # HI advisory
    if 'flagged_d:' in line and '\u0938\u093f\u092e\u094d\u092f\u0941\u0932\u0947\u091f\u0947\u0921' in line and 'advisory_b' not in line:
        line = line.replace(
            '", sim: "\u0938\u093f\u092e\u094d\u092f\u0941\u0932\u0947\u091f\u0947\u0921", flag_steer: "',
            '", advisory_b: "\u0938\u0902\u092d\u0935\u0924\u0903 \u0928\u093f\u0930\u094d\u0926\u0947\u0936 \u091c\u0948\u0938\u093e \u091f\u0947\u0915\u094d\u0938\u094d\u091f\u0964 ", advisory_d: "{name} \u092e\u0947\u0902 AI \u0915\u094b \u0928\u093f\u0930\u094d\u0926\u0947\u0936 \u0926\u0947\u0928\u0947 \u091c\u0948\u0938\u093e \u0936\u092c\u094d\u0926 \u0932\u0917 \u0938\u0915\u0924\u093e \u0939\u0948\u0964 \u0907\u0938\u0947 \u0939\u093e\u0930\u094d\u0921-\u092b\u093c\u094d\u0932\u0948\u0917 \u0928\u0939\u0940\u0902 \u0915\u093f\u092f\u093e \u0917\u092f\u093e; \u0930\u0948\u0902\u0915\u093f\u0902\u0917 \u0935\u0939\u0940 \u0939\u0948\u0964", sim: "\u0938\u093f\u092e\u094d\u092f\u0941\u0932\u0947\u091f\u0947\u0921", flag_steer: "',
            1,
        )
        if 'flag_advisory' not in line:
            # append before weeks_inf
            line = line.replace(
                '", weeks_inf:',
                '", flag_advisory: "\u0938\u0902\u092d\u0935\u0924\u0903 \u0928\u093f\u0930\u094d\u0926\u0947\u0936 \u091c\u0948\u0938\u093e \u091f\u0947\u0915\u094d\u0938\u094d\u091f", weeks_inf:',
                1,
            )
    # TE advisory
    if 'flagged_d:' in line and '\u0c38\u0c3f\u0c2e\u0c4d\u0c2f\u0c41\u0c32\u0c47\u0c1f\u0c46\u0c21\u0c4d' in line and 'advisory_b' not in line:
        line = line.replace(
            '", sim: "\u0c38\u0c3f\u0c2e\u0c4d\u0c2f\u0c41\u0c32\u0c47\u0c1f\u0c46\u0c21\u0c4d", flag_steer: "',
            '", advisory_b: "\u0c38\u0c42\u0c1a\u0c28\u0c32\u0c3e \u0c15\u0c28\u0c3f\u0c2a\u0c3f\u0c02\u0c1a\u0c47 \u0c1f\u0c46\u0c15\u0c4d\u0c38\u0c4d\u0c1f\u0c4d \u0c09\u0c02\u0c21\u0c35\u0c1a\u0c4d\u0c1a\u0c41. ", advisory_d: "{name}\u0c32\u0c4b AI\u0c15\u0c3f \u0c06\u0c26\u0c47\u0c36\u0c02\u0c32\u0c3e \u0c15\u0c28\u0c3f\u0c2a\u0c3f\u0c02\u0c1a\u0c47 \u0c2e\u0c3e\u0c1f\u0c32\u0c41 \u0c09\u0c02\u0c21\u0c35\u0c1a\u0c4d\u0c1a\u0c41. \u0c39\u0c3e\u0c30\u0c4d\u0c21\u0c4d-\u0c2b\u0c4d\u0c32\u0c3e\u0c17\u0c4d \u0c15\u0c3e\u0c32\u0c47\u0c26\u0c41; \u0c30\u0c4d\u0c2f\u0c3e\u0c02\u0c15\u0c3f\u0c02\u0c17\u0c4d \u0c2e\u0c3e\u0c30\u0c26\u0c41.", sim: "\u0c38\u0c3f\u0c2e\u0c4d\u0c2f\u0c41\u0c32\u0c47\u0c1f\u0c46\u0c21\u0c4d", flag_steer: "',
            1,
        )
        if 'flag_advisory' not in line:
            line = line.replace(
                '", weeks_inf:',
                '", flag_advisory: "\u0c38\u0c42\u0c1a\u0c28\u0c32\u0c3e \u0c15\u0c28\u0c3f\u0c2a\u0c3f\u0c02\u0c1a\u0c47 \u0c1f\u0c46\u0c15\u0c4d\u0c38\u0c4d\u0c1f\u0c4d", weeks_inf:',
                1,
            )
    out.append(line)

P.write_text(''.join(out), encoding='utf-8')
# verify
v = P.read_text(encoding='utf-8')
checks = [
    'Possible instruction-like text',
    'vis_live_example_cap',
    '~17s',
    '~17',
]
for c in checks:
    print(c, v.count(c))
