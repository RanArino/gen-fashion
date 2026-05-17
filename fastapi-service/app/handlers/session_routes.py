from fastapi import APIRouter, HTTPException


router = APIRouter()


@router.post("")
async def create_session():
    """Create a style session (M5-1)."""
    raise HTTPException(status_code=501, detail="Implement in M5-1")


@router.post("/{session_id}/source")
async def select_source(session_id: str):
    """Select clothing source (M5-3)."""
    raise HTTPException(status_code=501, detail="Implement in M5-3")


@router.get("/{session_id}/stream")
async def stream_session_events(session_id: str):
    """Stream agent events via SSE (M5-9)."""
    raise HTTPException(status_code=501, detail="Implement in M5-9")
