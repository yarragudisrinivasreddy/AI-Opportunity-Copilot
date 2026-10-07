"""Thin HTTP layer. Business rules live in services/ and core/."""
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.privacy import MAX_IMAGE_BYTES, MAX_VIDEO_BYTES
from app.fixtures import loader
from app.schemas.process import Process
from app.schemas.proposal import Weights
from app.security import User, authenticate

router = APIRouter(prefix="/api")


def ctx(request: Request):
    return request.app.state.ctx


def current_user(request: Request, c=Depends(ctx)) -> User:
    user = authenticate(request, c.settings)
    c.limiter.check(user.uid)
    return user


class CreateCaseIn(BaseModel):
    vertical: str = Field(default="manufacturing", max_length=40)


class DescriptionIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ConfirmIn(BaseModel):
    process: Process | None = None


class AnswerIn(BaseModel):
    field: str = Field(max_length=40)
    answer: str = Field(max_length=500)


class BriefIn(BaseModel):
    opportunity_id: str = Field(max_length=20)
    target_weeks: float | None = Field(default=None, gt=0, le=520)
    budget_low_inr: float | None = Field(default=None, gt=0, le=1e11)
    budget_high_inr: float | None = Field(default=None, gt=0, le=1e11)


class EvaluateIn(BaseModel):
    weights: Weights | None = None


@router.get("/sample")
def sample() -> dict:
    """Read-only sample walkthrough. No auth, no model calls, no cost."""
    return loader.sample_case()


@router.get("/config")
def public_config(c=Depends(ctx)) -> dict:
    """Public client config. No auth."""
    return {
        "uploadsEnabled": c.settings.uploads_enabled,
        "uploadsDisabledMessage": (
            "Photo and video upload is temporarily unavailable. "
            "Describe your process in text instead."
        ),
    }


@router.get("/cases")
def list_cases(user: User = Depends(current_user), c=Depends(ctx)) -> list[dict]:
    cases = c.cases.s.repo.list_cases(user.uid)
    return [{"id": x["id"], "status": x["status"], "createdAt": x["createdAt"]} for x in cases]


@router.post("/cases", status_code=201)
def create_case(body: CreateCaseIn, user: User = Depends(current_user), c=Depends(ctx)) -> dict:
    case = c.cases.create_case(user.uid, body.vertical)
    return {"id": case["id"], "status": case["status"]}


@router.post("/cases/{case_id}/media")
def upload_media(case_id: str, file: UploadFile = File(...), user: User = Depends(current_user),
                 c=Depends(ctx)) -> dict:
    limit = max(MAX_IMAGE_BYTES, MAX_VIDEO_BYTES)
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="file too large")
    return c.cases.add_media(case_id, user.uid, file.filename or "upload", data)


@router.put("/cases/{case_id}/description", status_code=204)
def set_description(case_id: str, body: DescriptionIn, user: User = Depends(current_user),
                    c=Depends(ctx)) -> None:
    c.cases.set_description(case_id, user.uid, body.text)


@router.post("/cases/{case_id}/analyze")
def analyze(case_id: str, user: User = Depends(current_user), c=Depends(ctx)) -> dict:
    return c.cases.analyze(case_id, user.uid)


@router.post("/cases/{case_id}/process/confirm")
def confirm(case_id: str, body: ConfirmIn, user: User = Depends(current_user), c=Depends(ctx)) -> dict:
    return c.cases.confirm_process(case_id, user.uid, body.process)


@router.get("/cases/{case_id}/question")
def question(case_id: str, user: User = Depends(current_user), c=Depends(ctx)) -> dict:
    return {"question": c.cases.next_question(case_id, user.uid)}


@router.post("/cases/{case_id}/answers", status_code=204)
def answer(case_id: str, body: AnswerIn, user: User = Depends(current_user), c=Depends(ctx)) -> None:
    c.cases.add_answer(case_id, user.uid, body.field, body.answer)


@router.post("/cases/{case_id}/discover")
def discover(case_id: str, user: User = Depends(current_user), c=Depends(ctx)) -> dict:
    return c.cases.discover(case_id, user.uid)


@router.post("/cases/{case_id}/brief")
def brief(case_id: str, body: BriefIn, user: User = Depends(current_user), c=Depends(ctx)) -> dict:
    if body.budget_low_inr and body.budget_high_inr and body.budget_low_inr > body.budget_high_inr:
        raise HTTPException(status_code=422, detail="budget_low_inr must not exceed budget_high_inr")
    return c.cases.generate_brief(
        case_id, user.uid, body.opportunity_id, target_weeks=body.target_weeks,
        budget_low=body.budget_low_inr, budget_high=body.budget_high_inr,
    )


@router.post("/cases/{case_id}/proposals/seed")
def seed(case_id: str, user: User = Depends(current_user), c=Depends(ctx)) -> list[dict]:
    return c.cases.seed_proposals(case_id, user.uid)


@router.post("/cases/{case_id}/evaluate")
def evaluate(case_id: str, body: EvaluateIn, user: User = Depends(current_user), c=Depends(ctx)) -> dict:
    return c.cases.evaluate(case_id, user.uid, body.weights)


@router.get("/cases/{case_id}")
def get_case(case_id: str, user: User = Depends(current_user), c=Depends(ctx)) -> dict:
    return c.cases.get_state(case_id, user.uid)


@router.delete("/cases/{case_id}", status_code=204)
def delete_case(case_id: str, user: User = Depends(current_user), c=Depends(ctx)) -> None:
    c.cases.delete_case(case_id, user.uid)
