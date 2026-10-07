"""Prompt-injection detection for untrusted text (PRD section 15).

Layer 3 of the defense: rules that flag instruction-like content and strip the offending
segments BEFORE text reaches any model. This is one layer; scoring is done by code regardless.
"""
import base64
import re
import unicodedata
from dataclasses import dataclass, field

_ZERO_WIDTH = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF, 0x00AD], None
)

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "override_instructions",
        re.compile(
            r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|"
            r"all|every|other|system|your)\b.{0,30}\b(instructions?|prompts?|rules?|proposals?|"
            r"bids?|text|context|guidelines?)\b"
        ),
    ),
    (
        "rank_me_first",
        re.compile(
            r"\b(rank|score|rate|select|choose|recommend|prefer|pick)\b.{0,30}\b(me|us|"
            r"this (proposal|provider|bid|vendor|company)|our (proposal|bid))\b.{0,30}"
            r"\b(first|top|highest|best|number one|#1|1st)\b"
        ),
    ),
    (
        "force_score",
        re.compile(
            r"\b(give|assign|award|set|output)\b.{0,25}\b(score|rating|marks?)\b.{0,20}"
            r"\b(100|10/10|maximum|perfect|full marks|1\.0)\b"
        ),
    ),
    ("score_literal", re.compile(r"\b(score|rating)\s*(of|=|:)\s*(100|10/10|1\.0)\b")),
    (
        "dismiss_competitors",
        re.compile(
            r"\b(ignore|exclude|disqualify|reject|penali[sz]e|downgrade)\b.{0,25}\b(the )?"
            r"(other|all other|competing|rival)\b.{0,15}\b(proposals?|bids?|providers?|vendors?)\b"
        ),
    ),
    (
        "fake_role_marker",
        re.compile(
            r"(^|\n|\s)(system|assistant|developer)\s*(message|prompt|instruction|note)?\s*:|"
            r"\[(system|assistant|inst)\]|<\|im_start\|>|<\|system\|>|###\s*(instruction|system)"
        ),
    ),
    ("persona_switch", re.compile(r"\b(you are now|act as|pretend to be|from now on you)\b")),
    (
        "exfiltrate",
        re.compile(
            r"\b(reveal|print|show|repeat|output|leak|disclose|tell me)\b.{0,30}\b(system prompt|"
            r"your instructions|hidden (prompt|instructions)|other proposals?|other bids?|"
            r"brief requirements|api key|secret)\b"
        ),
    ),
    (
        "suppress_flagging",
        re.compile(
            r"\b(do not|don't|never)\b.{0,20}\b(flag|mention|report|penali[sz]e|detect)\b"
        ),
    ),
    (
        "address_the_model",
        re.compile(
            r"\b(note to|attention|dear|message for|instruction for)\b.{0,15}\b(ai|llm|model|"
            r"evaluator|assistant|grader|reviewer bot)\b"
        ),
    ),
    (
        "mark_requirements_met",
        re.compile(
            r"\bmark\b.{0,25}\b(requirements?|criteria)\b.{0,20}\b(covered|met|satisfied|fully)\b"
        ),
    ),
    (
        "force_criteria",
        re.compile(
            r"\b(set|assign|treat)\b.{0,20}\b(timeline|cost|risk|fit|experience)\b.{0,15}"
            r"\b(to|as)\b.{0,12}\b(0|lowest|minimum|best|perfect|maximum)\b"
        ),
    ),
]

_HIDDEN_MARKERS = re.compile(
    r"<!--|-->|display\s*:\s*none|font-size\s*:\s*0|color\s*:\s*(#fff(fff)?|white)|"
    r"visibility\s*:\s*hidden|<\s*script|\\u200b|&#x200b;"
)
_B64 = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")
_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class InjectionReport:
    detected: bool = False
    reasons: list[str] = field(default_factory=list)
    removed_segments: int = 0
    sanitized_text: str = ""


def normalize(text: str) -> str:
    """NFKC, strip zero-width characters, lowercase, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    return re.sub(r"[ \t]+", " ", text).lower()


def _decoded_candidates(segment: str) -> list[str]:
    out: list[str] = []
    for token in _B64.findall(segment):
        try:
            raw = base64.b64decode(token + "=" * (-len(token) % 4), validate=False)
            decoded = raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if decoded and sum(c.isprintable() for c in decoded) / len(decoded) > 0.9:
            out.append(decoded)
    return out


def _segment_reasons(segment: str) -> list[str]:
    reasons: list[str] = []
    norm = normalize(segment)
    for name, pattern in _PATTERNS:
        if pattern.search(norm):
            reasons.append(name)
    if _HIDDEN_MARKERS.search(norm):
        reasons.append("hidden_content_marker")
    for decoded in _decoded_candidates(segment):
        inner = normalize(decoded)
        if any(p.search(inner) for _, p in _PATTERNS):
            reasons.append("encoded_instruction")
    return reasons


def scan(text: str) -> InjectionReport:
    """Flag instruction-like segments and return text with those segments removed."""
    if not text:
        return InjectionReport(sanitized_text="")
    kept: list[str] = []
    reasons: list[str] = []
    removed = 0
    for segment in _SPLIT.split(text):
        if not segment.strip():
            continue
        seg_reasons = _segment_reasons(segment)
        if seg_reasons:
            removed += 1
            reasons.extend(r for r in seg_reasons if r not in reasons)
        else:
            kept.append(segment)
    return InjectionReport(
        detected=removed > 0,
        reasons=reasons,
        removed_segments=removed,
        sanitized_text="\n".join(kept),
    )
