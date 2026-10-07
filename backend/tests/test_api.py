import io

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.deps import build_context
from app.main import create_app
from tests.conftest import ALICE, BOB, make_jpeg


def new_case(client, headers=ALICE) -> str:
    r = client.post("/api/cases", json={}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upload(client, case_id, data, name="a.jpg", headers=ALICE):
    return client.post(f"/api/cases/{case_id}/media", files={"file": (name, io.BytesIO(data))}, headers=headers)


def test_full_happy_path(client, jpeg):
    cid = new_case(client)
    r = upload(client, cid, jpeg)
    assert r.status_code == 200 and "face(s) blurred" in r.json()["privacy"][0]

    # analysis blocked until process exists; discover blocked until confirmed
    assert client.post(f"/api/cases/{cid}/discover", headers=ALICE).status_code == 409
    r = client.post(f"/api/cases/{cid}/analyze", headers=ALICE)
    assert r.status_code == 200 and not r.json()["confirmedByUser"]
    assert client.post(f"/api/cases/{cid}/discover", headers=ALICE).status_code == 409

    q = client.get(f"/api/cases/{cid}/question", headers=ALICE).json()["question"]
    assert q["field"] == "volume"
    for field, ans in [("volume", "About 1,500 a day"), ("time_per_unit", "2 minutes")]:
        assert client.post(f"/api/cases/{cid}/answers", json={"field": field, "answer": ans}, headers=ALICE).status_code == 204

    assert client.post(f"/api/cases/{cid}/process/confirm", json={}, headers=ALICE).json()["confirmedByUser"]
    d = client.post(f"/api/cases/{cid}/discover", headers=ALICE).json()
    assert len(d["opportunities"]) == 3 and d["opportunities"][0]["recommendation"]

    b = client.post(f"/api/cases/{cid}/brief", json={"opportunity_id": "o1", "target_weeks": 12,
                    "budget_low_inr": 800000, "budget_high_inr": 1200000}, headers=ALICE).json()
    assert b["data"]["status"] == "proposal_only" and b["data"]["expected_outcomes"]

    seeded = client.post(f"/api/cases/{cid}/proposals/seed", headers=ALICE).json()
    assert len(seeded) == 3 and all(p["simulated"] for p in seeded)
    ev = client.post(f"/api/cases/{cid}/evaluate", json={}, headers=ALICE).json()["data"]
    assert ev["ranking"][0] == "p_visionworks" and ev["rationale_validated"]
    assert ev["flags"] == ["injection_flagged:p_apexml"]

    state = client.get(f"/api/cases/{cid}", headers=ALICE).json()
    assert state["case"]["status"] == "evaluated" and "ownerUid" not in state["case"]
    assert client.delete(f"/api/cases/{cid}", headers=ALICE).status_code == 204
    assert client.get(f"/api/cases/{cid}", headers=ALICE).status_code == 404
    assert client.ctx.cases.s.repo.list_docs(cid, "media") == []


def test_analyze_from_description_only(client):
    cid = new_case(client)
    assert client.put(f"/api/cases/{cid}/description", json={"text": "Operators check parts by hand."}, headers=ALICE).status_code == 204
    assert client.post(f"/api/cases/{cid}/analyze", headers=ALICE).status_code == 200


def test_uploads_kill_switch(jpeg):
    s = Settings(env="test", uploads_enabled=False, daily_case_cap=3, rate_limit_per_minute=1000)
    from app.llm.fake import FakeLLM
    from app.core.local_privacy import StaticFaceDetector
    from app.core.privacy import Box

    ctx = build_context(s, llm=FakeLLM(), detector=StaticFaceDetector([Box(0.2, 0.2, 0.4, 0.5)]))
    c = TestClient(create_app(s, ctx))
    assert c.get("/api/config").json()["uploadsEnabled"] is False
    cid = new_case(c)
    r = upload(c, cid, jpeg)
    assert r.status_code == 403
    assert "text" in r.json()["detail"].lower()
    assert c.put(f"/api/cases/{cid}/description", json={"text": "Operators check parts by hand."},
                 headers=ALICE).status_code == 204
    assert c.post(f"/api/cases/{cid}/analyze", headers=ALICE).status_code == 200


def test_auth_required(client):
    assert client.post("/api/cases", json={}).status_code == 401
    assert client.post("/api/cases", json={}, headers={"X-Dev-User": "bad user!"}).status_code == 401


def test_other_users_cannot_see_or_touch_a_case(client, jpeg):
    cid = new_case(client)
    for method, path in [("get", f"/api/cases/{cid}"), ("delete", f"/api/cases/{cid}"),
                         ("post", f"/api/cases/{cid}/analyze"), ("get", f"/api/cases/{cid}/question")]:
        assert getattr(client, method)(path, headers=BOB).status_code == 404
    assert upload(client, cid, jpeg, headers=BOB).status_code == 404
    assert client.get(f"/api/cases/{cid}", headers=ALICE).status_code == 200
    assert client.get("/api/cases", headers=BOB).json() == []


def test_sample_is_public_and_costs_nothing(client):
    r = client.get("/api/sample")
    assert r.status_code == 200 and r.json()["meta"]["generatedWith"] == "fake-llm"
    assert client.ctx.llm.calls == []


def test_unsupported_and_oversize_uploads(client):
    cid = new_case(client)
    assert upload(client, cid, b"GIF89a" + b"0" * 100).status_code == 422
    assert upload(client, cid, b"x" * (21 * 1024 * 1024)).status_code == 413
    assert upload(client, cid, b"<script>alert(1)</script>", name="evil.jpg").status_code == 422


def test_media_after_analysis_rejected(client, jpeg):
    cid = new_case(client)
    upload(client, cid, jpeg)
    client.post(f"/api/cases/{cid}/analyze", headers=ALICE)
    assert upload(client, cid, jpeg).status_code == 409


def test_daily_case_cap(client):
    for _ in range(3):
        new_case(client)
    assert client.post("/api/cases", json={}, headers=ALICE).status_code == 429
    assert client.post("/api/cases", json={}, headers=BOB).status_code == 201


def test_rate_limit():
    s = Settings(env="test", rate_limit_per_minute=3)
    c = TestClient(create_app(s, build_context(s)))
    codes = [c.get("/api/cases", headers=ALICE).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]


def test_validation_errors(client):
    cid = new_case(client)
    assert client.post(f"/api/cases/{cid}/answers", json={"field": "nope", "answer": "x"}, headers=ALICE).status_code in (409, 422)
    assert client.post(f"/api/cases/{cid}/brief", json={"opportunity_id": "o1", "budget_low_inr": 5, "budget_high_inr": 1}, headers=ALICE).status_code == 422
    assert client.post(f"/api/cases/{cid}/analyze", headers=ALICE).status_code == 400  # nothing to analyse


def test_security_headers_and_cors(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    ok = client.options("/api/cases", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/cases", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_no_secrets_or_stack_traces_in_errors(client):
    r = client.get("/api/cases/does-not-exist", headers=ALICE)
    assert r.json() == {"detail": "not found"}


def test_audit_log_has_no_pii(client, jpeg):
    cid = new_case(client)
    upload(client, cid, jpeg)
    client.put(f"/api/cases/{cid}/description", json={"text": "call me on 98765 43210"}, headers=ALICE)
    dump = str(client.ctx.cases.s.repo.audit)
    assert "98765" not in dump and "case_created" in dump
    assert client.ctx.cases.s.repo.get_case(cid)["description"].count("98765") == 0


def test_production_guard():
    with pytest.raises(ValueError):
        Settings(env="production")
    with pytest.raises(ValueError):
        Settings(env="production", auth_mode="firebase", llm_mode="vertex", store_mode="firestore",
                 privacy_mode="gcp", media_mode="gcs", gcp_project="p", gcp_location="l", media_bucket="b")  # no model id
    ok = Settings(env="production", auth_mode="firebase", llm_mode="vertex", store_mode="firestore",
                  privacy_mode="gcp", media_mode="gcs", gcp_project="p", gcp_location="l",
                  gemini_model="m", media_bucket="b")
    assert ok.env == "production"


def test_docs_disabled_in_production():
    s = Settings(env="production", auth_mode="firebase", llm_mode="vertex", store_mode="firestore",
                 privacy_mode="gcp", media_mode="gcs", gcp_project="p", gcp_location="l",
                 gemini_model="m", media_bucket="b")
    from fastapi import FastAPI
    from app.deps import AppContext
    stub = AppContext(settings=s, cases=None, limiter=None, llm=None)  # type: ignore[arg-type]
    app = create_app(s, stub)
    assert app.docs_url is None and app.openapi_url is None
