import mimetypes

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from api.dependencies.security import TenantDep
from api.dependencies.services import FileStorageDep
from core.storage.file_storage import FileData

router = APIRouter(prefix="/upload")


class UploadFileResponse(BaseModel):
    url: str


def _content_type(file: UploadFile) -> str | None:
    if file.content_type:
        return file.content_type
    if not file.filename:
        return None
    return mimetypes.guess_type(file.filename)[0]


@router.post("/{task_id}", response_model=UploadFileResponse)
async def upload_file(
    file_storage: FileStorageDep,
    tenant: TenantDep,
    task_id: str,
    file: UploadFile,
) -> UploadFileResponse:
    url = await file_storage.store_file(
        FileData(
            filename=file.filename or "",
            contents=await file.read(),
            content_type=_content_type(file),
        ),
        f"{tenant}/{task_id}/uploads",
    )
    return UploadFileResponse(url=url)
