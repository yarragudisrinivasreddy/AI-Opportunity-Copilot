"""FastAPI app factory."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings, get_settings
from app.core.privacy import SanitizationError
from app.deps import AppContext, build_context
from app.llm.client import LLMError
from app.security import SecurityHeadersMiddleware
from app.services.cases import Conflict, NotFound, QuotaExceeded, UploadsDisabled

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")


def create_app(settings: Settings | None = None, context: AppContext | None = None) -> FastAPI:
    settings = settings or get_settings()
    prod = settings.env == "production"
    app = FastAPI(
        title="AI Opportunity Copilot API",
        docs_url=None if prod else "/docs",
        redoc_url=None,
        openapi_url=None if prod else "/openapi.json",
    )
    app.state.ctx = context or build_context(settings)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Dev-User", "X-Firebase-AppCheck"],
        max_age=600,
    )

    def err(status: int, message: str) -> JSONResponse:
        return JSONResponse(status_code=status, content={"detail": message})

    @app.exception_handler(NotFound)
    async def _nf(_: Request, __: NotFound):
        return err(404, "not found")

    @app.exception_handler(Conflict)
    async def _conflict(_: Request, exc: Conflict):
        return err(409, str(exc))

    @app.exception_handler(QuotaExceeded)
    async def _quota(_: Request, exc: QuotaExceeded):
        return err(429, str(exc))

    @app.exception_handler(UploadsDisabled)
    async def _uploads_off(_: Request, exc: UploadsDisabled):
        return err(403, str(exc))

    @app.exception_handler(SanitizationError)
    async def _san(_: Request, exc: SanitizationError):
        logger.info("media rejected: %s", exc)
        return err(422, "this file could not be accepted; try a different image or a shorter video")

    @app.exception_handler(LLMError)
    async def _llm(_: Request, exc: LLMError):
        logger.error("model failure: %s", exc)
        return err(502, "analysis failed; please try again or use the sample case")

    @app.exception_handler(ValueError)
    async def _value(_: Request, exc: ValueError):
        return err(400, str(exc))

    @app.get("/healthz")
    @app.get("/health")
    def healthz() -> dict:
        # Prefer /health or /api/health: Cloud Run's edge can swallow bare /healthz.
        return {"status": "ok", "env": settings.env}

    app.include_router(router)
    return app


def app_factory() -> FastAPI:  # uvicorn --factory app.main:app_factory
    return create_app()
