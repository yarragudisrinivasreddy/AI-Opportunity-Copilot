"""Composition root: build services from settings."""
from dataclasses import dataclass

from app.agents.bid_evaluator import BidEvaluator
from app.agents.brief import BriefAgent
from app.agents.opportunity import OpportunityAgent
from app.agents.vision_process import VisionProcessAgent
from app.config import Settings
from app.fixtures import loader
from app.llm.client import LLMClient
from app.security import SlidingWindowLimiter
from app.services.cases import CaseService, Services


@dataclass
class AppContext:
    settings: Settings
    cases: CaseService
    limiter: SlidingWindowLimiter
    ip_limiter: SlidingWindowLimiter
    llm: LLMClient


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_mode == "vertex":
        from app.llm.vertex import VertexGeminiClient

        return VertexGeminiClient(settings.gcp_project, settings.gcp_location, settings.gemini_model)
    from app.llm.fake import FakeLLM

    return FakeLLM()


def build_context(settings: Settings, llm: LLMClient | None = None, repo=None, media=None,
                  detector=None, redactor=None) -> AppContext:
    llm = llm or build_llm(settings)

    if repo is None:
        if settings.store_mode == "firestore":
            from app.repo.firestore import FirestoreRepository

            repo = FirestoreRepository(settings.gcp_project, settings.firestore_database)
        else:
            from app.repo.memory import InMemoryRepository

            repo = InMemoryRepository()
    if media is None:
        if settings.media_mode == "gcs":
            from app.repo.firestore import GcsMediaStore

            media = GcsMediaStore(settings.media_bucket)
        else:
            from app.repo.memory import InMemoryMediaStore

            media = InMemoryMediaStore()
    if detector is None:
        if settings.privacy_mode == "gcp":
            from app.core.privacy import CloudDlpImageRedactor, CloudVisionFaceDetector

            detector = CloudVisionFaceDetector()
            redactor = CloudDlpImageRedactor(settings.gcp_project)
        else:
            from app.core.local_privacy import OpenCVFaceDetector

            detector = OpenCVFaceDetector()

    services = Services(
        repo=repo, media=media,
        vision=VisionProcessAgent(llm), opportunities=OpportunityAgent(llm),
        briefs=BriefAgent(llm), evaluator=BidEvaluator(llm),
        detector=detector, redactor=redactor,
        providers=loader.providers(), seeded_proposals=loader.seeded_proposals(),
        daily_case_cap=settings.daily_case_cap,
        global_daily_case_cap=settings.global_daily_case_cap,
        uploads_enabled=settings.uploads_enabled,
    )
    return AppContext(
        settings=settings,
        cases=CaseService(services),
        limiter=SlidingWindowLimiter(settings.rate_limit_per_minute),
        ip_limiter=SlidingWindowLimiter(settings.ip_rate_limit_per_minute),
        llm=llm,
    )
