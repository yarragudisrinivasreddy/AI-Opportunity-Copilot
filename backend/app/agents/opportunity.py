"""Agent 2: propose up to three opportunities; code derives the recommendation."""
import json

from app.core import rubric as rubric_rules
from app.llm import prompts
from app.llm.client import LLMClient, structured_call
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
        self, process: Process, answers: dict[str, str]
    ) -> tuple[list[Opportunity], str | None]:
        context = {"process": process.model_dump(), "answers": answers}
        parts = [
            "CONFIRMED_PROCESS_AND_ANSWERS_JSON:",
            json.dumps(context, ensure_ascii=False),
            "Assess AI opportunities now.",
        ]
        valid_refs = {s.id for s in process.steps} | set(answers)

        def validate(result: OpportunitySet) -> list[str]:
            if not result.opportunities and not result.not_ai_explanation:
                return ["empty list requires not_ai_explanation"]
            return []

        raw = structured_call(
            self._llm,
            system=prompts.OPPORTUNITY_SYSTEM,
            parts=parts,
            schema=OpportunitySet,
            validator=validate,
            strict=False,
            temperature=0.2,
        )
        opportunities: list[Opportunity] = []
        for i, draft in enumerate(raw.opportunities[:3], start=1):
            strength, recommendation, flags = rubric_rules.recommend(draft.rubric)
            opportunities.append(
                Opportunity(
                    **draft.model_dump(exclude={"evidence_refs"}),
                    evidence_refs=[r for r in draft.evidence_refs if r in valid_refs],
                    id=f"o{i}",
                    strength=strength,
                    recommendation=recommendation,
                    flags=flags,
                )
            )
        explanation = raw.not_ai_explanation
        if not opportunities and not explanation:
            explanation = NO_AI_FALLBACK
        return opportunities, explanation
