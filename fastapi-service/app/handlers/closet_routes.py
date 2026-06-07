from fastapi import APIRouter, Depends, HTTPException, Response, status
from app.auth import verify_firebase_token
from app.dependencies import (
    get_delete_closet_item_use_case,
    get_download_url_use_case,
    get_register_clothing_item_use_case,
    get_upload_url_use_case,
)
from app.domain.closet import ClosetItemNotFound, MaxClosetItemsExceeded
from app.use_cases.closet import (
    DeleteClosetItemUseCase,
    GetDownloadUrlUseCase,
    GetUploadUrlUseCase,
    RegisterClothingItemUseCase,
)


router = APIRouter()


@router.get("/upload-url")
async def get_upload_url(
    item_id: str,
    user_id: str = Depends(verify_firebase_token),
    use_case: GetUploadUrlUseCase = Depends(get_upload_url_use_case),
):
    """Get signed upload URL for image (M2-3)."""
    try:
        upload_url = await use_case.execute(user_id, item_id)
    except MaxClosetItemsExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return {"upload_url": upload_url, "item_id": item_id}


@router.get("/items/{item_id}/download-url")
async def get_download_url(
    item_id: str,
    user_id: str = Depends(verify_firebase_token),
    use_case: GetDownloadUrlUseCase = Depends(get_download_url_use_case),
):
    """Get a short-lived signed GET URL for the caller's own object (M2-11 thumbnails)."""
    url = await use_case.execute(user_id, item_id)
    return {"download_url": url}


@router.post("/items/{item_id}/complete")
async def register_item(
    item_id: str,
    user_id: str = Depends(verify_firebase_token),
    use_case: RegisterClothingItemUseCase = Depends(get_register_clothing_item_use_case),
):
    """Register a clothing item (M2-4)."""
    return await use_case.execute(user_id, item_id)


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: str,
    user_id: str = Depends(verify_firebase_token),
    use_case: DeleteClosetItemUseCase = Depends(get_delete_closet_item_use_case),
):
    """Delete a closet item (M2-6)."""
    try:
        await use_case.execute(user_id, item_id)
    except ClosetItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
