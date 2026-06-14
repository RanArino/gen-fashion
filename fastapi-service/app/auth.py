import secrets

import firebase_admin
from fastapi import Depends, Header, HTTPException
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


async def require_internal_secret(
    x_internal_secret: str | None = Header(default=None),
) -> None:
    """Guard the /internal/* worker routes with a shared secret.

    These routes act on a caller-supplied ``userId`` and must never be openly
    reachable. Fails closed: if no secret is configured the route is locked
    (503) rather than left open. Production hardening (verify a Cloud Tasks
    OIDC token + Cloud Run internal ingress) is a separate, BLOCKING deploy
    gate tracked in the M2 ExecPlan — this secret is the dev/defense-in-depth
    seam that gate slots into.
    """
    configured = get_settings().internal_task_secret
    if not configured:
        raise HTTPException(status_code=503, detail="Internal endpoint is not configured")
    if not x_internal_secret or not secrets.compare_digest(x_internal_secret, configured):
        raise HTTPException(status_code=403, detail="Invalid or missing internal secret")
