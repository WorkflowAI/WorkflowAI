import re
from collections.abc import Callable
from typing import Any, Iterator, cast
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.routing import Mount
from httpx import AsyncClient
from starlette.routing import Route

from api.dependencies.security import (
    final_tenant_data,
    url_public_organization,
    user_auth_dependency,
)
from api.services.keys import InvalidToken
from core.domain.models import Model
from core.domain.tenant_data import PublicOrganizationData, TenantData
from core.domain.users import User
from core.utils import no_op

from .main import app


def _include_methods(methods: set[str] | None, exc_methods: set[str] | None) -> Callable[[str], bool]:
    if methods:
        if exc_methods:
            return lambda m: m in methods and m not in exc_methods
        return lambda m: m in methods
    if exc_methods:
        return lambda m: m not in exc_methods
    return lambda _: True


# Some routes should be accessible without any auth
# Only GET requests though
_PUBLIC_ROUTES = {
    "/v1/models",
    "/probes/health",
    "/probes/readiness",
    "/openapi.json",
    "/redoc",
    "/docs",
}


def authenticated_routes(  # noqa: C901
    prefix: str = "",
    methods: set[str] | None = None,
    exc_methods: set[str] | None = None,
) -> Iterator[tuple[str, str]]:
    not_authenticated = {
        *_PUBLIC_ROUTES,
        "/docs/oauth2-redirect",
        "/webhooks/clerk",
        "/webhooks/stripe",
        "/organizations/{tenant}",
        "/agents/home/messages",
        "/agents/home/agents/preview",
        "/v1/feedback",
        "/webhooks/slack",
        "/webhooks/slack/",
        "/webhooks/slack/actions",
        "/webhooks/slack/actions/",
        "/webhooks/helpscout",
        "/webhooks/helpscout/",
        "/v1/chat/completions",  # raises a 422 and not a 403
    }

    method_predicate = _include_methods(methods, exc_methods)

    for route in app.routes:
        # TODO: dedicated test for MCP routes auth
        if isinstance(route, Mount) and (route.path.startswith("/_mcp") or route.path.startswith("/mcp")):
            continue

        assert isinstance(route, Route)
        if not route.methods:
            continue

        if route.path in not_authenticated:
            continue

        if not route.path.startswith(prefix):
            continue

        for method in route.methods:
            if method_predicate(method):
                yield route.path, method


class TestAuthentication:
    @pytest.mark.parametrize("path,method", authenticated_routes())
    async def test_required_bearer(self, path: str, method: str, test_api_client: AsyncClient, mock_tenant_dep: Mock):
        mock_tenant_dep.side_effect = HTTPException(403, "Forbidden")

        res = await test_api_client.request(method, path, headers={"Authorization": "bla"})
        assert res.status_code == 403, f"Expected 403 for {path}"

    @pytest.mark.parametrize("path,method", authenticated_routes())
    async def test_invalid_user_auth(
        self,
        path: str,
        method: str,
        test_api_client: AsyncClient,
        mock_key_ring: Mock,
        mock_user_dep: Mock,
    ):
        mock_key_ring.verify.side_effect = InvalidToken()
        mock_user_dep.side_effect = user_auth_dependency

        mock_user_dep.reset_mock()

        res = await test_api_client.request(method, path, headers={"Authorization": "Bearer invalid_bearer"})
        assert res.status_code == 401, f"Expected 401 for {path}"

        mock_user_dep.assert_called_once()

    @pytest.mark.parametrize("path,method", authenticated_routes(prefix="/{tenant}/agents/{task_id}", methods={"GET"}))
    async def test_not_allowed_if_task_not_public(
        self,
        path: str,
        method: str,
        mock_user_dep: Mock,
        test_api_client: AsyncClient,
        mock_storage: Mock,
        mock_storage_for_tenant: Mock,
        mock_encryption: Mock,
        test_app: FastAPI,
    ):
        del test_app.dependency_overrides[final_tenant_data]
        del test_app.dependency_overrides[url_public_organization]
        del test_app.dependency_overrides[user_auth_dependency]

        mock_user_dep.return_value = User(
            tenant="another_tenant",
            sub="auser",
        )

        mock_storage.tasks.is_task_public.return_value = False
        mock_storage.organizations.find_tenant_for_org_id.return_value = TenantData(tenant="test")
        mock_storage.organizations.get_public_organization.return_value = PublicOrganizationData(
            tenant="tenant_from_url",
            uid=11,
        )

        path = path.replace("{tenant}", "tenant_slug").replace("{task_id}", "123")
        res = await test_api_client.request(method, path, headers={"Authorization": "Bearer bla"})
        assert res.status_code == 404, f"Expected 404 for {path}"

        mock_storage_for_tenant.assert_called_with(
            tenant="tenant_from_url",
            encryption=mock_encryption,
            event_router=no_op.event_router,
            tenant_uid=11,
        )
        mock_storage.tasks.is_task_public.assert_called_with("123")


class TestModelsEndpoint:
    async def test_models_endpoint_no_auth(self, test_api_client: AsyncClient, mock_tenant_dep: Mock):
        # Making sure we raise if the tenant dep is called
        mock_tenant_dep.side_effect = ValueError("test")
        res = await test_api_client.get("/v1/models?raw=true")
        assert res.status_code == 200, "Expected /models endpoint to be accessible without authentication"

        # Add some basic checks to ensure the response contains expected data
        data = res.json()
        assert isinstance(data, list)
        assert data

    async def test_openai_compatibility(self, test_api_client: AsyncClient, mock_tenant_dep: Mock):
        # Making sure we raise if the tenant dep is called
        mock_tenant_dep.side_effect = ValueError("test")
        res = await test_api_client.get("/v1/models")
        assert res.status_code == 200, "Expected /models endpoint to be accessible without authentication"

        # Add some basic checks to ensure the response contains expected data
        data = res.json()
        assert isinstance(data, dict)
        assert data["object"] == "list"
        assert isinstance(data["data"], list)

        first_model = cast(dict[str, Any], data["data"][0])
        assert first_model["object"] == "model"
        assert "capabilities" in first_model
        assert "supports" in first_model  # Legacy field for backward compatibility
        assert "parallel_tool_calls" in first_model["supports"]
        assert "pricing" in first_model
        pricing = cast(dict[str, Any], first_model["pricing"])
        assert "input_token_usd" in pricing
        assert "output_token_usd" in pricing

        assert "release_date" in first_model
        release_date = cast(str, first_model["release_date"])
        assert re.match(r"\d{4}-\d{2}-\d{2}", release_date)

        # Test new capabilities structure
        capabilities = cast(dict[str, Any], first_model["capabilities"])
        assert "json_mode" in capabilities
        assert "tool_calling" in capabilities
        assert "input_image" in capabilities
        assert "output_text" in capabilities

    async def test_models_endpoint_order_check(self, test_api_client: AsyncClient, mock_tenant_dep: Mock):
        # Making sure we raise if the tenant dep is called
        mock_tenant_dep.side_effect = ValueError("test")
        res = await test_api_client.get("/v1/models?raw=true")
        assert res.status_code == 200, "Expected /models endpoint to be accessible without authentication"

        # Add some basic checks to ensure the response contains expected data
        data = res.json()
        assert isinstance(data, list)
        assert data[0] == Model.GPT_41_LATEST.value
        assert data[1] == Model.GEMINI_2_0_FLASH_LATEST.value
        assert data[2] == Model.CLAUDE_4_SONNET_LATEST.value
