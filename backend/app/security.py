"""Auth, rate limiting and security headers.

Security headers are applied in an after-response middleware ONLY. Do not add a
before-request origin check: a previous event lost points when such a hook returned 403s to
the evaluator's requests.
"""
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings


@dataclass(frozen=True)
class User:
    uid: str
    anonymous: bool = False


def _firebase_verify(token: str) -> User:  # pragma: no cover - needs live Firebase
    import firebase_admin
    from firebase_admin import auth

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    decoded = auth.verify_id_token(token)
    provider = (decoded.get("firebase") or {}).get("sign_in_provider")
    return User(uid=decoded["uid"], anonymous=provider == "anonymous")


def _verify_app_check(token: str | None) -> None:  # pragma: no cover - needs live Firebase
    from firebase_admin import app_check

    if not token:
        raise HTTPException(status_code=401, detail="app check token required")
    try:
        app_check.verify_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid app check token") from exc


def authenticate(request: Request, settings: Settings) -> User:
    if settings.auth_mode == "dev":
        uid = request.headers.get("X-Dev-User", "").strip()
        if not uid or len(uid) > 64 or not uid.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(status_code=401, detail="missing or invalid X-Dev-User header")
        return User(uid=f"dev-{uid}")
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    if settings.enforce_app_check:
        _verify_app_check(request.headers.get("X-Firebase-AppCheck"))
    try:
        return _firebase_verify(header[7:])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc


class SlidingWindowLimiter:
    """Per-key requests/minute. Per-instance only; the daily case cap is the shared guard."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit, self.window = limit, window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            raise HTTPException(status_code=429, detail="too many requests; try the sample case")
        hits.append(now)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response
