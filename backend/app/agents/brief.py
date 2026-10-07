"""Agent 3: build-ready brief. Code (not the model) adds ROI ranges, status and disclaimer."""
import json

from app.core import roi
from app.llm import prompts
from app.llm.client import LLMClient, structured_call
from app.schemas.brief import Brief, BriefDraft, ExpectedOutcome
from app.schemas.opportunity import Opportunity
from app.schemas.process import Process


def requirement_ids(brief: Brief) -> list[tuple[str, str]]:
    """Stable ids R1..Rn derived from proposal_requirements order."""
    return [(f"R{i}", text) for i, text in enumerate(brief.proposal_requirements, start=1)]


class BriefAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def generate(
        self,
        opportunity: Opportunity,
        process: Process,
        answers: dict[str, str],
        *,
        target_timeline_weeks: float | None = None,
        budget_low_inr: float | None = None,
        budget_high_inr: float | None = None,
    ) -> Brief:
        context = {
            "opportunity": opportunity.model_dump(),
            "process": process.model_dump(),
            "answers": answers,
        }
        parts = [
            "SELECTED_OPPORTUNITY_PROCESS_AND_ANSWERS_JSON:",
            json.dumps(context, ensure_ascii=False),
            "Write the brief now.",
        ]
        draft = structured_call(
            self._llm,
            system=prompts.BRIEF_SYSTEM,
            parts=parts,
            schema=BriefDraft,
            temperature=0.2,
        )
        data = draft.model_dump()
        # ROI is computed in code from user-confirmed facts, as a range with its assumption.
        data["expected_outcomes"] = []
        assumptions = list(data["assumptions"])
        estimate = roi.estimate_effort(
            roi.parse_number(answers.get("volume")),
            roi.parse_minutes(answers.get("time_per_unit")),
            opportunity.rubric,
        )
        if estimate:
            outcome = ExpectedOutcome(
                metric="Manual effort saved per day",
                low=estimate.saved_hours_low,
                high=estimate.saved_hours_high,
                unit="hours/day",
                assumption=estimate.assumption,
            )
            data["expected_outcomes"] = [outcome.model_dump()]
            assumptions.append(
                f"Current effort is about {estimate.current_hours_per_day} hours/day, from the "
                "volume and time per item you provided."
            )
        else:
            assumptions.append(
                "No effort estimate is shown because volume and time per item were not confirmed."
            )
        data["assumptions"] = assumptions
        return Brief(
            **data,
            opportunity_id=opportunity.id,
            target_timeline_weeks=target_timeline_weeks,
            budget_low_inr=budget_low_inr,
            budget_high_inr=budget_high_inr,
        )
