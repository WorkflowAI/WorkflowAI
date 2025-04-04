from typing import Any, Optional
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

import api.services.groups as groups_module
from api.dependencies.provider_factory import _provider_factory  # pyright: ignore [reportPrivateUsage]
from api.dependencies.services import group_service, models_service
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.tenant_data import TenantData
from core.domain.users import UserIdentifier
from tests.models import task_variant


@pytest.fixture(scope="function")
def mock_detect_chain_of_thought():
    with patch.object(groups_module, "run_detect_chain_of_thought_task") as mock:
        yield mock


@pytest.fixture(scope="function")
def client_for_groups(
    test_api_client: AsyncClient,
    mock_storage: Mock,
    test_app: FastAPI,
    mock_detect_chain_of_thought: Mock,
    user: Optional[UserIdentifier] = None,
):
    # Using actual group service
    test_app.dependency_overrides[group_service] = group_service
    test_app.dependency_overrides[models_service] = models_service
    test_app.dependency_overrides[_provider_factory] = _provider_factory
    # Add mock for internal_tasks_service

    mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()

    def _get_or_create_task_group(
        task_id: str,
        task_schema_id: int,
        properties: TaskGroupProperties,
        tags: list[str],
        is_external: Optional[bool] = None,
        id: Optional[str] = None,
        user: Optional[UserIdentifier] = None,
    ):
        return TaskGroup(id="1", schema_id=task_schema_id, properties=properties, tags=tags, created_by=user)

    mock_storage.get_or_create_task_group.side_effect = _get_or_create_task_group
    mock_storage.organizations.get_organization.return_value = TenantData()
    return test_api_client


# TODO: remove since it's deprecated
class TestCreateGroup:
    @pytest.mark.parametrize("detect_chain_of_thought_return", [True, False])
    async def test_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client_for_groups: AsyncClient,
        mock_storage: Mock,
        detect_chain_of_thought_return: bool,
    ) -> None:
        # Override the async chain of thought detection method to return the parameter value directly
        async def fake_is_chain_of_thought(
            group_service: groups_module.GroupService,
            task_instructions: str | None,
            task_output_schema: dict[str, Any],
        ) -> bool:
            return detect_chain_of_thought_return

        monkeypatch.setattr(groups_module.GroupService, "_is_chain_of_thought_detected", fake_is_chain_of_thought)

        res = await client_for_groups.post(
            "/_/agents/1/schemas/1/groups",
            json={"properties": {"instructions": "test instructions", "model": "gpt-4o-2024-08-06"}},
        )
        assert res.status_code == 200
        response_json = res.json()

        # Validate the response structure
        expected_response = {
            "id": "1",
            "schema_id": 1,
            "iteration": 0,
            "properties": {
                "has_templated_instructions": False,
                "instructions": "test instructions",
                "is_chain_of_thought_enabled": detect_chain_of_thought_return,
                "model": "gpt-4o-2024-08-06",
                "runner_name": "WorkflowAI",
                "runner_version": "v0.1.0",
                "task_variant_id": "task_version_id",
                "temperature": 0.0,
            },
            "tags": [
                f"is_chain_of_thought_enabled={str(detect_chain_of_thought_return).lower()}",
                "model=gpt-4o-2024-08-06",
                "temperature=0",
            ],
            "similarity_hash": response_json["similarity_hash"],
            "created_by": {"user_email": "g"},
            "run_count": 0,
        }
        assert response_json == expected_response

        mock_storage.get_or_create_task_group.assert_called_once()

    async def test_wrong_provider(self, client_for_groups: AsyncClient, mock_storage: Mock) -> None:
        res = await client_for_groups.post(
            "/_/agents/1/schemas/1/groups",
            json={"properties": {"provider": "not_openai", "model": "gpt-4o-2024-08-06"}},
        )
        assert res.status_code == 400
        assert res.json() == {
            "error": {
                "code": "invalid_run_properties",
                "message": "Provider not_openai is not valid",
                "status_code": 400,
            },
        }

        mock_storage.get_or_create_task_group.assert_not_called()

    async def test_wrong_model(self, client_for_groups: AsyncClient, mock_storage: Mock) -> None:
        res = await client_for_groups.post(
            "/_/agents/1/schemas/1/groups",
            json={"properties": {"model": "not_gpt-4o-2024-05-13"}},
        )
        assert res.status_code == 400
        assert res.json() == {
            "error": {
                "code": "invalid_run_properties",
                "message": "Model not_gpt-4o-2024-05-13 is not valid",
                "status_code": 400,
            },
        }

        mock_storage.get_or_create_task_group.assert_not_called()

    async def test_model_and_provider(self, client_for_groups: AsyncClient, mock_storage: Mock) -> None:
        res = await client_for_groups.post(
            "/_/agents/1/schemas/1/groups",
            json={"properties": {"model": "gpt-4o-2024-11-20", "provider": "openai"}},
        )
        assert res.status_code == 200

        mock_storage.get_or_create_task_group.assert_called_once()

    async def test_model_and_wrong_provider(
        self,
        client_for_groups: AsyncClient,
        mock_storage: Mock,
    ) -> None:
        res = await client_for_groups.post(
            "/_/agents/1/schemas/1/groups",
            json={"properties": {"model": "gpt-4o-2024-11-20", "provider": "groq"}},
        )
        assert res.status_code == 400

        assert res.json() == {
            "error": {
                "message": "Provider 'groq' does not support 'gpt-4o-2024-11-20'",
                "status_code": 400,
                "code": "provider_does_not_support_model",
                "details": {
                    "model": "gpt-4o-2024-11-20",
                    "provider": "groq",
                },
            },
        }

        mock_storage.get_or_create_task_group.assert_not_called()

    async def test_chain_of_thought_detection_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client_for_groups: AsyncClient,
        mock_storage: Mock,
    ) -> None:
        # Override the async chain of thought detection method to return the parameter value directly
        async def fake_is_chain_of_thought(
            group_service: groups_module.GroupService,
            task_instructions: str | None,
            task_output_schema: dict[str, Any],
        ) -> bool:
            raise Exception("test error")

        monkeypatch.setattr(groups_module.GroupService, "_is_chain_of_thought_detected", fake_is_chain_of_thought)

        res = await client_for_groups.post(
            "/_/agents/1/schemas/1/groups",
            json={"properties": {"instructions": "Hello", "model": "gpt-4o-2024-08-06", "provider": "openai"}},
        )

        # Verify the request still succeeds even if detection fails
        assert res.status_code == 200
        response_json = res.json()

        # Chain of thought should be False when detection fails
        assert "is_chain_of_thought_enabled" not in response_json["properties"]
