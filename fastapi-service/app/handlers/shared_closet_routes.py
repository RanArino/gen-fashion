from fastapi import APIRouter, Depends

from app.auth import verify_firebase_token
from app.dependencies import get_shared_closet_gallery_use_case
from app.use_cases.styling import SharedClosetGalleryUseCase


router = APIRouter()


@router.get("")
async def list_shared_closets(
    _user_id: str = Depends(verify_firebase_token),
    use_case: SharedClosetGalleryUseCase = Depends(get_shared_closet_gallery_use_case),
):
    return {"closets": await use_case.list_closets()}


@router.get("/{closet_id}/items")
async def list_shared_closet_items(
    closet_id: str,
    _user_id: str = Depends(verify_firebase_token),
    use_case: SharedClosetGalleryUseCase = Depends(get_shared_closet_gallery_use_case),
):
    return {"items": await use_case.list_items(closet_id)}
