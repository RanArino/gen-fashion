import firebase_admin
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from app.config import get_settings


_bearer = HTTPBearer(auto_error=False)


def _ensure_app() -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": get_settings().project_id})


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
