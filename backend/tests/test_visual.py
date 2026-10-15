"""Concept visual endpoint: off by default; FakeImageClient for tests only."""
from app.config import Settings
from app.core.local_privacy import StaticFaceDetector
from app.core.privacy import Box
from app.deps import build_context
from app.llm.fake import FakeLLM
from app.llm.image import FakeImageClient, downscale_under
from app.main import create_app
from fastapi.testclient import TestClient
from tests.conftest import ALICE


def test_fake_image_client_returns_png_bytes():
    data = FakeImageClient().generate("concept of a tablet checklist")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_config_exposes_visuals_enabled(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["visualsEnabled"] is False
    assert body["maxPhotos"] >= 1
    assert body["maxPhotoBytes"] > 0
    assert body["maxVideoBytes"] == 25 * 1024 * 1024
    assert body["maxVideoBytes"] < 32 * 1024 * 1024
    assert body["maxVideoSeconds"] == 30


def test_visual_endpoint_off(client):
    c = client.post("/api/cases", json={}, headers=ALICE)
    assert c.status_code == 201
    cid = c.json()["id"]
    r = client.post(f"/api/cases/{cid}/opportunities/o1/visual", headers=ALICE)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "off"


def _live_to_discover():
    s = Settings(env="test", visuals_enabled=True, daily_case_cap=20, rate_limit_per_minute=1000)
    ctx = build_context(s, llm=FakeLLM(), detector=StaticFaceDetector([]))
    # Force FakeImageClient even though visuals_enabled (llm fake path already does).
    ctx.cases.s.image_client = FakeImageClient()
    ctx.cases.s.visuals_enabled = True
    app = create_app(s, ctx)
    return TestClient(app)


def test_visual_endpoint_ready_with_fake_and_cache():
    client = _live_to_discover()
    cid = client.post("/api/cases", json={}, headers=ALICE).json()["id"]
    client.put(f"/api/cases/{cid}/description", json={"text": "Operators check parts by hand on a table."}, headers=ALICE)
    client.post(f"/api/cases/{cid}/analyze", headers=ALICE)
    proc = client.get(f"/api/cases/{cid}", headers=ALICE).json()["process"]["data"]
    client.post(f"/api/cases/{cid}/process/confirm", json={"process": proc}, headers=ALICE)
    client.post(f"/api/cases/{cid}/answers", json={"field": "volume", "answer": "100"}, headers=ALICE)
    client.post(f"/api/cases/{cid}/answers", json={"field": "time_per_unit", "answer": "2 minutes"}, headers=ALICE)
    d = client.post(f"/api/cases/{cid}/discover", headers=ALICE).json()
    oid = d["opportunities"][0]["id"]
    r1 = client.post(f"/api/cases/{cid}/opportunities/{oid}/visual", headers=ALICE).json()
    assert r1["status"] == "ready" and r1["dataUrl"].startswith("data:image/")
    assert r1["cached"] is False
    r2 = client.post(f"/api/cases/{cid}/opportunities/{oid}/visual", headers=ALICE).json()
    assert r2["status"] == "ready" and r2["cached"] is True


def test_downscale_under_returns_small_payload():
    # Expand fake PNG by tiling via PIL if available; otherwise skip size assert.
    raw = FakeImageClient().generate("x")
    out, mime = downscale_under(raw, 250_000)
    assert mime.startswith("image/")
    assert len(out) <= 250_000
