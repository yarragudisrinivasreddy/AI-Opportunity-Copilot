"""Case workflow service: enforces ownership, gating and the status machine."""
import datetime as dt
import json
import logging
import uuid
from dataclasses import dataclass

from app.agents import questions
from app.agents.bid_evaluator import BidEvaluator, render_proposal_text
from app.agents.brief import BriefAgent
from app.agents.opportunity import OpportunityAgent
from app.agents.vision_process import VisionProcessAgent, clean_user_text
from app.core import privacy
from app.llm.client import LLMError
from app.repo.base import MediaStore, Repository
from app.schemas.brief import Brief
from app.schemas.opportunity import Opportunity
from app.schemas.process import Process
from app.schemas.proposal import Proposal, Provider, Weights

logger = logging.getLogger("app.services.cases")

STATUSES = ["captured", "analyzed", "confirmed", "discovered", "briefed", "proposals", "evaluated"]


class NotFound(Exception):
    pass


class Conflict(Exception):
    """Requested step is not allowed in the case's current state."""


class QuotaExceeded(Exception):
    pass


class UploadsDisabled(Exception):
    """Photo/video upload is turned off (e.g. privacy pipeline not verified)."""


UPLOADS_DISABLED_MESSAGE = (
    "Photo and video upload is temporarily unavailable. "
    "Describe your process in text instead."
)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass
class Services:
    repo: Repository
    media: MediaStore
    vision: VisionProcessAgent
    opportunities: OpportunityAgent
    briefs: BriefAgent
    evaluator: BidEvaluator
    detector: privacy.FaceDetector
    redactor: privacy.ImageRedactor | None
    providers: list[Provider]
    seeded_proposals: dict[str, dict]  # provider_id -> {"structured": Proposal, "rawText": str}
    daily_case_cap: int = 5
    uploads_enabled: bool = True


class CaseService:
    def __init__(self, s: Services) -> None:
        self.s = s

    # ---------- helpers ----------
    def _audit(self, uid: str, action: str, case_id: str = "", **meta) -> None:
        self.s.repo.add_audit({"actorUid": uid, "action": action, "caseId": case_id, "ts": _now(), "meta": meta})

    def _case(self, case_id: str, uid: str) -> dict:
        case = self.s.repo.get_case(case_id)
        # Same error for missing and foreign cases: do not reveal existence.
        if not case or case.get("ownerUid") != uid:
            raise NotFound(case_id)
        return case

    def _require(self, case: dict, minimum: str) -> None:
        if STATUSES.index(case["status"]) < STATUSES.index(minimum):
            raise Conflict(f"case must reach '{minimum}' first (currently '{case['status']}')")

    def _set_status(self, case: dict, status: str) -> None:
        if STATUSES.index(status) > STATUSES.index(case["status"]):
            self.s.repo.update_case(case["id"], {"status": status, "updatedAt": _now()})
        else:
            self.s.repo.update_case(case["id"], {"updatedAt": _now()})

    def _frames(self, case_id: str) -> list[bytes]:
        docs = sorted(self.s.repo.list_docs(case_id, "media"), key=lambda d: d["frameIndex"])
        return [self.s.media.get(d["sanitizedPath"]) for d in docs]

    def _answers(self, case_id: str) -> dict[str, str]:
        return {d["fieldKey"]: d["answer"] for d in self.s.repo.list_docs(case_id, "answers")}

    def _latest(self, case_id: str, collection: str) -> dict | None:
        docs = self.s.repo.list_docs(case_id, collection)
        return docs[-1] if docs else None

    # ---------- lifecycle ----------
    def create_case(self, uid: str, vertical: str = "manufacturing") -> dict:
        day = dt.date.today().isoformat()
        if self.s.repo.incr_daily_cases(uid, day) > self.s.daily_case_cap:
            raise QuotaExceeded("daily case limit reached; use the sample case")
        case = {
            "id": uuid.uuid4().hex[:16],
            "ownerUid": uid,
            "status": "captured",
            "vertical": vertical[:40],
            "isSample": False,
            "description": "",
            "frameCount": 0,
            "createdAt": _now(),
            "updatedAt": _now(),
        }
        self.s.repo.create_case(case)
        self._audit(uid, "case_created", case["id"])
        return case

    def add_media(self, case_id: str, uid: str, filename: str, data: bytes) -> dict:
        if not self.s.uploads_enabled:
            raise UploadsDisabled(UPLOADS_DISABLED_MESSAGE)
        case = self._case(case_id, uid)
        if case["status"] != "captured":
            raise Conflict("media can only be added before analysis")
        kind = sniff_kind(data)
        frames = privacy.sample_frames(data) if kind == "video" else [data]
        existing = case.get("frameCount", 0)
        if existing + len(frames) > privacy.MAX_FRAMES:
            raise privacy.SanitizationError("too many frames for one case")
        summaries = []
        for i, raw in enumerate(frames):
            result = privacy.sanitize_image(raw, self.s.detector, self.s.redactor)
            index = existing + i
            path = self.s.media.put(case_id, f"frame_{index}.jpg", result.data, result.mime)
            f = result.findings
            self.s.repo.put_doc(case_id, "media", f"{index:03d}", {
                "frameIndex": index, "sanitizedPath": path, "kind": "frame" if kind == "video" else "image",
                "privacy": {"facesBlurred": f.faces_blurred, "piiRedactionApplied": f.pii_redaction_applied,
                            "piiRegionsMasked": f.pii_regions_masked, "summary": f.summary()},
                "createdAt": _now(),
            })
            summaries.append(f.summary())
        self.s.repo.update_case(case_id, {"frameCount": existing + len(frames), "updatedAt": _now()})
        self._audit(uid, "media_added", case_id, frames=len(frames))
        return {"frames": len(frames), "privacy": summaries}

    def set_description(self, case_id: str, uid: str, text: str) -> None:
        case = self._case(case_id, uid)
        if case["status"] != "captured":
            raise Conflict("description can only be set before analysis")
        cleaned, removed = clean_user_text(text[:4000])
        self.s.repo.update_case(case_id, {"description": cleaned, "descriptionFlagged": removed > 0})

    def analyze(self, case_id: str, uid: str) -> dict:
        case = self._case(case_id, uid)
        self._require(case, "captured")
        frames = self._frames(case_id)
        process = self.s.vision.analyze(frames, case.get("description") or None)
        version = len(self.s.repo.list_docs(case_id, "process")) + 1
        doc = {"version": version, "data": process.model_dump(), "confirmedByUser": False,
               "userEdits": [], "createdAt": _now()}
        self.s.repo.put_doc(case_id, "process", f"{version:03d}", doc)
        self._set_status(case, "analyzed")
        self._audit(uid, "process_analyzed", case_id)
        return doc

    def confirm_process(self, case_id: str, uid: str, edited: Process | None) -> dict:
        case = self._case(case_id, uid)
        self._require(case, "analyzed")
        latest = self._latest(case_id, "process")
        data = edited.model_dump() if edited else latest["data"]
        edits = list(latest.get("userEdits", []))
        if edited and edited.model_dump() != latest["data"]:
            edits.append({"at": _now(), "note": "user edited process before confirming"})
        version = latest["version"] + 1
        doc = {"version": version, "data": data, "confirmedByUser": True, "userEdits": edits, "createdAt": _now()}
        self.s.repo.put_doc(case_id, "process", f"{version:03d}", doc)
        self._set_status(case, "confirmed")
        self._audit(uid, "process_confirmed", case_id)
        return doc

    def _confirmed_process(self, case_id: str) -> Process:
        latest = self._latest(case_id, "process")
        if not latest or not latest.get("confirmedByUser"):
            raise Conflict("process must be confirmed by the user first")
        return Process.model_validate(latest["data"])

    def next_question(self, case_id: str, uid: str) -> dict | None:
        case = self._case(case_id, uid)
        self._require(case, "analyzed")
        latest = self._latest(case_id, "process")
        q = questions.next_question(Process.model_validate(latest["data"]), self._answers(case_id))
        return None if q is None else {"field": q.field, "text": q.text, "index": q.index}

    def add_answer(self, case_id: str, uid: str, field: str, answer: str) -> None:
        case = self._case(case_id, uid)
        self._require(case, "analyzed")
        if field not in questions.QUESTION_BANK:
            raise Conflict("unknown question field")
        cleaned, _ = clean_user_text(answer[:500])
        self.s.repo.put_doc(case_id, "answers", field, {
            "fieldKey": field, "question": questions.QUESTION_BANK[field],
            "answer": cleaned or "I don't know", "source": "user", "createdAt": _now(),
        })

    def discover(self, case_id: str, uid: str) -> dict:
        case = self._case(case_id, uid)
        self._require(case, "confirmed")
        process = self._confirmed_process(case_id)
        opps, explanation = self.s.opportunities.discover(process, self._answers(case_id))
        for o in opps:
            self.s.repo.put_doc(case_id, "opportunities", o.id, o.model_dump())
        self.s.repo.update_case(case_id, {"notAiExplanation": explanation})
        self._set_status(case, "discovered")
        self._audit(uid, "opportunities_discovered", case_id, count=len(opps))
        return {"opportunities": [o.model_dump() for o in opps], "notAiExplanation": explanation}

    def generate_brief(
        self, case_id: str, uid: str, opportunity_id: str, *,
        target_weeks: float | None = None, budget_low: float | None = None, budget_high: float | None = None,
    ) -> dict:
        case = self._case(case_id, uid)
        self._require(case, "discovered")
        raw = self.s.repo.get_doc(case_id, "opportunities", opportunity_id)
        if not raw:
            raise NotFound(opportunity_id)
        opp = Opportunity.model_validate(raw)
        brief = self.s.briefs.generate(
            opp, self._confirmed_process(case_id), self._answers(case_id),
            target_timeline_weeks=target_weeks, budget_low_inr=budget_low, budget_high_inr=budget_high,
        )
        raw["selected"] = True
        self.s.repo.put_doc(case_id, "opportunities", opportunity_id, raw)
        version = len(self.s.repo.list_docs(case_id, "briefs")) + 1
        doc = {"id": f"b{version}", "oppId": opportunity_id, "version": version,
               "data": brief.model_dump(), "createdAt": _now()}
        self.s.repo.put_doc(case_id, "briefs", doc["id"], doc)
        self._set_status(case, "briefed")
        self._audit(uid, "brief_generated", case_id)
        return doc

    def seed_proposals(self, case_id: str, uid: str) -> list[dict]:
        case = self._case(case_id, uid)
        self._require(case, "briefed")
        out = []
        for pid, item in self.s.seeded_proposals.items():
            doc = {"id": pid, "providerId": pid, "simulated": True,
                   "structured": item["structured"].model_dump(), "rawText": item["rawText"],
                   "createdAt": _now()}
            self.s.repo.put_doc(case_id, "proposals", pid, doc)
            out.append(doc)
        self._set_status(case, "proposals")
        return out

    def evaluate(self, case_id: str, uid: str, weights: Weights | None) -> dict:
        case = self._case(case_id, uid)
        self._require(case, "proposals")
        brief_doc = self._latest(case_id, "briefs")
        brief = Brief.model_validate(brief_doc["data"])
        proposals = {d["id"]: d["rawText"] for d in self.s.repo.list_docs(case_id, "proposals")}
        if not proposals:
            raise Conflict("no proposals to evaluate")
        evaluation = self.s.evaluator.evaluate(brief_doc["id"], brief, proposals, weights or Weights())
        version = len(self.s.repo.list_docs(case_id, "evaluations")) + 1
        doc = {"id": f"e{version}", "data": evaluation.model_dump(), "createdAt": _now()}
        self.s.repo.put_doc(case_id, "evaluations", doc["id"], doc)
        self._set_status(case, "evaluated")
        self._audit(uid, "evaluated", case_id, flags=len(evaluation.flags))
        return doc

    # ---------- read / delete ----------
    def get_state(self, case_id: str, uid: str) -> dict:
        case = self._case(case_id, uid)
        latest_process = self._latest(case_id, "process")
        return {
            "case": {k: v for k, v in case.items() if k != "ownerUid"},
            "media": [d["privacy"] | {"frameIndex": d["frameIndex"]} for d in self.s.repo.list_docs(case_id, "media")],
            "process": latest_process,
            "answers": self.s.repo.list_docs(case_id, "answers"),
            "opportunities": self.s.repo.list_docs(case_id, "opportunities"),
            "brief": self._latest(case_id, "briefs"),
            "proposals": self.s.repo.list_docs(case_id, "proposals"),
            "evaluation": self._latest(case_id, "evaluations"),
            "providers": [p.model_dump() for p in self.s.providers],
        }

    def delete_case(self, case_id: str, uid: str) -> None:
        self._case(case_id, uid)
        self.s.media.delete_case(case_id)
        self.s.repo.delete_case(case_id)
        self._audit(uid, "case_deleted", case_id)


def sniff_kind(data: bytes) -> str:
    """Decide image vs video from magic bytes, never from the client-supplied filename/type."""
    if data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n" or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        return "image"
    if data[4:8] == b"ftyp":
        return "video"
    raise privacy.SanitizationError("unsupported file type")
