import secrets

import firebase_admin
import google.auth.transport.requests
import google.oauth2.id_token
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from app.config import get_settings


_bearer = HTTPBearer(auto_error=False)

INTERNAL_SECRET_HEADER = "X-Internal-Secret"


def _ensure_app() -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": get_settings().auth_project_id})


async def verify_firebase_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    _ensure_app()
    try:
        decoded = firebase_auth.verify_id_token(creds.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token: missing uid")
    return uid


def _verify_oidc_bearer(token: str, expected_audience: str, expected_sa: str) -> None:
    """Verify a Google OIDC identity token via the tokeninfo endpoint.

    Raises HTTPException(403) if the token is invalid, expired, has the wrong
    audience, or was issued for a different service account.
    """
    try:
        auth_req = google.auth.transport.requests.Request()
        id_info = google.oauth2.id_token.verify_oauth2_token(token, auth_req, expected_audience)
    except Exception as exc:
        raise HTTPException(status_code=403, detail=f"OIDC token verification failed: {exc}") from exc
    caller_email = id_info.get("email", "")
    if caller_email != expected_sa:
        raise HTTPException(
            status_code=403,
            detail=f"OIDC token service account mismatch: got {caller_email}",
        )


async def require_internal_secret(
    request: Request,
    x_internal_secret: str | None = Header(default=None),
) -> None:
    """Guard the /internal/* worker routes.

    Local (INTERNAL_INVOKER_SA unset): shared-secret check only.
    Production (INTERNAL_INVOKER_SA set): requires both a valid shared secret
    AND a Google OIDC bearer token whose audience matches FASTAPI_INTERNAL_BASE_URL
    and whose service-account email matches INTERNAL_INVOKER_SA (MD-8).
    """
    settings = get_settings()
    configured = settings.internal_task_secret
    if not configured:
        raise HTTPException(status_code=503, detail="Internal endpoint is not configured")
    if not x_internal_secret or not secrets.compare_digest(x_internal_secret, configured):
        raise HTTPException(status_code=403, detail="Invalid or missing internal secret")

    # Production OIDC layer: only enforced when INTERNAL_INVOKER_SA is set.
    if settings.internal_invoker_sa:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=403, detail="Missing OIDC bearer token")
        token = auth_header[len("Bearer "):]
        audience = (settings.fastapi_internal_base_url or "").rstrip("/")
        if not audience:
            raise HTTPException(status_code=503, detail="FASTAPI_INTERNAL_BASE_URL not configured")
        _verify_oidc_bearer(token, audience, settings.internal_invoker_sa)
