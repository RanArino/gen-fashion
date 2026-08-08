from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from app.auth import verify_firebase_token
from app.dependencies import (
    get_delete_closet_item_use_case,
    get_download_url_use_case,
    get_import_suggested_item_use_case,
    get_register_clothing_item_use_case,
    get_upload_url_use_case,
    get_update_item_metadata_use_case,
)
from app.domain.closet import ClosetItemNotFound, MaxClosetItemsExceeded
from app.domain.styling import StyleSessionNotFound
from app.use_cases.closet import (
    DeleteClosetItemUseCase,
    GetDownloadUrlUseCase,
    GetUploadUrlUseCase,
    ImportSuggestedClosetItemUseCase,
    RegisterClothingItemUseCase,
    UpdateClosetItemMetadataUseCase,
)


router = APIRouter()


class ImportSuggestionRequest(BaseModel):
    session_id: str = Field(alias="sessionId")
    candidate_id: str = Field(alias="candidateId")


class UpdateItemMetadataRequest(BaseModel):
    gender: str | None = None
    category: str | None = None
    colors: list[str] | None = None
    season: str | None = None
    tags: list[str] | None = None
    ownership_status: str | None = Field(default=None, alias="ownershipStatus")
    intent_tags: list[str] | None = Field(default=None, alias="intentTags")


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


@router.post("/import-suggestion")
async def import_suggestion(
    request: ImportSuggestionRequest,
    user_id: str = Depends(verify_firebase_token),
    use_case: ImportSuggestedClosetItemUseCase = Depends(get_import_suggested_item_use_case),
):
    """Save a proposed Rakuten suggestion to the closet as Interesting (MK-6)."""
    try:
        return await use_case.execute(user_id, request.session_id, request.candidate_id)
    except StyleSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MaxClosetItemsExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/items/{item_id}")
async def update_item_metadata(
    item_id: str,
    request: UpdateItemMetadataRequest,
    user_id: str = Depends(verify_firebase_token),
    use_case: UpdateClosetItemMetadataUseCase = Depends(get_update_item_metadata_use_case),
):
    try:
        return await use_case.execute(user_id, item_id, **request.model_dump())
    except ClosetItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
