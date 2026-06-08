from fastapi import APIRouter, HTTPException


router = APIRouter()


@router.get("/upload-url")
async def get_upload_url():
    """Get signed upload URL for image (M2-3)."""
    raise HTTPException(status_code=501, detail="Implement in M2-3")


@router.post("/items/{item_id}/complete")
async def register_item(item_id: str):
    """Register a clothing item (M2-4)."""
    raise HTTPException(status_code=501, detail="Implement in M2-4")


@router.delete("/items/{item_id}")
async def delete_item(item_id: str):
    """Delete a closet item (M2-6)."""
    raise HTTPException(status_code=501, detail="Implement in M2-6")
