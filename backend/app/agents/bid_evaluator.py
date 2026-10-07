"""Agent 4: three-stage bid evaluator. LLM extracts and explains; CODE scores and ranks."""
import json
import logging
import re

from app.agents.brief import requirement_ids
from app.core import injection, paths, scoring
from app.llm import prompts
from app.llm.client import LLMClient, LLMError, structured_call
from app.schemas.brief import Brief
from app.schemas.proposal import (
    CRITERIA,
    Evaluation,
    ExtractedProposal,
    ExtractedProposalDraft,
    InjectionFlag,
    Proposal,
    RationaleDraft,
    RationalePoint,
    RequirementCoverage,
    Weights,
)

logger = logging.getLogger("app.agents.evaluator")

_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_DEFAULT_PATH = {
    "technical_fit": "requirement_coverage",
    "experience": "similar_projects",
    "timeline": "timeline_weeks",
    "cost": "cost_inr",
    "risk": "risks",
}
SCORE_TOLERANCE = 0.005


def render_proposal_text(p: Proposal) -> str:
    """Render a structured proposal as the free text a provider would submit."""
    lines = [f"Solution approach: {p.solution_approach}", f"Architecture: {p.architecture}"]
    if p.technologies:
        lines.append("Technologies: " + ", ".join(p.technologies))
    if p.timeline_weeks:
        lines.append(f"Timeline: {p.timeline_weeks:g} weeks")
    if p.cost_inr:
        lines.append(f"Cost: INR {int(p.cost_inr):,}")
    if p.team:
        lines.append(f"Team: {p.team}")
    for sp in p.similar_projects:
        lines.append(f"Similar project: {sp.vertical} - {sp.problem_type}. Outcome: {sp.outcome}")
    for r in p.risks:
        lines.append(f"Risk: {r.risk}" + (f" Mitigation: {r.mitigation}" if r.mitigation else ""))
    if p.support:
        lines.append(f"Support: {p.support}")
    for o in p.expected_outcomes:
        lines.append(f"Expected outcome: {o}")
    for rr in p.requirement_responses:
        lines.append(f"{rr.requirement_id}: {rr.response}")
    return "\n".join(lines)


def segment(text: str) -> dict[str, str]:
    return {f"seg_{i}": s.strip() for i, s in enumerate(x for x in _SENT.split(text) if x.strip())}


class BidEvaluator:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    # ---- Stage 1: extraction (isolated call per proposal, no scoring authority) ----
    def extract(
        self, proposal_id: str, raw_text: str, brief: Brief
    ) -> tuple[ExtractedProposal, InjectionFlag]:
        report = injection.scan(raw_text)
        segments = segment(report.sanitized_text)
        reqs = requirement_ids(brief)
        req_block = "\n".join(f"{rid}: {text}" for rid, text in reqs)
        seg_block = "\n".join(f"[{sid}] {text}" for sid, text in segments.items())
        parts = [
            "BRIEF_VERTICAL_AND_PROBLEM:\n" + brief.problem[:600],
            "REQUIREMENTS:\n" + req_block,
            prompts.wrap_untrusted(f"proposal_{proposal_id}", seg_block),
        ]
        try:
            draft = structured_call(
                self._llm,
                system=prompts.EXTRACTOR_SYSTEM,
                parts=parts,
                schema=ExtractedProposalDraft,
                temperature=0.0,
            )
        except LLMError:
            logger.error("extraction failed for %s; scoring as empty", proposal_id)
            draft = ExtractedProposalDraft()
        draft = self._normalise(draft, [rid for rid, _ in reqs], set(segments))
        flag = InjectionFlag(
            detected=report.detected or draft.model_detected_injection,
            reasons=report.reasons + (["model_detected"] if draft.model_detected_injection else []),
            removed_segments=report.removed_segments,
        )
        extracted = ExtractedProposal(
            **draft.model_dump(), proposal_id=proposal_id, injection_flag=flag
        )
        return extracted, flag

    @staticmethod
    def _normalise(
        draft: ExtractedProposalDraft, req_ids: list[str], segment_ids: set[str]
    ) -> ExtractedProposalDraft:
        """Make extractor output safe for scoring: one entry per known requirement, real segments."""
        out = draft.model_copy(deep=True)
        by_id = {c.requirement_id: c for c in out.requirement_coverage if c.requirement_id in req_ids}
        coverage = [
            by_id.get(rid) or RequirementCoverage(requirement_id=rid, status="not_covered")
            for rid in req_ids
        ]
        for item in [*coverage, *out.similar_projects, *out.risks]:
            if item.field_path and item.field_path not in segment_ids:
                item.field_path = ""
        out.requirement_coverage = coverage
        for attr in ("timeline_weeks", "cost_inr"):
            value = getattr(out, attr)
            if value is not None and (value <= 0 or value > 1e12):
                setattr(out, attr, None)
        return out

    # ---- Stage 3: rationale (citations validated) ----
    def _validate_rationale(
        self, r: RationaleDraft, ranking: list[str], scores: dict, extracted: dict
    ) -> list[str]:
        problems: list[str] = []
        if r.recommended_proposal_id != ranking[0]:
            problems.append("recommended_proposal_id must equal the top-ranked id")
        for pt in r.points:
            sc = scores.get(pt.proposal_id)
            if sc is None or pt.criterion not in CRITERIA:
                problems.append(f"unknown proposal/criterion: {pt.proposal_id}/{pt.criterion}")
                continue
            if abs(sc.criteria[pt.criterion] - pt.score) > SCORE_TOLERANCE:
                problems.append(f"score mismatch for {pt.proposal_id}/{pt.criterion}")
            found, _ = paths.resolve(extracted[pt.proposal_id].model_dump(), pt.field_path)
            if not found:
                problems.append(f"field_path not found: {pt.proposal_id}:{pt.field_path}")
        return problems

    @staticmethod
    def _template_rationale(ranking: list[str], scores: dict) -> RationaleDraft:
        top = ranking[0]
        best = sorted(scores[top].criteria.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
        points = [
            RationalePoint(proposal_id=top, criterion=c, score=v, field_path=_DEFAULT_PATH[c])
            for c, v in best
        ]
        strengths = " and ".join(c.replace("_", " ") for c, _ in best)
        return RationaleDraft(
            recommended_proposal_id=top,
            summary=(
                f"{top} ranks first with an overall score of {scores[top].overall:.2f}. "
                f"Its strongest areas are {strengths}."
            ),
            points=points,
        )

    def evaluate(
        self, brief_id: str, brief: Brief, proposals: dict[str, Proposal | str], weights: Weights
    ) -> Evaluation:
        extracted: list[ExtractedProposal] = []
        flags: list[str] = []
        for pid, p in proposals.items():
            text = render_proposal_text(p) if isinstance(p, Proposal) else p
            ex, flag = self.extract(pid, text, brief)
            extracted.append(ex)
            if flag.detected:
                flags.append(f"injection_flagged:{pid}")

        ctx = scoring.build_context(
            brief.target_timeline_weeks, brief.budget_low_inr, brief.budget_high_inr, extracted
        )
        flags = list(ctx.flags) + flags
        weights = scoring.validate_weights(weights)
        score_list = scoring.score_all(extracted, weights, ctx)
        costs = {e.proposal_id: e.cost_inr for e in extracted}
        ranking = scoring.rank(score_list, costs)
        scores = {s.proposal_id: s for s in score_list}
        extracted_by_id = {e.proposal_id: e for e in extracted}

        context = {
            "ranking": ranking,
            "scores": [s.model_dump() for s in score_list],
            "extracted": {k: v.model_dump() for k, v in extracted_by_id.items()},
        }
        source = "model"
        validated = True
        try:
            rationale = structured_call(
                self._llm,
                system=prompts.RATIONALE_SYSTEM,
                parts=["CONTEXT_JSON:" + json.dumps(context, ensure_ascii=False)],
                schema=RationaleDraft,
                validator=lambda r: self._validate_rationale(r, ranking, scores, extracted_by_id),
                temperature=0.2,
            )
        except LLMError:
            rationale = self._template_rationale(ranking, scores)
            source = "template"
            validated = not self._validate_rationale(rationale, ranking, scores, extracted_by_id)
        return Evaluation(
            brief_id=brief_id,
            weights=weights,
            flags=flags,
            extracted=extracted,
            scores=score_list,
            ranking=ranking,
            rationale=rationale,
            rationale_validated=validated,
            rationale_source=source,
        )
