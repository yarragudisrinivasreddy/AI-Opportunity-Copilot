"""Load seeded fixtures. All providers and proposals are SIMULATED and labelled as such."""
import json
from functools import lru_cache
from pathlib import Path

from app.schemas.proposal import Proposal, Provider

_DIR = Path(__file__).parent


@lru_cache
def sample_case() -> dict:
    return json.loads((_DIR / "sample_case.json").read_text())


@lru_cache
def providers() -> list[Provider]:
    return [Provider.model_validate(p) for p in json.loads((_DIR / "providers.json").read_text())]


@lru_cache
def seeded_proposals() -> dict[str, dict]:
    raw = json.loads((_DIR / "proposals.json").read_text())
    return {
        pid: {"structured": Proposal.model_validate(item["structured"]), "rawText": item["rawText"]}
        for pid, item in raw.items()
    }
