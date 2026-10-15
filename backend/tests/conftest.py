import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.core.local_privacy import StaticFaceDetector
from app.core.privacy import Box
from app.deps import build_context
from app.llm.fake import FakeLLM
from app.main import create_app


@pytest.fixture(autouse=True)
def _isolate_settings_env(monkeypatch):
    """Developer shell/.env must not break tests (e.g. PRIVACY_MODE=local, UPLOADS_ENABLED=false)."""
    monkeypatch.setenv("PRIVACY_MODE", "fake")
    monkeypatch.setenv("LLM_MODE", "fake")
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("STORE_MODE", "memory")
    monkeypatch.setenv("MEDIA_MODE", "memory")
    monkeypatch.setenv("UPLOADS_ENABLED", "true")
    monkeypatch.setenv("VISUALS_ENABLED", "false")
    monkeypatch.setenv("ENV", "test")



def make_jpeg(size=(320, 240), seed=1) -> bytes:
    import random

    rnd = random.Random(seed)
    img = Image.new("RGB", size)
    px = img.load()
    for x in range(size[0]):
        for y in range(size[1]):
            px[x, y] = (rnd.randint(0, 255), (x * 255) // size[0], (y * 255) // size[1])
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


@pytest.fixture
def jpeg() -> bytes:
    return make_jpeg()


@pytest.fixture
def settings() -> Settings:
    # Force test-safe modes so a developer .env cannot break the fixture.
    return Settings(
        env="test",
        auth_mode="dev",
        llm_mode="fake",
        store_mode="memory",
        media_mode="memory",
        privacy_mode="fake",
        daily_case_cap=3,
        rate_limit_per_minute=1000,
        visuals_enabled=False,
    )


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(settings, llm):
    ctx = build_context(settings, llm=llm, detector=StaticFaceDetector([Box(0.2, 0.2, 0.4, 0.5)]))
    app = create_app(settings, ctx)
    c = TestClient(app)
    c.ctx = ctx
    return c


ALICE = {"X-Dev-User": "alice"}
BOB = {"X-Dev-User": "bob"}
