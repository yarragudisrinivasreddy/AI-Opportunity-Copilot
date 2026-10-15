"""Today → after flow rows for opportunities. Code validates and synthesises fallbacks."""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.opportunity import FlowRow
from app.schemas.process import Process


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


_PLACEHOLDER_TODAY = frozenset({
    "n/a", "na", "none", "tbd", "unknown", "-", "—", "a person decides exceptions",
})


def row_grounded(today: str, process: Process) -> bool:
    """True when today's text clearly echoes a confirmed process step."""
    t = _norm(today)
    if not t or t in _PLACEHOLDER_TODAY:
        return False
    for step in process.steps:
        s = _norm(step.text)
        if not s:
            continue
        if t == s or t in s or s in t:
            return True
        words = [w for w in t.split() if len(w) > 4]
        if sum(1 for w in words if w in s) >= 2:
            return True
    return False


def _human_today(process: Process) -> str:
    """Pick a real process step for the oversight row (never N/A)."""
    for step in process.steps:
        low = step.text.lower()
        if any(k in low for k in ("fail", "reject", "exception", "supervisor", "decide", "tag")):
            return step.text[:300]
    if process.steps:
        return process.steps[-1].text[:300]
    return "A person reviews exceptions"


def synthesize_flow(
    *,
    title: str,
    description: str,
    recommendation: str,
    human_oversight_required: bool,
    process: Process | None = None,
    improvement: str | None = None,
    humans_text: str | None = None,
) -> list[FlowRow]:
    """Build 3–5 rows from process steps + this opportunity's improvement / humans copy."""
    steps = process.steps if process else []
    today_a = steps[0].text if steps else f"Today: work related to {title}"
    today_b = steps[1].text if len(steps) > 1 else "Manual follow-up and re-entry"
    today_c = steps[2].text if len(steps) > 2 else "Supervisor reviews exceptions by hand"
    improve = (improvement or description or recommendation or title).strip()[:300]
    after_change = improve or "A clearer digital step for this work"
    # Never use generic “captured once upstream” — tie remove to this opportunity.
    after_remove = f"No longer a separate step — covered by: {after_change[:180]}"
    humans_after = (humans_text or "").strip()[:300] or (
        "A person still reviews exceptions and signs off"
        if human_oversight_required
        else "People stay involved only when something is unclear"
    )
    rows = [
        FlowRow(today=today_a[:300], after=after_change, kind="change"),
        FlowRow(today=today_b[:300], after=after_remove[:300], kind="remove"),
        FlowRow(today=today_c[:300], after=today_c[:300], kind="same"),
    ]
    if human_oversight_required:
        rows.append(
            FlowRow(
                today=_human_today(process) if process else "A person reviews exceptions",
                after=humans_after,
                kind="human",
            )
        )
    return rows[:5]


@dataclass(frozen=True)
class FlowBuildResult:
    rows: list[FlowRow]
    grounded_kept: int
    ungrounded_dropped: int
    synthesized: bool


def validate_or_synthesize_flow(
    rows: list[FlowRow] | None,
    *,
    title: str,
    description: str,
    recommendation: str,
    human_oversight_required: bool,
    process: Process,
    improvement: str | None = None,
    humans_text: str | None = None,
) -> FlowBuildResult:
    """Keep grounded model rows; drop ungrounded. Synthesise only if fewer than 3 grounded remain."""
    synth_kwargs = dict(
        title=title,
        description=description,
        recommendation=recommendation,
        human_oversight_required=human_oversight_required,
        process=process,
        improvement=improvement,
        humans_text=humans_text,
    )

    if not rows:
        return FlowBuildResult(
            rows=synthesize_flow(**synth_kwargs),
            grounded_kept=0,
            ungrounded_dropped=0,
            synthesized=True,
        )

    grounded: list[FlowRow] = []
    dropped = 0
    for r in rows[:5]:
        if r.kind not in ("same", "change", "remove", "human"):
            dropped += 1
            continue
        today = (r.today or "").strip()
        after = (r.after or "").strip()
        if not today or not after:
            dropped += 1
            continue
        # Every row — including human — must ground today in a confirmed step.
        if row_grounded(today, process):
            grounded.append(FlowRow(today=today[:300], after=after[:300], kind=r.kind))
        else:
            dropped += 1

    if len(grounded) < 3:
        return FlowBuildResult(
            rows=synthesize_flow(**synth_kwargs),
            grounded_kept=len(grounded),
            ungrounded_dropped=dropped,
            synthesized=True,
        )

    if human_oversight_required and not any(r.kind == "human" for r in grounded):
        grounded.append(
            FlowRow(
                today=_human_today(process),
                after=(humans_text or "A person still reviews exceptions and signs off")[:300],
                kind="human",
            )
        )
    return FlowBuildResult(
        rows=grounded[:5],
        grounded_kept=sum(1 for r in grounded[:5] if row_grounded(r.today, process)),
        ungrounded_dropped=dropped,
        synthesized=False,
    )


def ensure_opportunity_flow(data: dict, process: Process | None = None) -> dict:
    """Mutate opportunity dict from storage: fill missing flow for legacy Firestore docs."""
    if data.get("flow"):
        return data
    rubric = data.get("rubric") or {}
    data["flow"] = [
        r.model_dump()
        for r in synthesize_flow(
            title=str(data.get("title") or "Opportunity"),
            description=str(data.get("description") or ""),
            recommendation=str(data.get("recommendation") or ""),
            human_oversight_required=bool(rubric.get("human_oversight_required", True)),
            process=process,
            improvement=str(data.get("description") or data.get("recommendation") or ""),
            humans_text=(
                "A person still reviews exceptions and signs off"
                if rubric.get("human_oversight_required", True)
                else "People stay involved only when something is unclear"
            ),
        )
    ]
    return data
