"""Offline fake LLM for tests and key-free local development.

Outputs are deterministic and plausible for the manufacturing-inspection demo. NEVER use
numbers produced with this client in the deck, video or evalRuns (see eval/run.py guard).
"""
import json
import re
from collections.abc import Callable, Sequence

from app.llm.client import ImagePart, LLMError, Part, T
from app.schemas.brief import BriefDraft
from app.schemas.opportunity import OpportunitySet
from app.schemas.process import Process
from app.schemas.proposal import (
    ExtractedProposalDraft,
    ProjectRelevance,
    RationaleDraft,
    RationalePoint,
    RequirementCoverage,
    RiskMitigation,
)

Handler = Callable[[str, Sequence[Part]], object]


def _text(parts: Sequence[Part]) -> str:
    return "\n".join(p for p in parts if isinstance(p, str))


def _process(system: str, parts: Sequence[Part]) -> Process:
    n_frames = sum(isinstance(p, ImagePart) for p in parts)
    ref = "frame_0" if n_frames else "description"
    return Process.model_validate(
        {
            "process_name": "Manual product quality inspection",
            "environment": "Inspection table in a small manufacturing unit",
            "actors": ["operator", "supervisor"],
            "tools": ["inspection table", "paper checklist", "measuring device"],
            "steps": [
                {"id": "s1", "text": "Product placed on the inspection table", "kind": "observation", "evidence_ref": ref},
                {"id": "s2", "text": "Operator visually checks the component", "kind": "observation", "evidence_ref": ref},
                {"id": "s3", "text": "Operator compares the component with a paper checklist", "kind": "observation", "evidence_ref": ref, "decision_point": True},
                {"id": "s4", "text": "Measurements and result are recorded by hand", "kind": "observation", "evidence_ref": ref, "data_entry": True},
                {"id": "s5", "text": "Failed items are set aside for supervisor review", "kind": "assumption", "decision_point": True},
            ],
            "pain_points": [
                {"text": "Results are recorded manually, which is slow and error-prone", "kind": "assumption"}
            ],
            "missing_fields": ["volume", "time_per_unit", "exception_handling", "data_availability"],
        }
    )


def _opportunities(system: str, parts: Sequence[Part]) -> OpportunitySet:
    return OpportunitySet.model_validate(
        {
            "opportunities": [
                {
                    "title": "AI visual pre-screening",
                    "description": "Use multimodal vision to flag visible defects so humans only verify exceptions.",
                    "rubric": {"repetitive_work": "high", "data_availability": "medium", "ai_feasibility": "high",
                               "business_impact": "high", "implementation_complexity": "medium",
                               "human_oversight_required": True, "rule_based_sufficient": False},
                    "evidence_refs": ["s2", "s3"],
                },
                {
                    "title": "Inspection copilot for operators",
                    "description": "Guide operators through the checklist and capture results by voice or photo.",
                    "rubric": {"repetitive_work": "high", "data_availability": "high", "ai_feasibility": "high",
                               "business_impact": "medium", "implementation_complexity": "low",
                               "human_oversight_required": True, "rule_based_sufficient": False},
                    "evidence_refs": ["s3", "s4"],
                },
                {
                    "title": "Automated result logging",
                    "description": "Replace handwritten records with structured digital capture and daily summaries.",
                    "rubric": {"repetitive_work": "high", "data_availability": "high", "ai_feasibility": "medium",
                               "business_impact": "medium", "implementation_complexity": "low",
                               "human_oversight_required": False, "rule_based_sufficient": True},
                    "evidence_refs": ["s4"],
                },
            ],
            "not_ai_explanation": None,
        }
    )


def _brief(system: str, parts: Sequence[Part]) -> BriefDraft:
    return BriefDraft.model_validate(
        {
            "problem": "Components are inspected and recorded by hand, which is slow and inconsistent.",
            "current_workflow": [
                "Product placed on the inspection table",
                "Operator visually checks the component",
                "Operator compares it with a paper checklist",
                "Result is recorded by hand",
                "Failed items go to the supervisor",
            ],
            "proposed_solution": "A vision-assisted pre-screening step flags likely defects; operators verify only flagged or low-confidence items and results are logged automatically.",
            "ai_approaches": [
                {"approach": "Multimodal vision model", "reason": "Detect visible defects from inspection images"},
                {"approach": "Structured logging workflow", "reason": "Record results without manual entry"},
            ],
            "required_data": ["Labelled images of good and defective components", "Current checklist and defect definitions"],
            "integrations": ["Existing quality records (spreadsheet or ERP)"],
            "human_in_the_loop": ["Operator confirms every flagged defect", "Supervisor approves threshold changes"],
            "expected_outcomes": [],
            "risks": [
                {"risk": "Limited labelled defect images", "mitigation_prompt": "Describe your data collection and labelling plan"},
                {"risk": "Lighting and camera variation on the shop floor", "mitigation_prompt": "Describe how you will standardise capture conditions"},
            ],
            "phases": [
                {"name": "Proof of concept", "description": "Test detection on a sample of real images", "exit_criteria": "Agreed detection quality on held-out images"},
                {"name": "Pilot", "description": "Run alongside manual inspection on one line", "exit_criteria": "Agreement with human inspectors above the agreed target"},
                {"name": "Production", "description": "Roll out with monitoring and retraining", "exit_criteria": "Stable performance and operator adoption"},
            ],
            "assumptions": ["Inspection volume and time per unit are as stated by the user", "Images can be captured consistently"],
            "proposal_requirements": [
                "Describe the detection approach and expected accuracy measurement",
                "State how human verification is kept in the loop",
                "Provide a data collection and labelling plan",
                "Give a phased timeline with exit criteria",
                "List integration needs with existing records",
                "Name risks and mitigations",
            ],
        }
    )


def _extractor(system: str, parts: Sequence[Part]) -> ExtractedProposalDraft:
    text = _text(parts)
    req_ids = re.findall(r"^(R\d+):", text, flags=re.M)
    body = text.split("<<<UNTRUSTED_DATA", 1)[-1]
    segs = dict(re.findall(r"\[(seg_\d+)\] (.*)", body))
    coverage = []
    for rid in req_ids:
        hit = next(((sid, s) for sid, s in segs.items() if f"{rid}:" in s or f"{rid} " in s), None)
        if hit is None:
            coverage.append(RequirementCoverage(requirement_id=rid, status="not_covered"))
        else:
            status = "covered" if len(hit[1]) > 60 else "partial"
            coverage.append(RequirementCoverage(requirement_id=rid, status=status, field_path=hit[0]))
    projects = []
    for sid, s in segs.items():
        if s.lower().startswith("similar project"):
            low = s.lower()
            if "manufactur" in low and "inspection" in low:
                rel = "same_vertical_and_problem"
            elif "quality" in low or "vision" in low or "manufactur" in low:
                rel = "adjacent"
            else:
                rel = "unrelated"
            projects.append(ProjectRelevance(relevance=rel, field_path=sid))
    risks = [
        RiskMitigation(mitigated="mitigation:" in s.lower(), field_path=sid)
        for sid, s in segs.items()
        if s.lower().startswith("risk:")
    ]
    weeks = re.search(r"(\d+(?:\.\d+)?)\s*weeks", body)
    cost = re.search(r"(?:₹|INR)\s?([\d,]+)", body)
    low = body.lower()
    return ExtractedProposalDraft(
        requirement_coverage=coverage,
        similar_projects=projects,
        timeline_weeks=float(weeks.group(1)) if weeks else None,
        cost_inr=float(cost.group(1).replace(",", "")) if cost else None,
        risks=risks,
        human_in_loop_addressed="human" in low,
        data_readiness_plan="labelling" in low or "data readiness" in low,
        model_detected_injection=False,
    )


_PATHS = {
    "technical_fit": "requirement_coverage",
    "experience": "similar_projects",
    "timeline": "timeline_weeks",
    "cost": "cost_inr",
    "risk": "risks",
}


def _rationale(system: str, parts: Sequence[Part]) -> RationaleDraft:
    raw = _text(parts).split("CONTEXT_JSON:", 1)[-1].strip()
    ctx = json.loads(raw.splitlines()[0] if raw.startswith("{") and "\n" in raw else raw)
    top = ctx["ranking"][0]
    scores = {s["proposal_id"]: s for s in ctx["scores"]}
    best = sorted(scores[top]["criteria"].items(), key=lambda kv: -kv[1])[:2]
    points = [
        RationalePoint(proposal_id=top, criterion=c, score=v, field_path=_PATHS[c]) for c, v in best
    ]
    return RationaleDraft(
        recommended_proposal_id=top,
        summary=f"{top} ranks first with an overall score of {scores[top]['overall']}.",
        points=points,
    )


class FakeLLM:
    def __init__(self, handlers: dict[type, Handler] | None = None) -> None:
        self.handlers: dict[type, Handler] = {
            Process: _process,
            OpportunitySet: _opportunities,
            BriefDraft: _brief,
            ExtractedProposalDraft: _extractor,
            RationaleDraft: _rationale,
        }
        if handlers:
            self.handlers.update(handlers)
        self.calls: list[str] = []
        self.is_fake = True

    def generate_structured(
        self,
        *,
        system: str,
        parts: Sequence[Part],
        schema: type[T],
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
    ) -> T:
        handler = self.handlers.get(schema)
        if handler is None:
            raise LLMError(f"no fake handler for {schema.__name__}")
        self.calls.append(schema.__name__)
        result = handler(system, parts)
        return schema.model_validate(result.model_dump() if hasattr(result, "model_dump") else result)
