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
    OpenAIProxyToolFunction,
)
from core.domain.consts import INPUT_KEY_MESSAGES
from core.domain.errors import BadRequestError
from core.domain.message import Message, MessageRole, Messages
from core.domain.models.models import Model
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_io import RawMessagesSchema
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
                function=OpenAIProxyToolFunction(
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
        result = await proxy_handler._prepare_run(completion_request, PublicOrganizationData())
        assert result.properties.enabled_tools == [
            Tool(name="my_function", input_schema={}, output_schema={}, strict=True),
        ]


class TestCheckForDuplicateMessages:
    def test_no_messages(self, proxy_handler: OpenAIProxyHandler):
        """Check that we just don't raise if we have no messages in the deployment"""
        messages = Messages(messages=[Message.with_text("Hello, world!")])
        proxy_handler._check_for_duplicate_messages(None, messages)

    def test_duplicate_messages(self, proxy_handler: OpenAIProxyHandler):
        """Check that we raise if we have duplicate messages"""
        messages = Messages(messages=[Message.with_text("Hello, world!")])
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
            messages=Messages(messages=[Message.with_text("Hello, world!")]),
            input=None,
            response_format=None,
        )
        assert result.final_input == Messages(messages=[Message.with_text("Hello, world!")])


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
            messages=Messages(messages=[Message.with_text("Hello, world!", role=role)]),
            input=None,
            response_format=None,
        )
        # All messages are passed through to the input, none are in the version
        assert result.final_input == Messages(messages=[Message.with_text("Hello, world!", role=role)])
        assert result.properties.messages is None

    async def test_no_templated_message_with_empty_input_sytem(
        self,
        proxy_handler: OpenAIProxyHandler,
    ):
        """When the input is an empty dict, we still use messages in the version properties"""
        result = await proxy_handler._prepare_for_model(
            agent_ref=ModelRef(model=Model.GPT_4O_LATEST, agent_id=None),
            tenant_data=PublicOrganizationData(),
            messages=Messages(
                messages=[
                    Message.with_text("You are a helpful assistant", role="system"),
                    Message.with_text("Hello, world!", role="user"),
                ],
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
            messages=Messages(messages=[Message.with_text("Hello, world!", role="user")]),
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
            messages=Messages(
                messages=[
                    Message.with_text("Hello, world!", role="system"),
                    Message.with_text("Hello, {{name}}!", role="user"),
                    Message.with_text("Hello, {{dude}}!", role="user"),
                    Message.with_text("Not a template", role="user"),
                ],
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
