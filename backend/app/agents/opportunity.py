"""Agent 2: propose up to three opportunities; code derives the recommendation."""
import json

from app.core import rubric as rubric_rules
from app.core.flow import validate_or_synthesize_flow
from app.llm import prompts
from app.llm.client import LLMClient, LLMError, structured_call
from app.schemas.opportunity import Opportunity, OpportunitySet
from app.schemas.process import Process

NO_AI_FALLBACK = (
    "Based on the confirmed process, a simpler workflow change is likely a better first step "
    "than AI."
)


class OpportunityAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def discover(
        self, process: Process, answers: dict[str, str], *, language: str = "en",
    ) -> tuple[list[Opportunity], str | None, list[dict]]:
        lang = language if language in ("en", "hi", "te") else "en"
        context = {"process": process.model_dump(), "answers": answers, "language": lang}
        parts = [
            "CONFIRMED_PROCESS_AND_ANSWERS_JSON:",
            json.dumps(context, ensure_ascii=False),
            f"Write user-facing title, description and flow text in language '{lang}'. "
            "Do not translate enums, numbers, currency or ids. Assess AI opportunities now.",
        ]
        valid_refs = {s.id for s in process.steps} | set(answers)

        def validate(result: OpportunitySet) -> list[str]:
            if not result.opportunities and not result.not_ai_explanation:
                return ["empty list requires not_ai_explanation"]
            return []

        try:
            raw = structured_call(
                self._llm,
                system=prompts.OPPORTUNITY_SYSTEM,
                parts=parts,
                schema=OpportunitySet,
                validator=validate,
                strict=False,
                temperature=0.2,
                retries=2,
                max_output_tokens=8192,
            )
        except LLMError:
            # Telugu/Hindi JSON is often truncated; fall back to English once so the path completes.
            if lang != "en":
                parts[-1] = (
                    "Write user-facing title, description and flow text in language 'en'. "
                    "Do not translate enums, numbers, currency or ids. Assess AI opportunities now."
                )
                raw = structured_call(
                    self._llm,
                    system=prompts.OPPORTUNITY_SYSTEM,
                    parts=parts,
                    schema=OpportunitySet,
                    validator=validate,
                    strict=False,
                    temperature=0.2,
                    retries=2,
                    max_output_tokens=8192,
                )
            else:
                raise
        opportunities: list[Opportunity] = []
        flow_audit: list[dict] = []
        for i, draft in enumerate(raw.opportunities[:3], start=1):
            strength, recommendation, flags = rubric_rules.recommend(draft.rubric)
            humans = (
                "A person still reviews exceptions and signs off"
                if draft.rubric.human_oversight_required
                else "People stay involved only when something is unclear"
            )
            built = validate_or_synthesize_flow(
                list(draft.flow),
                title=draft.title,
                description=draft.description,
                recommendation=recommendation,
                human_oversight_required=draft.rubric.human_oversight_required,
                process=process,
                improvement=draft.description,
                humans_text=humans,
            )
            flow_audit.append({
                "id": f"o{i}",
                "groundedKept": built.grounded_kept,
                "ungroundedDropped": built.ungrounded_dropped,
                "synthesized": built.synthesized,
            })
            opportunities.append(
                Opportunity(
                    **draft.model_dump(exclude={"evidence_refs", "flow"}),
                    evidence_refs=[r for r in draft.evidence_refs if r in valid_refs],
                    id=f"o{i}",
                    strength=strength,
                    recommendation=recommendation,
                    flags=flags,
                    flow=built.rows,
                )
            )
        explanation = raw.not_ai_explanation
        if not opportunities and not explanation:
            explanation = NO_AI_FALLBACK
        return opportunities, explanation, flow_audit
