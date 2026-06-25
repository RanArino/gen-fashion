from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from app.auth import require_internal_secret
from app.dependencies import get_process_uploaded_item_use_case
from app.use_cases.closet import ProcessUploadedClothingItemUseCase


# Every route on this router is guarded by the shared internal secret. The
# /internal prefix gives no network isolation on its own (the app is published
# on the same host port as the public routes), so the guard is mandatory.
router = APIRouter(dependencies=[Depends(require_internal_secret)])


class ProcessUploadTask(BaseModel):
    user_id: str = Field(alias="userId")
    item_id: str


@router.post("/internal/tasks/process-upload")
async def process_upload(
    task: ProcessUploadTask,
    use_case: ProcessUploadedClothingItemUseCase = Depends(get_process_uploaded_item_use_case),
):
    await use_case.execute(task.user_id, task.item_id)
    return {"status": "ok"}
