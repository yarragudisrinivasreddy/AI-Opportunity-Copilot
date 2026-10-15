"""Need-driven follow-up questions (PRD FR-06). Wording personalised from the process, max 5."""
from dataclasses import dataclass
import re

from app.schemas.process import Process

MAX_QUESTIONS = 5

QUESTION_FIELDS = (
    "volume",
    "time_per_unit",
    "exception_handling",
    "data_availability",
    "systems_used",
)

QUESTION_BANK: dict[str, str] = {
    "volume": "Roughly how many items does this process handle per day?",
    "time_per_unit": "About how long does one item take from start to finish?",
    "exception_handling": "What happens when an item fails the check or something goes wrong?",
    "data_availability": "Do you have past records or photos of this work (saved images, logs, spreadsheets)?",
    "systems_used": "What do you use today to record or track this work (paper, spreadsheet, other software)?",
}

_RECORD_HINTS = (
    "record", "write", "writ", "type", "excel", "log", "sheet", "register", "chart",
    "enter", "retype", "day book", "spreadsheet", "paper", "form", "checklist",
)


@dataclass(frozen=True)
class Question:
    field: str
    text: str
    index: int
    total: int


@dataclass(frozen=True)
class _StepCtx:
    text: str
    actor: str
    tool: str


def _clip(s: str, n: int) -> str:
    s = " ".join((s or "").strip().split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _actor_for_step(process: Process, step_text: str) -> str:
    """Actor named in this step only — earliest whole-word match (subject wins over later nouns)."""
    low = step_text.lower()
    best, best_pos = "", len(low) + 1
    for a in process.actors:
        if not a:
            continue
        m = re.search(rf"(?<![a-z0-9]){re.escape(a.lower())}(?![a-z0-9])", low)
        if m and m.start() < best_pos:
            best, best_pos = a, m.start()
    return _clip(best, 40) if best else ""


def _tool_for_step(process: Process, step_text: str) -> str:
    """Tool named in this step only (longest match first)."""
    low = step_text.lower()
    for t in sorted((x for x in process.tools if x), key=lambda x: -len(x)):
        if re.search(rf"(?<![a-z0-9]){re.escape(t.lower())}(?![a-z0-9])", low):
            return _clip(t, 40)
    return ""


def _ctx_at(process: Process, index: int) -> _StepCtx | None:
    if index < 0 or index >= len(process.steps):
        return None
    text = (process.steps[index].text or "").strip()
    if not text:
        return None
    return _StepCtx(
        text=_clip(text, 90),
        actor=_actor_for_step(process, text),
        tool=_tool_for_step(process, text),
    )


def _fail_ctx(process: Process) -> _StepCtx | None:
    for i, step in enumerate(process.steps):
        low = step.text.lower()
        if any(k in low for k in ("fail", "reject", "exception", "wrong", "rework", "phone", "tag")):
            return _ctx_at(process, i)
    return None


def _record_ctx(process: Process) -> _StepCtx | None:
    """Prefer the last recording-like step (often Excel/typing over an earlier paper note)."""
    found: _StepCtx | None = None
    for i, step in enumerate(process.steps):
        low = step.text.lower()
        if any(k in low for k in _RECORD_HINTS):
            found = _ctx_at(process, i)
    if found:
        return found
    if process.steps:
        return _ctx_at(process, min(len(process.steps) - 1, 2))
    return None


def _is_record_keeper(actor: str, record: _StepCtx | None) -> bool:
    """True only when the actor owns the recording step (named in that step)."""
    if not actor or not record:
        return False
    # Must be the actor bound to the record step — not merely mentioned earlier.
    if record.actor and actor.lower() == record.actor.lower():
        return True
    return actor.lower() in (record.text or "").lower()


def personalize_question(field: str, process: Process) -> str:
    """Ask only for a missing fact. Actor/tool are taken from the quoted step."""
    c0 = _ctx_at(process, 0)
    c1 = _ctx_at(process, 1) or c0
    c_last = _ctx_at(process, len(process.steps) - 1) if process.steps else None
    fail = _fail_ctx(process)
    record = _record_ctx(process)
    pain = _clip(process.pain_points[0].text, 70) if process.pain_points else ""

    if field == "volume":
        ctx = c1 or c0
        if ctx and ctx.actor:
            return f"Roughly how many times a day does {ctx.actor} do this step: “{ctx.text}”?"
        if ctx:
            return f"Roughly how many times a day does this step happen: “{ctx.text}”?"
        return QUESTION_BANK["volume"]

    if field == "time_per_unit":
        start, end = c0, c_last or c1
        if start and end and start.text != end.text:
            return (
                f"About how many minutes does one cycle take from "
                f"“{start.text}” through to “{end.text}”?"
            )
        if start:
            return f"About how many minutes does “{start.text}” usually take end to end?"
        return QUESTION_BANK["time_per_unit"]

    if field == "exception_handling":
        ctx = fail
        if ctx and ctx.actor:
            return f"When this happens — “{ctx.text}” — what exactly does {ctx.actor} do next?"
        if pain and c0 and c0.actor:
            return f"When something goes wrong ({pain}), what does {c0.actor} do?"
        if c0 and c0.actor:
            return f"What does {c0.actor} do when a check fails or something goes wrong?"
        return QUESTION_BANK["exception_handling"]

    if field == "data_availability":
        ctx = record or c1 or c0
        if ctx:
            tool_bit = f" in {ctx.tool}" if ctx.tool else ""
            return (
                f"Do you already keep records from “{ctx.text}”{tool_bit} "
                f"— photos, logs, sheets, or files?"
            )
        return QUESTION_BANK["data_availability"]

    if field == "systems_used":
        ctx = record or c1 or c0
        if not ctx:
            return QUESTION_BANK["systems_used"]
        # Only name an actor when that actor owns the recording step.
        if ctx.tool and _is_record_keeper(ctx.actor, ctx):
            return (
                f"Besides {ctx.tool}, what else does {ctx.actor} use today "
                f"when doing “{ctx.text}”?"
            )
        if ctx.tool:
            return (
                f"Besides {ctx.tool}, what else is used today to keep records "
                f"from “{ctx.text}”?"
            )
        if _is_record_keeper(ctx.actor, ctx):
            return f"What tool or system does {ctx.actor} use when doing “{ctx.text}”?"
        return f"What tool or system is used today to keep records from “{ctx.text}”?"

    return QUESTION_BANK.get(field, QUESTION_BANK["volume"])


def next_question(process: Process, answered: dict[str, str]) -> Question | None:
    if len(answered) >= MAX_QUESTIONS:
        return None
    remaining = [
        field for field in process.missing_fields
        if field not in answered and field in QUESTION_BANK
    ]
    if not remaining:
        return None
    field = remaining[0]
    index = len(answered) + 1
    total = min(MAX_QUESTIONS, len(answered) + len(remaining))
    return Question(
        field=field,
        text=personalize_question(field, process),
        index=index,
        total=total,
    )
