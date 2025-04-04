import datetime
import logging
from unittest.mock import AsyncMock, Mock

import pytest

from core.agents.detect_chain_of_thought_task import (
    DetectChainOfThoughtUsageTaskOutput,
)
from core.domain.errors import InvalidRunOptionsError
from core.domain.models import Provider
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tenant_data import ProviderSettings
from core.domain.tool import Tool
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment
from core.domain.version_reference import VersionReference
from core.runners.workflowai.workflowai_runner import WorkflowAIRunner
from core.storage import ObjectNotFoundException
from core.storage.mongo.models.organization_document import DecryptableProviderSettings
from core.tools import ToolKind
from tests.models import task_deployment, task_variant

from .groups import GroupService  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def mock_logger():
    return Mock(spec=logging.Logger)


@pytest.fixture(scope="function")
async def mock_detect_chain_of_thought(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    from api.services import groups

    mock_func: AsyncMock = AsyncMock(
        return_value=DetectChainOfThoughtUsageTaskOutput(should_use_chain_of_thought=True),
    )
    monkeypatch.setattr(groups, groups.run_detect_chain_of_thought_task.__name__, mock_func)
    return mock_func


@pytest.fixture(scope="function")
def group_service(
    mock_storage: Mock,
    mock_event_router: Mock,
    mock_analytics_service: Mock,
    mock_logger: Mock,
) -> GroupService:
    grp = GroupService(
        storage=mock_storage,
        event_router=mock_event_router,
        analytics_service=mock_analytics_service,
        user=UserIdentifier(user_id="test_user_id", user_email="test_user_email@example.com"),
    )
    grp._logger = mock_logger  # pyright: ignore [reportPrivateUsage]
    return grp


class TestSanitizeGroupsForInternalRunner:
    async def test_with_variant(
        self,
        group_service: GroupService,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
    ) -> None:
        mock_storage.task_version_resource_by_id.return_value = task_version_resource

        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference.with_properties(model="gpt-4o-2024-08-06", task_variant_id="t1"),
        )

        assert isinstance(runner, WorkflowAIRunner)
        assert runner.task == task_version_resource
        assert runner.properties.model_dump(mode="json", exclude_none=True) == {
            "model": "gpt-4o-2024-08-06",
            "temperature": 0.0,
            "runner_name": "WorkflowAI",
            "runner_version": "v0.1.0",
            "task_variant_id": "task_version_id",
            # template name, provider and is_structured_generation_enabled are not
            # set at the group property level but will be set in metadatas during the run
        }

    async def test_with_environment(
        self,
        group_service: GroupService,
        task_version_resource: SerializableTaskVariant,
        mock_storage: Mock,
    ) -> None:
        mock_storage.task_version_resource_by_id.return_value = task_version_resource
        mock_storage.task_deployments.get_task_deployment.return_value = task_deployment(
            environment=VersionEnvironment.PRODUCTION,
            properties=TaskGroupProperties.model_validate(
                {"model": "gpt-4o-2024-08-06", "task_variant_id": "task_version_id"},
            ),
        )
        await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference(version=VersionEnvironment.PRODUCTION),
        )

        mock_storage.task_deployments.get_task_deployment.assert_called_once()
        mock_storage.task_version_resource_by_id.assert_called_once()

    async def test_without_variant(
        self,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
        group_service: GroupService,
    ) -> None:
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource
        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference.with_properties(model="gpt-4o-2024-08-06"),
        )

        assert isinstance(runner, WorkflowAIRunner)
        assert runner.task == task_version_resource
        assert runner.properties.model_dump(exclude_none=True, mode="json") == {
            "model": "gpt-4o-2024-08-06",
            "temperature": 0.0,
            "runner_name": "WorkflowAI",
            "runner_version": "v0.1.0",
            "task_variant_id": "task_version_id",
        }

    async def test_detect_tool_use_enabled(
        self,
        group_service: GroupService,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
    ) -> None:
        """Test that tool use detection works when enabled"""
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource

        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference.with_properties(
                model="gpt-4o-2024-08-06",
                instructions="Test instructions @browser-text",
            ),
        )

        assert isinstance(runner, WorkflowAIRunner)
        assert runner.task == task_version_resource
        assert runner.properties.enabled_tools == [ToolKind.WEB_BROWSER_TEXT]

    async def test_detect_tool_use_disabled(
        self,
        group_service: GroupService,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
    ) -> None:
        """Test that tool use detection works when disabled"""
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource

        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference.with_properties(
                model="gpt-4o-2024-08-06",
                instructions="Test instructions",
            ),
        )

        assert isinstance(runner, WorkflowAIRunner)
        assert runner.task == task_version_resource
        assert runner.properties.enabled_tools is None

    async def test_detect_chain_of_thought_enabled(
        self,
        mock_detect_chain_of_thought: Mock,
        group_service: GroupService,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
    ) -> None:
        """Test that chain of thought detection works when enabled"""
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource
        mock_detect_chain_of_thought.return_value = DetectChainOfThoughtUsageTaskOutput(
            should_use_chain_of_thought=True,
        )

        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference.with_properties(
                model="gpt-4o-2024-08-06",
                instructions="Test instructions",
            ),
            detect_chain_of_thought=True,
        )

        assert isinstance(runner, WorkflowAIRunner)
        assert runner.properties.is_chain_of_thought_enabled is True
        mock_detect_chain_of_thought.assert_called_once()

    async def test_detect_chain_of_thought_disabled(
        self,
        mock_detect_chain_of_thought: Mock,
        group_service: GroupService,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
    ) -> None:
        """Test that chain of thought detection works when disabled"""
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource

        mock_detect_chain_of_thought.return_value = DetectChainOfThoughtUsageTaskOutput(
            should_use_chain_of_thought=False,
        )

        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference.with_properties(
                model="gpt-4o-2024-08-06",
                instructions="Test instructions",
            ),
            detect_chain_of_thought=True,
        )

        assert isinstance(runner, WorkflowAIRunner)
        assert runner.properties.is_chain_of_thought_enabled is False
        mock_detect_chain_of_thought.assert_called_once()

    async def test_detect_chain_of_thought_no_instructions(
        self,
        group_service: GroupService,
        mock_detect_chain_of_thought: Mock,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
    ) -> None:
        """Test that chain of thought detection is skipped when no instructions"""
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource

        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference.with_properties(
                model="gpt-4o-2024-08-06",
                instructions="",
            ),
            detect_chain_of_thought=True,
        )

        assert isinstance(runner, WorkflowAIRunner)
        assert (
            runner.properties.is_chain_of_thought_enabled is False
        )  # is_chain_of_thought_enabled is False when instructions are empty
        mock_detect_chain_of_thought.assert_not_called()

    async def test_detect_chain_of_thought_error_handling(
        self,
        group_service: GroupService,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
        mock_detect_chain_of_thought: Mock,
    ) -> None:
        """Test that chain of thought detection errors are handled gracefully"""
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource

        mock_detect_chain_of_thought.side_effect = Exception("Test error")

        # Should not raise exception
        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference.with_properties(
                model="gpt-4o-2024-08-06",
                instructions="Test instructions",
            ),
            detect_chain_of_thought=True,
        )

        assert isinstance(runner, WorkflowAIRunner)
        # Chain of thought should not be set when there's an error
        assert runner.properties.is_chain_of_thought_enabled is None
        mock_detect_chain_of_thought.assert_called_once()

    async def test_detect_chain_of_thought_existing_group(
        self,
        group_service: GroupService,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
        mock_detect_chain_of_thought: Mock,
    ) -> None:
        """Test that chain of thought detection is skipped for existing groups"""
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource
        mock_storage.task_deployments.get_task_deployment.return_value = task_deployment(
            properties=TaskGroupProperties(
                model="gpt-4o-2024-08-06",
                instructions="some_other_value",
            ),
        )

        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference(version=VersionEnvironment.PRODUCTION),
            detect_chain_of_thought=True,
        )

        assert isinstance(runner, WorkflowAIRunner)
        assert runner.properties.model == "gpt-4o-2024-08-06"
        assert runner.properties.instructions == "some_other_value"
        # Should not call detect chain of thought for existing groups
        mock_detect_chain_of_thought.assert_not_called()

    async def test_detect_chain_of_thought_flag_disabled(
        self,
        group_service: GroupService,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
        mock_detect_chain_of_thought: Mock,
    ) -> None:
        """Test that chain of thought detection is skipped when flag is disabled"""
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource

        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id=task_version_resource.task_id,
            task_schema_id=task_version_resource.task_schema_id,
            reference=VersionReference.with_properties(
                model="gpt-4o-2024-08-06",
                instructions="Test instructions",
            ),
            detect_chain_of_thought=False,  # Explicitly disabled
        )

        assert isinstance(runner, WorkflowAIRunner)
        assert runner.properties.is_chain_of_thought_enabled is None
        mock_detect_chain_of_thought.assert_not_called()

    async def test_provider_configs_passed_to_runner(
        self,
        group_service: GroupService,
        mock_storage: Mock,
    ) -> None:
        provider_settings: list[ProviderSettings] = [
            DecryptableProviderSettings(
                id="google_provider_settings",
                created_at=datetime.datetime(2022, 1, 1, 0, 0, 0),
                provider=Provider.GOOGLE,
                secrets='{"api_key": "some_key"}_encrypted',
            ),
            DecryptableProviderSettings(
                id="openai_provider_settings",
                created_at=datetime.datetime(2022, 1, 1, 0, 0, 0),
                provider=Provider.OPEN_AI,
                secrets='{"api_key": "user_api_key"}_encrypted',
            ),
        ]
        mock_storage.task_deployments.get_task_deployment.return_value = task_deployment(
            properties=TaskGroupProperties.model_validate(
                {
                    "model": "gpt-4o-2024-05-13",
                    "task_variant_id": "task_variant_id",
                },
            ),
        )
        mock_storage.task_version_resource_by_id.return_value = task_variant(
            task_id="task_id",
            task_schema_id=1,
        )

        runner, _ = await group_service.sanitize_groups_for_internal_runner(
            task_id="task_id",
            task_schema_id=1,
            reference=VersionReference(version=VersionEnvironment.PRODUCTION),
            provider_settings=provider_settings,
        )
        assert isinstance(runner, WorkflowAIRunner)

        assert runner._custom_configs == provider_settings  # pyright: ignore [reportPrivateUsage]

    async def test_template_is_validated(
        self,
        group_service: GroupService,
        mock_storage: Mock,
        task_version_resource: SerializableTaskVariant,
    ):
        mock_storage.task_variant_latest_by_schema_id.return_value = task_version_resource

        with pytest.raises(InvalidRunOptionsError) as e:
            await group_service.sanitize_groups_for_internal_runner(
                task_id=task_version_resource.task_id,
                task_schema_id=task_version_resource.task_schema_id,
                reference=VersionReference.with_properties(
                    model="gpt-4o-2024-08-06",
                    # Invalid template
                    instructions="Hello {{name}",
                ),
            )

        assert "Instruction template is invalid" in str(e.value)


class TestSanitizeGroupProperties:
    async def test_amazon_bedrock_redirects_to_amazon_bedrock(self, group_service: GroupService) -> None:
        properties = TaskGroupProperties(
            provider="amazon_bedrock",
        )
        task = task_variant()

        properties = await group_service._sanitize_group_properties(task, properties)  # pyright: ignore [reportPrivateUsage]
        assert properties.provider == "amazon_bedrock"

    async def test_openai_redirects_to_openai(self, group_service: GroupService) -> None:
        properties = TaskGroupProperties(
            provider="openai",
        )
        task = task_variant()

        properties = await group_service._sanitize_group_properties(task, properties)  # pyright: ignore [reportPrivateUsage]
        assert properties.provider == "openai"


class TestSetEnabledTools:
    @pytest.mark.parametrize(
        "properties, expected_enabled_tools",
        [
            (TaskGroupProperties(instructions="Use @browser-text to search"), [ToolKind.WEB_BROWSER_TEXT]),
            (TaskGroupProperties(instructions="Use @search to search"), [ToolKind.WEB_SEARCH_GOOGLE]),
            (
                TaskGroupProperties(instructions="Use @browser-text to search and @search"),
                [ToolKind.WEB_BROWSER_TEXT, ToolKind.WEB_SEARCH_GOOGLE],
            ),
            (TaskGroupProperties(instructions="Use @web"), None),  # The @web handle is not a valid tool kind anymore
            (TaskGroupProperties(instructions=""), None),
            (TaskGroupProperties(), None),
            (TaskGroupProperties(instructions="Regular instructions without any tool handles"), None),
            (
                TaskGroupProperties(instructions="@browser-text", enabled_tools=[ToolKind.WEB_BROWSER_TEXT]),
                [ToolKind.WEB_BROWSER_TEXT],
            ),
            (
                TaskGroupProperties.model_validate(
                    {"instructions": "@browser-text", "enabled_tools": ["@browser-text"]},
                ),
                [ToolKind.WEB_BROWSER_TEXT],
            ),
            (
                TaskGroupProperties(
                    instructions="@search-google",
                    enabled_tools=[Tool(name="browser-text", description="", input_schema={}, output_schema={})],
                ),
                [
                    Tool(name="browser-text", description="", input_schema={}, output_schema={}),
                    ToolKind.WEB_SEARCH_GOOGLE,
                ],
            ),
            # Test ordering of enabled tools
            (
                TaskGroupProperties(
                    instructions="@search @browser-text",
                    enabled_tools=None,
                ),
                [ToolKind.WEB_BROWSER_TEXT, ToolKind.WEB_SEARCH_GOOGLE],
            ),
            # Test ordering of enabled tools and external tools
            (
                TaskGroupProperties(
                    instructions="@search @browser-text",
                    enabled_tools=[
                        Tool(name="A", description="", input_schema={}, output_schema={}),
                        Tool(name="Z", description="", input_schema={}, output_schema={}),
                        ToolKind.WEB_SEARCH_GOOGLE,
                        ToolKind.WEB_BROWSER_TEXT,
                    ],
                ),
                [
                    Tool(name="A", description="", input_schema={}, output_schema={}),
                    ToolKind.WEB_BROWSER_TEXT,
                    ToolKind.WEB_SEARCH_GOOGLE,
                    Tool(name="Z", description="", input_schema={}, output_schema={}),
                ],
            ),
        ],
    )
    def test_set_enabled_tools_with_tool_handles(
        self,
        group_service: GroupService,
        properties: TaskGroupProperties,
        expected_enabled_tools: list[ToolKind] | None,
    ) -> None:
        """Test that tools are correctly detected from instructions containing tool handles"""

        group_service._set_enabled_tools(properties)  # pyright: ignore[reportPrivateUsage]

        if expected_enabled_tools is None:
            assert properties.enabled_tools is None
        else:
            assert properties.enabled_tools == expected_enabled_tools, "The order of enabled tools is incorrect"


class TestObjectNotFoundException:
    async def test_object_not_found_error(self, group_service: GroupService, mock_storage: Mock) -> None:
        """Test that object not found error is raised when the object is not found"""
        mock_storage.task_deployments.get_task_deployment.side_effect = ObjectNotFoundException(
            "Version not found",
            code="version_not_found",
        )
        with pytest.raises(ObjectNotFoundException) as e:
            await group_service.sanitize_version_reference(
                "task_id",
                1,
                VersionReference(version=VersionEnvironment.PRODUCTION),
            )

        assert e.value.code == "version_not_found"


# class TestEnableStructuredGenerationIfSupported:
#     async def test_structured_generation_not_supported(
#         self,
#         group_service: GroupService,
#         mock_storage: Mock,
#     ) -> None:
#         """Test that structured generation is not enabled when provider doesn't support it"""
#         provider = Mock()
#         provider.is_structured_generation_supported = False

#         properties = TaskGroupProperties()
#         output_schema = {"type": "object"}

#         await GroupService._enable_structured_generation_if_supported(  # pyright: ignore [reportPrivateUsage]
#             provider=provider,
#             model=Model.GPT_4O_2024_08_06,
#             task_name="test",
#             properties=properties,
#             output_schema=output_schema,
#         )

#         assert properties.is_structured_generation_enabled is False
#         provider.is_schema_supported_for_structured_generation.assert_not_called()

#     async def test_structured_generation_supported_basic_schema(
#         self,
#         group_service: GroupService,
#         mock_storage: Mock,
#     ) -> None:
#         """Test that structured generation is enabled when provider supports it with basic schema"""
#         provider = Mock()
#         provider.is_structured_generation_supported = True
#         provider.is_schema_supported_for_structured_generation = AsyncMock(return_value=True)

#         properties = TaskGroupProperties()
#         output_schema = {"type": "object"}

#         await GroupService._enable_structured_generation_if_supported(  # pyright: ignore [reportPrivateUsage]
#             provider=provider,
#             model=Model.GPT_4O_2024_08_06,
#             task_name="test",
#             properties=properties,
#             output_schema=output_schema,
#         )

#         assert properties.is_structured_generation_enabled is True
#         provider.is_schema_supported_for_structured_generation.assert_called_once_with(
#             task_name="test",
#             model=Model.GPT_4O_2024_08_06,
#             schema=output_schema,
#         )

#     async def test_structured_generation_with_chain_of_thought(
#         self,
#         group_service: GroupService,
#         mock_storage: Mock,
#     ) -> None:
#         """Test that structured generation handles chain of thought schema modifications"""
#         provider = Mock()
#         provider.is_structured_generation_supported = True
#         provider.is_schema_supported_for_structured_generation = AsyncMock(return_value=True)

#         properties = TaskGroupProperties(is_chain_of_thought_enabled=True)
#         output_schema: dict[str, Any] = {"type": "object", "properties": {"some_property": {"type": "string"}}}

#         await GroupService._enable_structured_generation_if_supported(  # pyright: ignore [reportPrivateUsage]
#             provider=provider,
#             model=Model.GPT_4O_2024_08_06,
#             task_name="test",
#             properties=properties,
#             output_schema=output_schema,
#         )

#         assert properties.is_structured_generation_enabled is True
#         # Verify the schema was modified with reasoning steps
#         provider.is_schema_supported_for_structured_generation.assert_called_once()
#         modified_schema = provider.is_schema_supported_for_structured_generation.call_args[1]["schema"]
#         assert "internal_reasoning_steps" in modified_schema["properties"]

#     async def test_structured_generation_with_tools(
#         self,
#         group_service: GroupService,
#         mock_storage: Mock,
#     ) -> None:
#         """Test that structured generation handles tool calls schema modifications"""
#         provider = Mock()
#         provider.is_structured_generation_supported = True
#         provider.is_schema_supported_for_structured_generation = AsyncMock(return_value=True)

#         properties = TaskGroupProperties(enabled_tools=[ToolKind.WEB_BROWSER_TEXT])
#         output_schema: dict[str, Any] = {"type": "object", "properties": {}}

#         await GroupService._enable_structured_generation_if_supported(  # pyright: ignore [reportPrivateUsage]
#             provider=provider,
#             model=Model.GPT_4O_2024_08_06,
#             task_name="test",
#             properties=properties,
#             output_schema=output_schema,
#         )

#         assert properties.is_structured_generation_enabled is True
#         # Verify the schema was modified with tool calls
#         provider.is_schema_supported_for_structured_generation.assert_called_once()
#         modified_schema = provider.is_schema_supported_for_structured_generation.call_args[1]["schema"]
#         assert "internal_tool_calls" in modified_schema["properties"]

#     async def test_structured_generation_schema_not_supported(
#         self,
#         group_service: GroupService,
#         mock_storage: Mock,
#     ) -> None:
#         """Test that structured generation is not enabled when schema is not supported"""
#         provider = Mock()
#         provider.is_structured_generation_supported = True
#         provider.is_schema_supported_for_structured_generation = AsyncMock(return_value=False)

#         properties = TaskGroupProperties()
#         output_schema = {"type": "object"}

#         await group_service._enable_structured_generation_if_supported(  # pyright: ignore [reportPrivateUsage]
#             provider=provider,
#             model=Model.GPT_4O_2024_08_06,
#             task_name="test",
#             properties=properties,
#             output_schema=output_schema,
#         )

#         assert properties.is_structured_generation_enabled is False
#         provider.is_schema_supported_for_structured_generation.assert_called_once_with(
#             task_name="test",
#             model=Model.GPT_4O_2024_08_06,
#             schema=output_schema,
#         )
