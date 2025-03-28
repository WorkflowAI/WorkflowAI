import json
import os
from typing import Any

import httpx
import pytest

from core.storage.file_storage import FileData
from core.storage.s3.s3_file_storage import S3FileStorage


@pytest.fixture()
def s3_file_storage():
    store = S3FileStorage(
        connection_string=os.getenv(
            "TEST_S3_CONNECTION_STRING",
            "s3://minio:miniosecret@localhost:9000/workflowai-test-task-runs?secure=false",
        ),
    )
    clt: Any = store._s3_client  # pyright: ignore[reportPrivateUsage]

    try:
        clt.head_bucket(Bucket="workflowai-test-task-runs")
    except Exception:
        # Create bucket if it doesn't exist
        clt.create_bucket(Bucket="workflowai-test-task-runs")

        # Make bucket public

        clt.put_bucket_policy(
            Bucket="workflowai-test-task-runs",
            Policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "PublicReadGetObject",
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": ["arn:aws:s3:::workflowai-test-task-runs/*"],
                        },
                    ],
                },
            ),
        )

    return store


@pytest.mark.skip("Skipping S3 test")
async def test_store_file(s3_file_storage: S3FileStorage):
    file = FileData(
        contents=b"Hello, world!",
        content_type="text/plain",
    )

    url = await s3_file_storage.store_file(file, "test")
    assert url is not None

    async with httpx.AsyncClient() as client:
        content = await client.get(url)
        assert content.status_code == 200
        assert content.content == b"Hello, world!"
