import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from api.dependencies.security import final_tenant_data, url_public_organization, user_organization
from api.routers.task_schemas import UpdateTaskInstructionsRequest
from core.domain.page import Page
from core.domain.task_info import TaskInfo
from core.domain.task_preview import TaskPreview
from core.domain.task_run import SerializableTaskRun
from core.domain.task_run_query import SerializableTaskRunQuery
from core.domain.tenant_data import PublicOrganizationData, TenantData
from core.domain.users import User
from core.storage.models import TaskUpdate
from core.tools import ToolKind
from core.utils import no_op
from tests.models import (
    task_variant,
)
from tests.utils import mock_aiter

GLOBAL_AVAILABLE_MODELS_COUNT = 54


@pytest.fixture(scope="function", autouse=True)
def mock_bedrock_model_region_map(patched_bedrock_config: None):
    # Make the patched environment used for everyone
    yield


class TestGetTaskSchema:
    @pytest.fixture(scope="function", autouse=True)
    async def reset_security_dependencies(self, test_app: FastAPI):
        del test_app.dependency_overrides[final_tenant_data]
        del test_app.dependency_overrides[user_organization]
        del test_app.dependency_overrides[url_public_organization]

    async def test_public_task(
        self,
        mock_user_dep: Mock,
        test_api_client: AsyncClient,
        mock_storage: Mock,
        mock_encryption: Mock,
        mock_storage_for_tenant: Mock,
    ):
        mock_user_dep.return_value = User(
            tenant="another_tenant",
            sub="auser",
        )
        mock_storage.tasks.is_task_public = AsyncMock(return_value=True)

        mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()
        mock_storage.organizations.get_public_organization.return_value = PublicOrganizationData(
            tenant="org_id_test",
            uid=11,
        )
        mock_storage.organizations.find_tenant_for_org_id.return_value = TenantData(tenant="another_tenant")

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="bla",
            name="",
            is_public=True,
            hidden_schema_ids=[],
            schema_details=[],
        )

        res = await test_api_client.get("/test/agents/123/schemas/1")
        assert res.status_code == 200

        mock_storage.organizations.get_public_organization.assert_called_with("test")

        # Last call is to check if task is public
        mock_storage_for_tenant.assert_called_once_with(
            tenant="org_id_test",
            tenant_uid=11,
            encryption=mock_encryption,
            event_router=no_op.event_router,
        )

    async def test_private_task_different_tenant(
        self,
        mock_tenant_dep: Mock,
        mock_user_dep: Mock,
        test_api_client: AsyncClient,
        mock_storage: Mock,
        mock_encryption: Mock,
        mock_storage_for_tenant: Mock,
    ):
        mock_user_dep.return_value = User(
            tenant="another_tenant",
            sub="auser",
        )
        mock_tenant_dep.side_effect = final_tenant_data
        mock_storage.tasks.is_task_public = AsyncMock(return_value=False)

        mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()
        mock_storage.organizations.get_public_organization.return_value = PublicOrganizationData(
            tenant="org_id_test",
            uid=11,
        )
        mock_storage.organizations.find_tenant_for_org_id.return_value = TenantData(tenant="another_tenant")

        res = await test_api_client.get("/test/agents/123/schemas/1")
        assert res.status_code == 404

        mock_storage_for_tenant.assert_called_once_with(
            tenant="org_id_test",
            tenant_uid=11,
            encryption=mock_encryption,
            event_router=no_op.event_router,
        )

    async def test_private_task_same_tenant(
        self,
        mock_tenant_dep: Mock,
        mock_user_dep: Mock,
        test_api_client: AsyncClient,
        mock_storage: Mock,
    ):
        mock_user_dep.return_value = User(
            tenant="test",
            sub="auser",
            org_id="test",
        )
        mock_tenant_dep.side_effect = final_tenant_data
        mock_storage.tasks.is_task_public = AsyncMock(return_value=False)

        mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()
        mock_storage.organizations.get_public_organization.return_value = PublicOrganizationData(tenant="org_id_test")
        mock_storage.organizations.find_tenant_for_org_id.return_value = TenantData(tenant="org_id_test")

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="bla",
            name="",
            is_public=True,
            hidden_schema_ids=[],
            schema_details=[],
        )

        res = await test_api_client.get("/test/agents/123/schemas/1")
        assert res.status_code == 200

    async def test_last_active_at(
        self,
        mock_user_dep: Mock,
        mock_tenant_dep: Mock,
        test_api_client: AsyncClient,
        mock_storage: Mock,
    ):
        mock_user_dep.return_value = User(
            tenant="test",
            sub="auser",
            org_id="test",
        )
        mock_tenant_dep.side_effect = final_tenant_data
        mock_storage.tasks.is_task_public = AsyncMock(return_value=False)

        mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()
        mock_storage.organizations.get_public_organization.return_value = PublicOrganizationData(tenant="org_id_test")
        mock_storage.organizations.find_tenant_for_org_id.return_value = TenantData(tenant="test")

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="bla",
            name="",
            is_public=True,
            hidden_schema_ids=[],
            schema_details=[
                {"schema_id": 1, "last_active_at": datetime(2024, 1, 1, tzinfo=timezone.utc)},
            ],
        )

        res = await test_api_client.get("/test/agents/123/schemas/1")
        assert res.status_code == 200
        assert res.json()["last_active_at"] == "2024-01-01T00:00:00Z"

    async def test_last_active_at_none(
        self,
        mock_user_dep: Mock,
        mock_tenant_dep: Mock,
        test_api_client: AsyncClient,
        mock_storage: Mock,
    ):
        mock_user_dep.return_value = User(
            tenant="test",
            sub="auser",
            org_id="test",
        )
        mock_tenant_dep.side_effect = final_tenant_data
        mock_storage.tasks.is_task_public = AsyncMock(return_value=False)

        mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()
        mock_storage.organizations.get_public_organization.return_value = PublicOrganizationData(tenant="org_id_test")
        mock_storage.organizations.find_tenant_for_org_id.return_value = TenantData(tenant="test")

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="bla",
            name="",
            is_public=True,
            hidden_schema_ids=[],
            schema_details=[],
        )

        res = await test_api_client.get("/test/agents/123/schemas/1")
        assert res.status_code == 200
        assert res.json()["last_active_at"] is None

    async def test_last_active_at_not_in_schema_details(
        self,
        mock_user_dep: Mock,
        mock_tenant_dep: Mock,
        test_api_client: AsyncClient,
        mock_storage: Mock,
    ):
        mock_user_dep.return_value = User(
            tenant="test",
            sub="auser",
            org_id="test",
        )
        mock_tenant_dep.side_effect = final_tenant_data
        mock_storage.tasks.is_task_public = AsyncMock(return_value=False)

        mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()
        mock_storage.organizations.get_public_organization.return_value = PublicOrganizationData(tenant="org_id_test")
        mock_storage.organizations.find_tenant_for_org_id.return_value = TenantData(tenant="test")

        mock_storage.tasks.get_task_info.return_value = TaskInfo(
            task_id="bla",
            name="",
            is_public=True,
            hidden_schema_ids=[],
            schema_details=[
                {"schema_id": 2, "last_active_at": datetime(2024, 1, 1, tzinfo=timezone.utc)},
            ],
        )

        res = await test_api_client.get("/test/agents/123/schemas/1")
        assert res.status_code == 200
        assert res.json()["last_active_at"] is None


@pytest.fixture(scope="function")
def mock_runs_service(test_app: FastAPI) -> Mock:
    from api.dependencies.services import runs_service as runs_service_dep
    from api.services.runs import RunsService

    runs_service = Mock(spec=RunsService)

    test_app.dependency_overrides[runs_service_dep] = lambda: runs_service

    return runs_service


class TestImportInputs:
    async def test_import_inputs(
        self,
        test_api_client: AsyncClient,
        mock_internal_tasks_service: Mock,
    ):
        mock_internal_tasks_service.input_import.import_input.return_value = [
            {"input_field": "value1"},
            {"input_field": "value2"},
        ]

        response = await test_api_client.post(
            "/test/agents/123/schemas/1/inputs/import",
            json={"inputs_text": "raw input data", "stream": False},
        )

        assert response.status_code == 200
        assert response.json() == {
            "imported_inputs": [
                {"input_field": "value1"},
                {"input_field": "value2"},
            ],
        }
        assert mock_internal_tasks_service.input_import.import_input.mock_calls[0].args[1] == "raw input data"

    async def test_import_inputs_with_file_and_text(
        self,
        test_api_client: AsyncClient,
        mock_internal_tasks_service: Mock,
    ):
        mock_internal_tasks_service.input_import.import_input.return_value = [
            {"input_field": "value1"},
            {"input_field": "value2"},
        ]

        response = await test_api_client.post(
            "/test/agents/123/schemas/1/inputs/import",
            json={
                "inputs_text": "raw input data",
                "inputs_file": {
                    "name": "test.txt",
                    "base64_data": "Sm9obiwgMzIsIEJvc3Rvbgo=",
                    "content_type": "text/plain",
                },
                "stream": False,
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "imported_inputs": [
                {"input_field": "value1"},
                {"input_field": "value2"},
            ],
        }
        assert (
            mock_internal_tasks_service.input_import.import_input.mock_calls[0].args[1]
            == """raw input data

Attached file content: John, 32, Boston
"""
        )

    async def test_import_inputs_with_file_only(
        self,
        test_api_client: AsyncClient,
        mock_internal_tasks_service: Mock,
    ):
        mock_internal_tasks_service.input_import.import_input.return_value = [
            {"input_field": "value1"},
            {"input_field": "value2"},
        ]

        response = await test_api_client.post(
            "/test/agents/123/schemas/1/inputs/import",
            json={
                "inputs_file": {
                    "name": "test.txt",
                    "base64_data": "Sm9obiwgMzIsIEJvc3Rvbgo=",
                    "content_type": "text/plain",
                },
                "stream": False,
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "imported_inputs": [
                {"input_field": "value1"},
                {"input_field": "value2"},
            ],
        }
        assert (
            mock_internal_tasks_service.input_import.import_input.mock_calls[0].args[1]
            == """Attached file content: John, 32, Boston
"""
        )

    async def test_import_inputs_with_neither_text_nor_file(
        self,
        test_api_client: AsyncClient,
        mock_internal_tasks_service: Mock,
    ):
        mock_internal_tasks_service.input_import.import_input.return_value = [
            {"input_field": "value1"},
            {"input_field": "value2"},
        ]

        response = await test_api_client.post(
            "/test/agents/123/schemas/1/inputs/import",
            json={
                "stream": False,
            },
        )

        assert response.status_code == 422
        assert response.json() == {
            "detail": "Either inputs_text or inputs_file must be provided",
        }
        mock_internal_tasks_service.input_import.import_input.assert_not_called()

    async def test_import_inputs_stream(
        self,
        test_api_client: AsyncClient,
        mock_internal_tasks_service: Mock,
    ):
        mock_internal_tasks_service.input_import.stream_import_input.return_value = mock_aiter(
            (0, {"input_field": "value1"}),
            (1, {"input_field": "value2"}),
        )

        async with test_api_client.stream(
            "POST",
            "/test/agents/123/schemas/1/inputs/import",
            json={"inputs_text": "raw input data", "stream": True},
        ) as response:
            assert response.status_code == 200
            chunks = [json.loads(chunk.replace(b"data: ", b"").decode()) async for chunk in response.aiter_raw()]

        assert chunks == [
            {"index": 0, "imported_input": {"input_field": "value1"}},
            {"index": 1, "imported_input": {"input_field": "value2"}},
        ]
        assert mock_internal_tasks_service.input_import.stream_import_input.mock_calls[0].args[1] == "raw input data"


class TestListRuns:
    # test default arguments for fetching runs

    async def test_list_run_excludes_llm_completions(
        self,
        test_api_client: AsyncClient,
        mock_runs_service: Mock,
        mock_storage: Mock,
    ):
        mock_storage.tasks.get_task_info.return_value = TaskInfo(task_id="task_id", uid=1)
        mock_runs_service.list_runs.return_value = Page[SerializableTaskRun](
            items=[],
            count=0,
        )

        response = await test_api_client.get("/_/agents/task_id/schemas/1/runs")
        assert response.status_code == 200
        assert response.json() == {"items": [], "count": 0}

        mock_runs_service.list_runs.assert_called_once_with(
            1,
            SerializableTaskRunQuery(
                task_id="task_id",
                task_schema_id=1,
                exclude_fields={"llm_completions"},
                limit=20,
                status={"success"},
            ),
        )


class TestPatchTaskSchema:
    async def test_patch_task_schema_hide(
        self,
        test_api_client: AsyncClient,
        mock_storage: Mock,
    ):
        # Mock the necessary storage calls
        mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()
        mock_storage.tasks.update_task.return_value = TaskUpdate(hide_schema=1)

        # Make the patch request to hide the schema
        response = await test_api_client.patch(
            "/test/agents/task_id/schemas/1",
            json={
                "is_hidden": True,
            },
        )

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["is_hidden"] is True
        assert json_response["name"] == "task_name"
        assert json_response["task_id"] == "task_id"
        assert json_response["schema_id"] == 1

        # Verify storage was called correctly
        mock_storage.tasks.update_task.assert_called_once_with(
            "task_id",
            TaskUpdate(hide_schema=1),
        )

    async def test_patch_task_schema_unhide(
        self,
        test_api_client: AsyncClient,
        mock_storage: Mock,
    ):
        # Mock the necessary storage calls
        mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()
        mock_storage.tasks.update_task.return_value = TaskUpdate(unhide_schema=1)

        # Make the patch request to unhide the schema
        response = await test_api_client.patch(
            "/test/agents/task_id/schemas/1",
            json={
                "is_hidden": False,
            },
        )

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["is_hidden"] is False

        # Verify storage was called correctly
        mock_storage.tasks.update_task.assert_called_once_with(
            "task_id",
            TaskUpdate(unhide_schema=1),
        )

    async def test_patch_task_schema_no_hidden_status(
        self,
        test_api_client: AsyncClient,
        mock_storage: Mock,
    ):
        # Mock the necessary storage calls
        mock_storage.task_variant_latest_by_schema_id.return_value = task_variant()

        # Make the patch request without is_hidden field
        response = await test_api_client.patch(
            "/test/agents/task_id/schemas/1",
            json={},
        )

        assert response.status_code != 200

        # Verify storage was not called
        mock_storage.tasks.get_task_info.assert_not_called()
        mock_storage.tasks.update_task.assert_not_called()


class TestGenerateTaskPreview:
    async def test_generate_task_preview_success(
        self,
        test_api_client: AsyncClient,
        mock_internal_tasks_service: Mock,
    ):
        # Mock the streaming response
        mock_internal_tasks_service.stream_generate_task_preview.return_value = mock_aiter(
            TaskPreview(
                input={"test_input": "value"},
                output={"test_output": "result"},
            ),
        )

        async with test_api_client.stream(
            "POST",
            "/test/agents/schemas/preview",
            json={
                "chat_messages": [
                    {"role": "USER", "content": "Create a task that does X"},
                ],
                "task_input_schema": {
                    "type": "object",
                    "properties": {"test_input": {"type": "string"}},
                },
                "task_output_schema": {
                    "type": "object",
                    "properties": {"test_output": {"type": "string"}},
                },
            },
        ) as response:
            assert response.status_code == 200
            chunks = [json.loads(chunk.replace(b"data: ", b"").decode()) async for chunk in response.aiter_raw()]

        assert chunks == [
            {
                "input": {"test_input": "value"},
                "output": {"test_output": "result"},
            },
        ]

        # Verify the service was called with correct parameters
        mock_internal_tasks_service.stream_generate_task_preview.assert_called_once()
        call_args = mock_internal_tasks_service.stream_generate_task_preview.call_args[1]["task_input"]
        assert call_args.chat_messages[0].content == "Create a task that does X"
        assert call_args.task_input_schema == {
            "type": "object",
            "properties": {"test_input": {"type": "string"}},
        }
        assert call_args.task_output_schema == {
            "type": "object",
            "properties": {"test_output": {"type": "string"}},
        }
        assert call_args.current_preview is None

    async def test_generate_task_preview_with_current_preview(
        self,
        test_api_client: AsyncClient,
        mock_internal_tasks_service: Mock,
    ):
        # Mock the streaming response
        mock_internal_tasks_service.stream_generate_task_preview.return_value = mock_aiter(
            TaskPreview(
                input={"test_input": "updated_value"},
                output={"test_output": "updated_result"},
            ),
        )

        async with test_api_client.stream(
            "POST",
            "/test/agents/schemas/preview",
            json={
                "chat_messages": [
                    {"role": "USER", "content": "Update the task"},
                ],
                "task_input_schema": {
                    "type": "object",
                    "properties": {"test_input": {"type": "string"}},
                },
                "task_output_schema": {
                    "type": "object",
                    "properties": {"test_output": {"type": "string"}},
                },
                "current_preview": {
                    "input": {"test_input": "old_value"},
                    "output": {"test_output": "old_result"},
                },
            },
        ) as response:
            assert response.status_code == 200
            chunks = [json.loads(chunk.replace(b"data: ", b"").decode()) async for chunk in response.aiter_raw()]

        assert chunks == [
            {
                "input": {"test_input": "updated_value"},
                "output": {"test_output": "updated_result"},
            },
        ]

        # Verify the service was called with correct parameters including current_preview
        mock_internal_tasks_service.stream_generate_task_preview.assert_called_once()
        call_args = mock_internal_tasks_service.stream_generate_task_preview.call_args[1]["task_input"]
        assert call_args.current_preview == TaskPreview(
            input={"test_input": "old_value"},
            output={"test_output": "old_result"},
        )

    async def test_generate_task_preview_validation_error(
        self,
        test_api_client: AsyncClient,
        mock_internal_tasks_service: Mock,
    ):
        response = await test_api_client.post(
            "/test/agents/schemas/preview",
            json={
                # Missing required fields
                "chat_messages": [],
            },
        )

        assert response.status_code == 422
        assert "task_input_schema" in response.json()["detail"][0]["loc"]
        assert "task_output_schema" in response.json()["detail"][1]["loc"]
        mock_internal_tasks_service.stream_generate_task_preview.assert_not_called()


class TestUpdateTaskInstructionsRequest:
    def test_is_no_op_with_no_selected_tools(self):
        request = UpdateTaskInstructionsRequest(
            instructions="Test instructions",
            selected_tools=None,
        )
        assert request.is_no_op() is True

    def test_is_no_op_with_selected_tools(self):
        request = UpdateTaskInstructionsRequest(
            instructions="Test instructions",
            selected_tools=["@browser-text", "@search-google"],  # type: ignore[list-item]
        )
        assert request.is_no_op() is False

    def test_valid_request_with_empty_selected_tools(self):
        request = UpdateTaskInstructionsRequest(
            instructions="Test instructions",
            selected_tools=[],
        )
        assert request.instructions == "Test instructions"
        assert request.selected_tools == []
        assert request.is_no_op() is False

    def test_valid_request_with_selected_tools(self):
        request = UpdateTaskInstructionsRequest(
            instructions="Test instructions",
            selected_tools=["@browser-text", "@search-google"],  # type: ignore[list-item]
        )
        assert request.instructions == "Test instructions"
        assert request.selected_tools == ["@browser-text", "@search-google"]
        assert request.is_no_op() is False

    def test_valid_request_with_no_selected_tools(self):
        request = UpdateTaskInstructionsRequest(
            instructions="Test instructions",
        )
        assert request.instructions == "Test instructions"
        assert request.selected_tools is None
        assert request.is_no_op() is True

    def test_cleaned_selected_tools_with_valid_tools(self):
        request = UpdateTaskInstructionsRequest(
            instructions="Test instructions",
            selected_tools=["@browser-text", "@search-google"],  # type: ignore[list-item]
        )
        cleaned_tools = request.selected_tools
        assert cleaned_tools is not None

        assert len(cleaned_tools) == 2

        assert all(isinstance(tool, ToolKind) for tool in cleaned_tools)
        assert ToolKind.WEB_BROWSER_TEXT in cleaned_tools
        assert ToolKind.WEB_SEARCH_GOOGLE in cleaned_tools

    def test_cleaned_selected_tools_with_aliases(self):
        request = UpdateTaskInstructionsRequest(
            instructions="Test instructions",
            selected_tools=["@search"],  # type: ignore[list-item]
        )
        cleaned_tools = request.selected_tools
        assert cleaned_tools is not None
        assert len(cleaned_tools) == 1
        assert ToolKind.WEB_SEARCH_GOOGLE in cleaned_tools

    def test_cleaned_selected_tools_with_none(self):
        request = UpdateTaskInstructionsRequest(
            instructions="Test instructions",
            selected_tools=None,
        )
        assert request.selected_tools is None

    def test_cleaned_selected_tools_with_empty_list(self):
        request = UpdateTaskInstructionsRequest(
            instructions="Test instructions",
            selected_tools=[],
        )
        assert request.selected_tools == []
