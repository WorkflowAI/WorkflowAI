# pyright: reportPrivateUsage=false
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.exceptions import HTTPException

from api.routers.mcp import mcp_server


class _DummyRequest:
    """Lightweight request replacement exposing only headers."""

    def __init__(self, headers: dict[str, str]):
        self.headers = headers


async def _dummy_find_tenant(_: Any, __: Any, ___: Any) -> None:
    """Stub for SecurityService.find_tenant that always returns *None* (invalid token)."""
    return


class _DummySystemStorage:  # noqa: D101 – internal testing stub
    def __init__(self):
        self.organizations = SimpleNamespace()


async def _call_get_task_tuple() -> Any:
    """Helper to keep the call in one place for the invalid-token test."""
    await mcp_server.get_task_tuple_from_task_id("dummy-agent")


# Missing bearer token ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "callable_under_test",
    [mcp_server.get_mcp_service, _call_get_task_tuple],
)
async def test_missing_bearer_token_raises(
    callable_under_test: Callable[[], Awaitable[Any]],
    monkeypatch: pytest.MonkeyPatch,
):
    """Ensure a 401 is returned when no *Authorization* header is present."""

    monkeypatch.setattr(
        mcp_server,
        "get_http_request",
        lambda: _DummyRequest(headers={}),
        raising=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await callable_under_test()

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing bearer token"


# Invalid bearer token ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "callable_under_test",
    [mcp_server.get_mcp_service, _call_get_task_tuple],
)
async def test_invalid_bearer_token_raises(
    callable_under_test: Callable[[], Awaitable[Any]],
    monkeypatch: pytest.MonkeyPatch,
):
    """Ensure a 401 is returned when the bearer token is invalid (tenant not found)."""

    # Provide a fake request with an *Authorization* header.
    monkeypatch.setattr(
        mcp_server,
        "get_http_request",
        lambda: _DummyRequest(headers={"Authorization": "Bearer invalid-token"}),
        raising=True,
    )

    # Patch *SecurityService.find_tenant* to simulate an unknown token.
    monkeypatch.setattr(mcp_server.SecurityService, "find_tenant", _dummy_find_tenant, raising=True)

    # Patch storage helpers used before *find_tenant* is called so they don't hit real infra.
    monkeypatch.setattr(
        mcp_server.storage,
        "shared_encryption",
        lambda: None,
        raising=True,
    )
    monkeypatch.setattr(
        mcp_server.storage,
        "system_storage",
        lambda _: _DummySystemStorage(),  # type: ignore[misc]
        raising=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await callable_under_test()

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid bearer token"
