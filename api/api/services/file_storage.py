import logging
import os
from typing import override

from core.storage.file_storage import FileData, FileStorage


def _default_file_storage() -> FileStorage:
    # We return an empty blob storage if the env variables are not set

    connection_string = os.getenv("WORKFLOWAI_STORAGE_CONNECTION_STRING", "")
    if connection_string.startswith("DefaultEndpointsProtocol"):
        from core.storage.azure.azure_blob_file_storage import AzureBlobFileStorage

        return AzureBlobFileStorage(
            os.getenv("WORKFLOWAI_STORAGE_CONNECTION_STRING", ""),
            os.getenv("WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER", "workflowai-task-runs"),
        )

    if connection_string.startswith("s3://"):
        from core.storage.s3.s3_file_storage import S3FileStorage

        return S3FileStorage(
            connection_string,
            os.getenv("WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER", ""),
        )

    logging.getLogger(__name__).warning(
        "No file storage configured, using noop file storage. Set WORKFLOWAI_STORAGE_CONNECTION_STRING to use a real file storage.",
    )

    class NoopFileStorage(FileStorage):
        @override
        async def store_file(self, file: FileData, folder_path: str) -> str:
            return ""

    return NoopFileStorage()


shared_file_storage = _default_file_storage()
