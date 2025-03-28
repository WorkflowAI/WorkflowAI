import hashlib
import logging
import mimetypes
from typing import override

from azure.core.exceptions import ResourceExistsError
from azure.core.pipeline.transport import AioHttpTransport
from azure.storage.blob.aio import BlobClient, BlobServiceClient

from core.storage.file_storage import CouldNotStoreFileError, FileData, FileStorage


class AzureBlobFileStorage(FileStorage):
    def __init__(self, connection_string: str, container_name: str):
        self.connection_string = connection_string
        self.container_name = container_name

        self._logger = logging.getLogger(__name__)

    async def _get_blob_service_client(self) -> BlobServiceClient:
        return BlobServiceClient.from_connection_string(
            self.connection_string,
            # TODO: refine these settings after monitoring performance
            transport=AioHttpTransport(
                connection_timeout=300.0,
                read_timeout=300.0,
                retries=3,
                maximum_valid_request_size=500 * 1024 * 1024,
            ),
        )

    @override
    async def store_file(self, file: FileData, folder_path: str) -> str:
        # folder_path is like /{tenant}/{task_id}

        content_hash = hashlib.sha256(file.contents).hexdigest()
        extension = mimetypes.guess_extension(file.content_type) if file.content_type else None
        blob_name = f"{folder_path}/{content_hash}{extension or ''}"

        async with await self._get_blob_service_client() as blob_service_client:
            try:
                blob_client: BlobClient = blob_service_client.get_blob_client(
                    container=self.container_name,
                    blob=blob_name,
                )

                try:
                    await blob_client.upload_blob(
                        file.contents,
                        content_type=file.content_type,
                        overwrite=False,
                    )
                    return blob_client.url  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                except ResourceExistsError:
                    # If the file already exists, we don't need to do anything
                    return blob_client.url  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            except Exception as e:
                raise CouldNotStoreFileError() from e
