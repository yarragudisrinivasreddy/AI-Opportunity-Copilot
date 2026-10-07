"""Need-driven follow-up questions (PRD FR-06). Deterministic wording, max 5."""
from dataclasses import dataclass

from app.schemas.process import Process

MAX_QUESTIONS = 5

QUESTION_BANK: dict[str, str] = {
    "volume": "Roughly how many items does this process handle per day?",
    "time_per_unit": "About how long does one item take from start to finish?",
    "exception_handling": "What happens when an item fails the check or something goes wrong?",
    "data_availability": "Do you have past records or photos of this work (saved images, logs, spreadsheets)?",
    "systems_used": "What do you use today to record or track this work (paper, spreadsheet, other software)?",
}


@dataclass(frozen=True)
class Question:
    field: str
    text: str
    index: int  # 1-based position among questions asked so far


def next_question(process: Process, answered: dict[str, str]) -> Question | None:
    """Ask only about fields the agent reported missing and the user has not answered.

    'I don't know' counts as answered (it is stored with the field key).
    """
    if len(answered) >= MAX_QUESTIONS:
        return None
    for field in process.missing_fields:
        if field not in answered and field in QUESTION_BANK:
            return Question(field=field, text=QUESTION_BANK[field], index=len(answered) + 1)
    return None
