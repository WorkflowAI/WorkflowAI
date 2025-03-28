from __future__ import annotations

import boto3
import httpx
from botocore.auth import SigV4Auth  # pyright: ignore [reportMissingTypeStubs]
from botocore.awsrequest import AWSRequest  # pyright: ignore [reportMissingTypeStubs]

# Strongly inspired by https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/lib/bedrock/_auth.py


def _get_session(
    *,
    aws_access_key: str | None,
    aws_secret_key: str | None,
    aws_session_token: str | None,
    region: str | None,
):
    return boto3.Session(
        region_name=region,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        aws_session_token=aws_session_token,
    )


def get_auth_headers(
    *,
    method: str,
    url: str,
    headers: httpx.Headers,
    aws_access_key: str | None,
    aws_secret_key: str | None,
    aws_session_token: str | None,
    region: str | None,
    data: str | None,
) -> dict[str, str]:
    session = _get_session(
        region=region,
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key,
        aws_session_token=aws_session_token,
    )

    headers = headers.copy()

    request = AWSRequest(method=method.upper(), url=url, headers=headers, data=data)
    credentials = session.get_credentials()  # type: ignore

    signer = SigV4Auth(credentials, "bedrock", session.region_name)  # type: ignore
    signer.add_auth(request)  # type: ignore

    prepped = request.prepare()

    return {key: value for key, value in dict(prepped.headers).items() if value is not None}  # type: ignore
