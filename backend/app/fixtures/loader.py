"""Load seeded fixtures. All providers and proposals are SIMULATED and labelled as such."""
import json
from functools import lru_cache
from pathlib import Path

from app.schemas.proposal import Proposal, Provider

_DIR = Path(__file__).parent


def _read_json(name: str) -> object:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


@lru_cache
def sample_case() -> dict:
    return _read_json("sample_case.json")  # type: ignore[return-value]


@lru_cache
def providers() -> list[Provider]:
    return [Provider.model_validate(p) for p in _read_json("providers.json")]  # type: ignore[arg-type]


@lru_cache
def seeded_proposals() -> dict[str, dict]:
    raw = _read_json("proposals.json")  # type: ignore[assignment]
    return {
        pid: {"structured": Proposal.model_validate(item["structured"]), "rawText": item["rawText"]}
        for pid, item in raw.items()
    }
