from typing import Any, Literal, Protocol

class S3Client(Protocol):
    def put_object(self, Bucket: str, Key: str, Body: Any, ContentType: str) -> Any: ...

def client(
    service_name: Literal["s3"],
    /,
    endpoint_url: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
) -> S3Client: ...

class Session:
    def __init__(
        self,
        /,
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
    ) -> None: ...
