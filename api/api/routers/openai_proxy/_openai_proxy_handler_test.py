# pyright: reportPrivateUsage=false

from typing import Any
from unittest.mock import Mock

import pytest

from api.routers.openai_proxy._openai_proxy_handler import OpenAIProxyHandler
from api.routers.openai_proxy._openai_proxy_models import (
    EnvironmentRef,
    ModelRef,
    OpenAIProxyChatCompletionRequest,
    OpenAIProxyMessage,
    OpenAIProxyTool,
    OpenAIProxyToolDefinition,
)
from api.services.feedback_svc import FeedbackTokenGenerator
from core.domain.consts import INPUT_KEY_MESSAGES
from core.domain.errors import BadRequestError
from core.domain.message import Message, MessageRole, Messages
from core.domain.models.models import Model
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import RawMessagesSchema, RawStringMessageSchema
from core.domain.tenant_data import PublicOrganizationData
from core.domain.tool import Tool
from core.domain.version_environment import VersionEnvironment
from tests import models as test_models


@pytest.fixture
def proxy_handler(
    mock_group_service: Mock,
    mock_storage: Mock,
    mock_run_service: Mock,
    mock_event_router: Mock,
):
    return OpenAIProxyHandler(
        group_service=mock_group_service,
        storage=mock_storage,
        run_service=mock_run_service,
        event_router=mock_event_router,
        feedback_generator=Mock(spec=FeedbackTokenGenerator),
    )


class TestPrepareRun:
    @pytest.fixture
    def completion_request(self):
        return OpenAIProxyChatCompletionRequest(
            model="gpt-4o",
            messages=[
                OpenAIProxyMessage(role="user", content="Hello, world!"),
            ],
        )

    async def test_deployment_tools_overriden(
        self,
        proxy_handler: OpenAIProxyHandler,
        completion_request: OpenAIProxyChatCompletionRequest,
        mock_storage: Mock,
    ):
        """Check that the tools are overriden when provided in the completion request"""

        completion_request.input = None
        completion_request.model = "my-agent/#1/production"
        completion_request.tools = [
            OpenAIProxyTool(
                type="function",
                function=OpenAIProxyToolDefinition(
                    name="my_function",
                    parameters={},
                    strict=True,
                ),
            ),
        ]
        mock_storage.task_deployments.get_task_deployment.return_value = test_models.task_deployment(
            properties=TaskGroupProperties(
                model="gpt-4o",
                task_variant_id="my-variant",  # type: ignore
                enabled_tools=["hello"],
            ),
        )
        mock_storage.task_version_resource_by_id.return_value = test_models.task_variant(
            input_io=RawMessagesSchema,
        )
        result = await proxy_handler.prepare_run(completion_request, PublicOrganizationData())
        assert result.properties.enabled_tools == [
            Tool(name="my_function", input_schema={}, output_schema={}, strict=True),
        ]

    async def test_deployment_with_extra_input(
        self,
        proxy_handler: OpenAIProxyHandler,
        mock_storage: Mock,
        completion_request: OpenAIProxyChatCompletionRequest,
    ):
        """Check the error message when an input is sent to a deployment that does not expect an input"""
        completion_request.model = "my agent/#1/production"
        completion_request.messages = [
            OpenAIProxyMessage(role="user", content="Hello, world!"),
        ]
        completion_request.input = {"name": "John"}

        mock_storage.task_deployments.get_task_deployment.return_value = test_models.task_deployment(
            properties=TaskGroupProperties(
                model="gpt-4o",
                task_variant_id="my-variant",  # type: ignore
                enabled_tools=["hello"],
            ),
        )
        mock_storage.task_version_resource_by_id.return_value = test_models.task_variant(
            input_io=RawMessagesSchema,
        )
        with pytest.raises(BadRequestError) as e:
            await proxy_handler.prepare_run(completion_request, PublicOrganizationData())
        assert "You send input variables but the deployment you are trying to use does not expect any" in str(e.value)

    @pytest.mark.skip(reason="Fix the error message")
    async def test_deployment_with_missing_input(
        self,
        proxy_handler: OpenAIProxyHandler,
        mock_storage: Mock,
        completion_request: OpenAIProxyChatCompletionRequest,
    ):
        completion_request.model = "my agent/#1/production"
        completion_request.messages = []
        completion_request.input = None

        mock_storage.task_deployments.get_task_deployment.return_value = test_models.task_deployment(
            properties=TaskGroupProperties(
                model="gpt-4o",
                task_variant_id="my-variant",  # type: ignore
                enabled_tools=["hello"],
                messages=[Message.with_text("Hello {{name}}!", role="user")],
            ),
        )
        mock_storage.task_version_resource_by_id.return_value = test_models.task_variant(
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        )

        with pytest.raises(BadRequestError) as e:
            await proxy_handler.prepare_run(completion_request, PublicOrganizationData())
        assert "Your deployment on schema #1 expects input variables" in str(e.value)

    async def test_with_deployment_and_non_slug_agent_id(
        self,
        proxy_handler: OpenAIProxyHandler,
        mock_storage: Mock,
        completion_request: OpenAIProxyChatCompletionRequest,
    ):
        """Check that we slugify the agent id if it's not a slug"""
        completion_request.model = "my agent/#1/production"
        completion_request.messages = [
            OpenAIProxyMessage(role="user", content="Hello, world!"),
        ]
        completion_request.input = None
        mock_storage.task_deployments.get_task_deployment.return_value = test_models.task_deployment(
            properties=TaskGroupProperties(
                model="gpt-4o",
                task_variant_id="my-variant",  # type: ignore
                enabled_tools=["hello"],
            ),
        )
        mock_storage.task_version_resource_by_id.return_value = test_models.task_variant(input_io=RawMessagesSchema)
        await proxy_handler.prepare_run(completion_request, PublicOrganizationData())

        mock_storage.task_deployments.get_task_deployment.assert_called_once_with(
            "my-agent",
            1,
            "production",
        )
        mock_storage.task_version_resource_by_id.assert_called_once_with(
            "my-agent",
            "my-variant",
        )

    async def test_with_model_and_non_slug_agent_id(
        self,
        proxy_handler: OpenAIProxyHandler,
        mock_storage: Mock,
        completion_request: OpenAIProxyChatCompletionRequest,
    ):
        """Check that we slugify the agent id if it's not a slug"""
        completion_request.model = "my agent/gpt-4"
        completion_request.messages = [
            OpenAIProxyMessage(role="user", content="Hello, world!"),
        ]
        completion_request.input = None
        mock_storage.store_task_resource.side_effect = lambda x: (x, True)  # type: ignore

        prepared = await proxy_handler.prepare_run(completion_request, PublicOrganizationData())
        assert prepared.variant.task_id == "my-agent"
        assert prepared.variant.name == "my agent"

    async def test_workflowai_internal(
        self,
        proxy_handler: OpenAIProxyHandler,
        mock_storage: Mock,
    ):
        """Check that the workflowai_internal path works correctly"""

        completion_request = OpenAIProxyChatCompletionRequest(
            model="gpt-4o",
            messages=[],  # Empty messages as required for workflowai_internal
            agent_id="my-test-agent",
            input={"name": "John", "age": 30},
            workflowai_internal=OpenAIProxyChatCompletionRequest.WorkflowAIInternal(
                variant_id="my-variant-id",
                version_messages=[
                    Message.with_text("You are a helpful assistant", role="system"),
                    Message.with_text("Hello {{name}}, you are {{age}} years old!", role="user"),
                ],
            ),
        )

        mock_variant = test_models.task_variant(
            id="my-variant-id",
            task_id="my-test-agent",
            input_io=RawMessagesSchema,
            output_io=RawStringMessageSchema,
        )
        mock_storage.task_version_resource_by_id.return_value = mock_variant

        result = await proxy_handler.prepare_run(completion_request, PublicOrganizationData())

        # Verify that it called _prepare_for_variant_id correctly
        mock_storage.task_version_resource_by_id.assert_called_once_with(
            "my-test-agent",
            "my-variant-id",
        )

        # Verify the result structure
        assert result.variant == mock_variant
        assert result.properties.model == "gpt-4o"
        assert result.properties.messages == [
            Message.with_text("You are a helpful assistant", role="system"),
            Message.with_text("Hello {{name}}, you are {{age}} years old!", role="user"),
        ]
        assert result.properties.task_variant_id == "my-variant-id"
        assert result.final_input == {"name": "John", "age": 30}


class TestCheckForDuplicateMessages:
    def test_no_messages(self, proxy_handler: OpenAIProxyHandler):
        """Check that we just don't raise if we have no messages in the deployment"""
        messages = Messages.with_messages(Message.with_text("Hello, world!"))
        proxy_handler._check_for_duplicate_messages(None, messages)

    def test_duplicate_messages(self, proxy_handler: OpenAIProxyHandler):
        """Check that we raise if we have duplicate messages"""
        messages = Messages.with_messages(Message.with_text("Hello, world!"))
        with pytest.raises(BadRequestError):
            proxy_handler._check_for_duplicate_messages([Message.with_text("Hello, world!")], messages)


class TestPrepareRunForDeployment:
    async def test_no_messages(self, proxy_handler: OpenAIProxyHandler, mock_storage: Mock):
        """Check that we just don't raise if we have no messages in the deployment"""

        mock_storage.task_deployments.get_task_deployment.return_value = test_models.task_deployment(
            properties=TaskGroupProperties(
                model="gpt-4o",
                task_variant_id="my-variant",  # type: ignore
                # No messages
            ),
        )
        mock_storage.task_version_resource_by_id.return_value = test_models.task_variant()

        result = await proxy_handler._prepare_for_deployment(
            agent_ref=EnvironmentRef(agent_id="", schema_id=1, environment=VersionEnvironment.PRODUCTION),
            tenant_data=PublicOrganizationData(),
            messages=Messages.with_messages(Message.with_text("Hello, world!")),
            input=None,
            response_format=None,
        )
        assert result.final_input == Messages.with_messages(Message.with_text("Hello, world!"))

    async def test_with_agent_id_with_underscores(self, proxy_handler: OpenAIProxyHandler, mock_storage: Mock):
        """Check that we slugify the agent id if it's not a slug"""
        mock_storage.task_deployments.get_task_deployment.return_value = test_models.task_deployment(
            properties=TaskGroupProperties(
                model="gpt-4o",
                task_variant_id="my-variant",  # type: ignore
                # No messages
            ),
        )
        mock_storage.task_version_resource_by_id.return_value = test_models.task_variant(task_id="my_agent")
        result = await proxy_handler._prepare_for_deployment(
            agent_ref=EnvironmentRef(agent_id="my_agent", schema_id=1, environment=VersionEnvironment.PRODUCTION),
            tenant_data=PublicOrganizationData(),
            messages=Messages.with_messages(Message.with_text("Hello, world!")),
            input=None,
            response_format=None,
        )
        assert result.final_input == Messages.with_messages(Message.with_text("Hello, world!"))

        # TODO: fix the case for my-agent once we have stopped santizing url safe agent ids
        mock_storage.task_deployments.get_task_deployment.assert_called_once_with(
            "my-agent",
            1,
            "production",
        )


class TestPrepareRunForModel:
    @pytest.fixture(autouse=True)
    def mock_storage_with_variant(self, mock_storage: Mock):
        def side_effect(value: Any):
            return value, True

        mock_storage.store_task_resource.side_effect = side_effect

    @pytest.mark.parametrize("role", ["user", "assistant", "system"])
    async def test_no_templated_message_no_input(self, proxy_handler: OpenAIProxyHandler, role: MessageRole):
        """Check that we don't set the message in the version properties if input is None"""
        result = await proxy_handler._prepare_for_model(
            agent_ref=ModelRef(model=Model.GPT_4O_LATEST, agent_id=None),
            tenant_data=PublicOrganizationData(),
            messages=Messages.with_messages(Message.with_text("Hello, world!", role=role)),
            input=None,
            response_format=None,
        )
        # All messages are passed through to the input, none are in the version
        assert result.final_input == Messages.with_messages(Message.with_text("Hello, world!", role=role))
        assert result.properties.messages is None

    async def test_no_templated_message_with_empty_input_sytem(
        self,
        proxy_handler: OpenAIProxyHandler,
    ):
        """When the input is an empty dict, we still use messages in the version properties"""
        result = await proxy_handler._prepare_for_model(
            agent_ref=ModelRef(model=Model.GPT_4O_LATEST, agent_id=None),
            tenant_data=PublicOrganizationData(),
            messages=Messages.with_messages(
                Message.with_text("You are a helpful assistant", role="system"),
                Message.with_text("Hello, world!", role="user"),
            ),
            input={},
            response_format=None,
        )
        assert result.final_input == {
            INPUT_KEY_MESSAGES: [Message.with_text("Hello, world!", role="user")],
        }
        assert result.properties.messages == [
            Message.with_text("You are a helpful assistant", role="system"),
        ]

    async def test_no_templated_message_with_input_user(self, proxy_handler: OpenAIProxyHandler):
        """Check that we set the message in the version properties if input is not None"""
        result = await proxy_handler._prepare_for_model(
            agent_ref=ModelRef(model=Model.GPT_4O_LATEST, agent_id=None),
            tenant_data=PublicOrganizationData(),
            messages=Messages.with_messages(Message.with_text("Hello, world!", role="user")),
            input={},
            response_format=None,
        )
        assert result.final_input == {
            INPUT_KEY_MESSAGES: [Message.with_text("Hello, world!", role="user")],
        }

        assert result.properties.messages == []

    async def test_templated_messages(self, proxy_handler: OpenAIProxyHandler):
        result = await proxy_handler._prepare_for_model(
            agent_ref=ModelRef(model=Model.GPT_4O_LATEST, agent_id=None),
            tenant_data=PublicOrganizationData(),
            messages=Messages.with_messages(
                Message.with_text("Hello, world!", role="system"),
                Message.with_text("Hello, {{name}}!", role="user"),
                Message.with_text("Hello, {{dude}}!", role="user"),
                Message.with_text("Not a template", role="user"),
            ),
            input={
                "name": "John",
                "dude": "Jane",
            },
            response_format=None,
        )
        assert result.final_input == {
            "name": "John",
            "dude": "Jane",
            INPUT_KEY_MESSAGES: [
                Message.with_text("Not a template", role="user"),
            ],
        }
        assert result.properties.messages == [
            Message.with_text("Hello, world!", role="system"),
            Message.with_text("Hello, {{name}}!", role="user"),
            Message.with_text("Hello, {{dude}}!", role="user"),
        ]
        assert result.variant.input_schema.json_schema == {
            "format": "messages",
            "properties": {
                "name": {"type": "string"},
                "dude": {"type": "string"},
            },
            "type": "object",
        }


class TestBuildVariant:
    def test_build_variant_no_template(self):
        result, idx = OpenAIProxyHandler._build_variant(
            messages=Messages.with_messages(Message.with_text("Hello, world!", role="user")),
            agent_slug="slug-agent",
            input=None,
            response_format=None,
        )
        assert idx == -1
        assert result.input_schema == RawMessagesSchema
        assert result.output_schema == RawStringMessageSchema

        assert result.task_id == "slug-agent"
        assert result.name == "Slug Agent"

    def test_build_variant_weird_agent_id(self):
        result, idx = OpenAIProxyHandler._build_variant(
            messages=Messages.with_messages(Message.with_text("Hello, world!", role="user")),
            agent_slug="L'agent de la mère",
            input=None,
            response_format=None,
        )
        assert idx == -1
        assert result.input_schema == RawMessagesSchema
        assert result.output_schema == RawStringMessageSchema

        assert result.task_id == "lagent-de-la-mere"
        assert result.name == "L'agent de la mère"

    def test_build_variant_with_agent_id_with_underscores(self):
        result, idx = OpenAIProxyHandler._build_variant(
            messages=Messages.with_messages(Message.with_text("Hello, world!", role="user")),
            agent_slug="my_agent",
            input=None,
            response_format=None,
        )
        assert idx == -1
        # TODO: fix the case for my-agent
        assert result.task_id == "my-agent"
        assert result.name == "my_agent"
