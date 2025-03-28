import asyncio
import hashlib
import logging
import mimetypes
from typing import override
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from core.storage.file_storage import CouldNotStoreFileError, FileData, FileStorage


class S3FileStorage(FileStorage):
    def __init__(self, connection_string: str, bucket_name: str | None = None):
        parsed = urlparse(connection_string)
        host = parsed.hostname
        port = parsed.port
        insecure = "secure=false" in parsed.query.lower()
        self.host = f"{'http' if insecure else 'https'}://{host}"
        if port:
            self.host += f":{port}"
        self.bucket_name = bucket_name or parsed.path.lstrip("/")
        self._logger = logging.getLogger(__name__)
        self._s3_client = boto3.client(
            "s3",
            endpoint_url=self.host,
            aws_access_key_id=parsed.username,
            aws_secret_access_key=parsed.password,
        )

    def _put_object(self, key: str, body: bytes, content_type: str):
        self._s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    @override
    async def store_file(self, file: FileData, folder_path: str) -> str:
        # Generate a unique filename using content hash
        content_hash = hashlib.sha256(file.contents).hexdigest()
        extension = mimetypes.guess_extension(file.content_type) if file.content_type else None
        key = f"{folder_path}/{content_hash}{extension or ''}"

        try:
            await asyncio.get_running_loop().run_in_executor(
                None,
                self._put_object,
                key,
                file.contents,
                file.content_type or "application/octet-stream",
            )

            return f"{self.host}/{self.bucket_name}/{key}"
        except ClientError as e:
            self._logger.exception(
                "Failed to store file in S3",
                extra={"bucket": self.bucket_name, "key": key},
                exc_info=e,
            )
            raise CouldNotStoreFileError() from e
