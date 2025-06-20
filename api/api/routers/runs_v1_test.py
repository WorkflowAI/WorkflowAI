from typing import Any
from unittest.mock import Mock

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from api.routers.runs_v1 import SearchTaskRunsRequest
from api.services.version_test import mock_aiter
from core.domain.agent_run import AgentRun
from core.domain.task_info import TaskInfo
from core.domain.task_run_query import SerializableTaskRunQuery
from core.utils.uuid import uuid7
from tests.models import task_run_ser


class TestSearchTaskRunsRequestQuery:
    @pytest.mark.parametrize("field_name", ["metadata.key", "metadata.key.subkey"])
    def test_valid_field_name(self, field_name: str):
        request = SearchTaskRunsRequest.Query.model_validate(
            {"field_name": field_name, "operator": "is", "values": ["value"]},
        )
        assert request.field_name == field_name

    @pytest.mark.parametrize("field_name", [1, "[invalid]", "INSERT?", "INSERT INTO ", None])
    def test_invalid_field_name(self, field_name: Any):
        with pytest.raises(ValidationError):
            SearchTaskRunsRequest.Query.model_validate(
                {"field_name": field_name, "operator": "is", "values": ["value"]},
            )


class TestLatestRun:
    # test_api_client is in the arg to be sure the mock happens after the test_api_client is created
    @pytest.fixture()
    def returned_run(test_api_client: Any, mock_storage: Mock):
        run = task_run_ser(id=str(uuid7()), task_uid=1, task_schema_id=1, status="success")
        mock_storage.task_runs.fetch_task_run_resources.return_value = mock_aiter(run)
        mock_storage.tasks.get_task_info.return_value = TaskInfo(task_id="bla", uid=2)
        return run

    async def test_latest_run(
        self,
        test_api_client: AsyncClient,
        mock_storage: Mock,
        returned_run: AgentRun,
    ):
        response = await test_api_client.get("/v1/_/agents/bla/runs/latest")
        assert response.status_code == 200
        assert response.json()["id"] == returned_run.id

        mock_storage.task_runs.fetch_task_run_resources.assert_called_once_with(
            task_uid=2,
            query=SerializableTaskRunQuery(
                task_id="bla",
                exclude_fields={"llm_completions"},
                limit=1,
            ),
        )

    async def test_latest_run_with_status(
        self,
        test_api_client: AsyncClient,
        returned_run: AgentRun,
        mock_storage: Mock,
    ):
        response = await test_api_client.get("/v1/_/agents/bla/runs/latest?is_success=true")
        assert response.status_code == 200
        assert response.json()["id"] == returned_run.id

        mock_storage.task_runs.fetch_task_run_resources.assert_called_once_with(
            task_uid=2,
            query=SerializableTaskRunQuery(
                task_id="bla",
                exclude_fields={"llm_completions"},
                limit=1,
                status={"success"},
            ),
        )

    async def test_latest_with_schema_id(
        self,
        test_api_client: AsyncClient,
        returned_run: AgentRun,
        mock_storage: Mock,
    ):
        response = await test_api_client.get("/v1/_/agents/bla/runs/latest?schema_id=1")
        assert response.status_code == 200
        assert response.json()["id"] == returned_run.id

        mock_storage.task_runs.fetch_task_run_resources.assert_called_once_with(
            task_uid=2,
            query=SerializableTaskRunQuery(
                task_id="bla",
                task_schema_id=1,
                exclude_fields={"llm_completions"},
                limit=1,
            ),
        )

    async def test_latest_run_includes_metadata(
        self,
        test_api_client: AsyncClient,
        returned_run: AgentRun,
    ):
        """Test that metadata is included in the RunV1 response"""
        returned_run.metadata = {"environment": "test", "user_id": "123", "custom_field": "value"}

        response = await test_api_client.get("/v1/_/agents/bla/runs/latest")
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["id"] == returned_run.id
        assert response_data["metadata"] == {
            "environment": "test",
            "user_id": "123",
            "custom_field": "value",
        }

    async def test_latest_run_with_null_metadata(
        self,
        test_api_client: AsyncClient,
        returned_run: AgentRun,
    ):
        """Test that null metadata is handled correctly"""
        returned_run.metadata = None

        response = await test_api_client.get("/v1/_/agents/bla/runs/latest")
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["id"] == returned_run.id
        # metadata should not be present in response when it's None (due to response_model_exclude_none=True)
        assert "metadata" not in response_data


class TestGetRunByID:
    # test_api_client is in the arg to be sure the mock happens after the test_api_client is created
    @pytest.fixture()
    def returned_run(test_api_client: Any, mock_storage: Mock):
        run = task_run_ser(id=str(uuid7()), task_uid=1, task_schema_id=1, status="success")
        mock_storage.task_runs.fetch_task_run_resource.return_value = run
        mock_storage.tasks.get_task_info.return_value = TaskInfo(task_id="bla", uid=2)
        return run

    async def test_get_run_includes_metadata(
        self,
        test_api_client: AsyncClient,
        returned_run: AgentRun,
        mock_storage: Mock,
    ):
        """Test that metadata is included in the get_run response"""
        returned_run.metadata = {"environment": "production", "user_id": "456", "custom_data": "test_value"}

        response = await test_api_client.get(f"/v1/_/agents/test_task/runs/{returned_run.id}")
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["id"] == returned_run.id
        assert response_data["metadata"] == {
            "environment": "production",
            "user_id": "456",
            "custom_data": "test_value",
        }

        mock_storage.task_runs.fetch_task_run_resource.assert_called_once_with(
            ("bla", 2),
            returned_run.id,
            exclude={"llm_completions"},
            include=None,
        )
