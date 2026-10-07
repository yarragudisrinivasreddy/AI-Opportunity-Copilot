"""ROI as ranges with stated assumptions (PRD section 11). Never a single-point figure."""
import re
from dataclasses import dataclass

from app.schemas.opportunity import Rubric

# Planning bands only. They are assumptions to validate in a pilot, not predictions.
_REDUCTION_BANDS = {
    ("high", "high"): (0.40, 0.70),
    ("high", "medium"): (0.30, 0.55),
    ("medium", "high"): (0.25, 0.50),
    ("medium", "medium"): (0.15, 0.40),
}
_DEFAULT_BAND = (0.0, 0.20)

_NUM = re.compile(r"(\d[\d,]*\.?\d*)")


def parse_number(text: str | None) -> float | None:
    """First number in free text ('about 1,500 a day' -> 1500.0). None if absent."""
    if not text:
        return None
    match = _NUM.search(text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_minutes(text: str | None) -> float | None:
    """Minutes per unit from text like '2 minutes', '30 seconds', '1.5 hours'."""
    value = parse_number(text)
    if value is None:
        return None
    lowered = (text or "").lower()
    if "sec" in lowered:
        return value / 60.0
    if "hour" in lowered or re.search(r"\bhrs?\b", lowered):
        return value * 60.0
    return value


@dataclass(frozen=True)
class EffortEstimate:
    current_hours_per_day: float
    reduction_low: float
    reduction_high: float
    saved_hours_low: float
    saved_hours_high: float
    assumption: str


def estimate_effort(
    volume_per_day: float | None, minutes_per_unit: float | None, rubric: Rubric
) -> EffortEstimate | None:
    """Return a range-based estimate, or None if inputs were not confirmed by the user."""
    if not volume_per_day or not minutes_per_unit or volume_per_day <= 0 or minutes_per_unit <= 0:
        return None
    current = volume_per_day * minutes_per_unit / 60.0
    low, high = _REDUCTION_BANDS.get(
        (rubric.ai_feasibility, rubric.business_impact), _DEFAULT_BAND
    )
    if rubric.data_availability in ("low", "unknown"):
        low, high = low * 0.5, high * 0.75
    assumption = (
        f"Assumes AI pre-screening can remove {int(low * 100)}% to {int(high * 100)}% of "
        "manual effort. This is a planning band, not a prediction; verify in a pilot."
    )
    return EffortEstimate(
        current_hours_per_day=round(current, 1),
        reduction_low=round(low, 2),
        reduction_high=round(high, 2),
        saved_hours_low=round(current * low, 1),
        saved_hours_high=round(current * high, 1),
        assumption=assumption,
    )
