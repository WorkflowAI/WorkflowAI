# pyright: reportPrivateUsage=false

from typing import Any

import pytest
from pydantic import AliasChoices
from pydantic.alias_generators import to_camel

from core.domain.errors import BadRequestError
from core.domain.fields.file import File
from core.domain.message import Message, MessageContent
from core.domain.models.models import Model
from core.domain.task_group_properties import TaskGroupProperties, ToolChoiceFunction
from core.domain.tool import Tool
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.domain.version_environment import VersionEnvironment
from core.providers.base.provider_error import MissingModelError
from core.tools import ToolKind
from core.utils.strings import to_pascal_case

from ._openai_proxy_models import (
    EnvironmentRef,
    ModelRef,
    OpenAIProxyChatCompletionRequest,
    OpenAIProxyContent,
    OpenAIProxyFunctionCall,
    OpenAIProxyImageURL,
    OpenAIProxyMessage,
    OpenAIProxyToolCall,
    _OpenAIProxyExtraFields,
)


class TestOpenAIProxyChatCompletionRequest:
    def test_minimal_payload(self):
        """Check that we have enough defaults to accept minimal payload"""
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
            },
        )
        assert payload

    def test_workflowai_internal(self):
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o-mini",
                "messages": [],
                "workflowai_internal": {
                    "variant_id": "123",
                    "version_messages": [
                        {
                            "role": "system",
                            "content": [{"type": "text", "text": "You are a helpful assistant"}],
                        },
                    ],
                },
                "agent_id": "123",
                "stream": True,
                "stream_options": {
                    "valid_json_chunks": True,
                },
            },
        )
        assert payload
        assert payload.workflowai_internal is not None
        assert payload.workflowai_internal.variant_id == "123"
        assert payload.workflowai_internal.version_messages == [
            Message.with_text("You are a helpful assistant", role="system"),
        ]

    @pytest.mark.parametrize(
        "extra",
        (
            pytest.param(
                {
                    "input": {"h": "w"},
                    "conversation_id": "123",
                    "agent_id": "456",
                    "use_fallback": "never",
                    "provider": "openai",
                },
                id="snake_case",
            ),
            pytest.param(
                {
                    "input": {"h": "w"},
                    "conversationId": "123",
                    "agentId": "456",
                    "useFallback": "never",
                    "provider": "openai",
                },
                id="camel_case",
            ),
            pytest.param(
                {
                    "Input": {"h": "w"},
                    "ConversationId": "123",
                    "AgentId": "456",
                    "UseFallback": "never",
                    "Provider": "openai",
                },
                id="pascal_case",
            ),
        ),
    )
    def test_alias_generator(self, extra: dict[str, Any]):
        base: dict[str, Any] = {"messages": [], "model": "gpt-4o"}
        payload = OpenAIProxyChatCompletionRequest.model_validate(base | extra)
        assert payload.model_dump(exclude_unset=True) == {
            **base,
            "input": {"h": "w"},
            "conversation_id": "123",
            "agent_id": "456",
            "use_fallback": "never",
            "provider": "openai",
        }

    def test_different_alias_generators(self):
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {"messages": [], "model": "gpt-4o", "reasoningEffort": "low"},
        )
        assert payload.reasoning_effort is None


class TestOpenAIProxyExtraFieldsValidation:
    def test_exhaustive(self):
        # Check that all fields have a choice validation alias
        for k, field in _OpenAIProxyExtraFields.model_fields.items():
            assert field.validation_alias is not None
            assert isinstance(field.validation_alias, AliasChoices)
            assert field.validation_alias.choices[0] == k

            choice_set = set(field.validation_alias.choices)
            assert to_pascal_case(k) in choice_set
            assert to_camel(k) in choice_set


class TestOpenAIProxyContent:
    def test_image_url_to_domain(self):
        payload = OpenAIProxyContent(
            type="image_url",
            image_url=OpenAIProxyImageURL(
                url="https://hello.com/image.png",
            ),
        )
        assert payload.to_domain() == MessageContent(file=File(url="https://hello.com/image.png", format="image"))

    def test_stripped_text(self):
        payload = OpenAIProxyContent(
            type="text",
            text="   Hello, world!   ",
        )
        assert payload.to_domain() == MessageContent(text="Hello, world!")


class TestOpenAIProxyMessageToDomain:
    def test_with_tool_calls(self):
        payload = OpenAIProxyMessage(
            role="tool",
            content="Hello, world!",
            tool_call_id="1",
        )
        assert payload.to_domain() == Message(
            role="user",
            content=[
                MessageContent(
                    tool_call_result=ToolCall(
                        id="1",
                        tool_name="",
                        tool_input_dict={},
                        result="Hello, world!",
                    ),
                ),
            ],
        )

    def test_with_tool_call_requests(self):
        message = OpenAIProxyMessage(
            content="I'll help you draft an email to this GitHub user. First, let me gather their information to personalize the message.",
            role="assistant",
            tool_calls=[
                OpenAIProxyToolCall(
                    id="toolu_01DWXmuSygXFvBcVTxhEoCeb",
                    type="function",
                    function=OpenAIProxyFunctionCall(
                        name="enrich_github_username",
                        arguments='{"github_username": "guillaumegoogle"}',
                    ),
                ),
            ],
            function_call=None,
            tool_call_id=None,
        )
        domain_message = message.to_domain()
        assert domain_message is not None
        assert domain_message.role == "assistant"
        assert len(domain_message.content) == 2
        assert (
            domain_message.content[0].text
            == "I'll help you draft an email to this GitHub user. First, let me gather their information to personalize the message."
        )
        assert domain_message.content[1].tool_call_request is not None
        assert domain_message.content[1].tool_call_request.id == "toolu_01DWXmuSygXFvBcVTxhEoCeb"

    def test_empty_content_in_tool_message(self):
        message = OpenAIProxyMessage.model_validate(
            {
                "content": "",
                "role": "tool",
                "tool_call_id": "2",
            },
        )
        domain_message = message.to_domain()
        assert domain_message is not None
        assert len(domain_message.content) == 1
        assert domain_message.content[0].tool_call_result

    def test_function_role(self):
        message = OpenAIProxyMessage(
            role="function",
            name="my_function",
            content="Hello, world!",
            # Will likely not be set by the user but instead by the domain_messages method
            tool_call_id="1",
        )
        domain_message = message.to_domain()
        assert domain_message is not None
        assert domain_message.role == "user"
        assert domain_message.content[0] == MessageContent(
            tool_call_result=ToolCall(
                id="1",
                tool_name="",
                tool_input_dict={},
                result="Hello, world!",
            ),
        )

    def test_empty_message(self):
        message = OpenAIProxyMessage(
            role="user",
            content="",
        )
        domain_message = message.to_domain()
        assert domain_message is None


class TestOpenAIProxyChatCompletionRequestDomainMessages:
    def test_with_function_call(self):
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [
                    {"role": "user", "content": "Hello, world!"},
                    {
                        "role": "assistant",
                        "function_call": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
                    },
                    {
                        "role": "function",
                        "name": "get_weather",
                        "content": "The weather in Paris is sunny",
                    },
                ],
                "model": "gpt-4o",
            },
        )
        messages = list(payload.domain_messages())
        assert len(messages) == 3
        assert messages[0] == Message(role="user", content=[MessageContent(text="Hello, world!")])
        assert messages[1] == Message(
            role="assistant",
            content=[
                MessageContent(
                    tool_call_request=ToolCallRequestWithID(
                        id="get_weather_30f889b51cc908ea225f3b5a5c6939cf",
                        tool_name="get_weather",
                        tool_input_dict={"city": "Paris"},
                    ),
                ),
            ],
        )
        assert messages[2] == Message(
            role="user",
            content=[
                MessageContent(
                    tool_call_result=ToolCall(
                        id="get_weather_30f889b51cc908ea225f3b5a5c6939cf",
                        tool_name="",
                        tool_input_dict={},
                        result="The weather in Paris is sunny",
                    ),
                ),
            ],
        )

    def test_empty_message(self):
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "system", "content": "Hello, world!"}, {"role": "user", "content": ""}],
                "model": "gpt-4o",
            },
        )
        messages = list(payload.domain_messages())
        assert len(messages) == 1
        assert messages[0] == Message(role="system", content=[MessageContent(text="Hello, world!")])


class TestOpenAIProxyChatCompletionRequestToolChoice:
    @pytest.mark.parametrize(
        "tool_choice_input, expected_tool_choice_output",
        [
            (None, None),
            ("auto", "auto"),
            ("none", "none"),
            ("required", "required"),
            (
                {"type": "function", "function": {"name": "my_function"}},
                ToolChoiceFunction(name="my_function"),
            ),
            ("invalid_choice", None),
        ],
    )
    def test_workflowai_tool_choice(self, tool_choice_input: Any, expected_tool_choice_output: Any):
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
                "tool_choice": tool_choice_input,
            },
        )
        assert payload.worflowai_tool_choice == expected_tool_choice_output

    @pytest.mark.parametrize(
        "tool_choice_input, expected_tool_choice_output",
        [
            pytest.param(None, None, id="none"),
            pytest.param("auto", "auto", id="auto"),
            pytest.param("none", "none", id="none"),
            pytest.param(
                {"name": "my_function"},
                ToolChoiceFunction(name="my_function"),
                id="function",
            ),
            pytest.param("invalid_choice", None, id="invalid"),
        ],
    )
    def test_workflowai_tool_choice_function_call(self, tool_choice_input: Any, expected_tool_choice_output: Any):
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
                "function_call": tool_choice_input,
            },
        )
        assert payload.worflowai_tool_choice == expected_tool_choice_output


class TestOpenAIProxyChatCompletionRequestExtractReferences:
    @pytest.mark.parametrize(
        ("req", "agent_id"),
        [
            pytest.param({}, None, id="model only"),
            pytest.param({"model": "my-agent/gpt-4o"}, "my-agent", id="model with agent_id"),
            pytest.param({"model": "my_agent/gpt-4o"}, "my_agent", id="model with agent_id underscores"),
            pytest.param({"metadata": {"agent_id": "my-agent"}}, "my-agent", id="agent id in metadata"),
            pytest.param({"agent_id": "my-agent"}, "my-agent", id="model with agent_id"),
            # Model has a provider prefix but agent_id is provided so it takes precedence
            pytest.param(
                {"model": "openai/gpt-4o", "agent_id": "my-agent"},
                "my-agent",
                id="model with provider prefix",
            ),
            # Model has a provider prefix but agent id is provided in metadata so it takes precedence
            pytest.param(
                {"model": "openai/gpt-4o", "metadata": {"agent_id": "my-agent"}},
                "my-agent",
                id="model with provider prefix and agent id in metadata",
            ),
            # agent_id and metadata are set so agent_id takes precedence
            pytest.param(
                {"model": "openai/gpt-4o", "agent_id": "my-agent", "metadata": {"agent_id": "metadata-agent"}},
                "my-agent",
                id="model with provider prefix, agent id in body and metadata",
            ),
            # When the environment in metadata is not a valid WAI environment we just ignore it
            # to avoid collisions with user provided environment
            pytest.param(
                {"model": "gpt-4o", "metadata": {"agent_id": "my-agent", "environment": "whatever"}},
                "my-agent",
                id="environment in metadata does not have the proper format",
            ),
            pytest.param(
                {"model": "gpt-4o", "metadata": {"agent_id": "my-agent", "environment": "#123/invalid"}},
                "my-agent",
                id="environment in metadata does not have a correct environment",
            ),
        ],
    )
    def test_model_ref(self, req: dict[str, Any], agent_id: str | None):
        """Test cases where the request points to a model, not a deployment"""
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
                **req,
            },
        )
        refs = payload.extract_references()
        assert isinstance(refs, ModelRef)
        assert refs.model == Model.GPT_4O_LATEST
        assert refs.agent_id == agent_id

    @pytest.mark.parametrize(
        ("req", "expected_agent_id", "expected_schema_id", "expected_environment"),
        [
            pytest.param(
                {"model": "my-agent/#123/production"},
                "my-agent",
                123,
                VersionEnvironment.PRODUCTION,
                id="agent_schema_env_format",
            ),
            pytest.param(
                {"model": "my_agent/#123/production"},
                "my_agent",
                123,
                VersionEnvironment.PRODUCTION,
                id="agent_id_underscores",
            ),
            pytest.param(
                {
                    "model": "gpt-4o",
                    "agent_id": "my-agent",
                    "schema_id": 123,
                    "environment": "production",
                },
                "my-agent",
                123,
                VersionEnvironment.PRODUCTION,
                id="body_parameters",
            ),
            pytest.param(
                {"model": "my-agent/#123/prod"},
                "my-agent",
                123,
                VersionEnvironment.PRODUCTION,
                id="environment_alias",
            ),
            pytest.param(
                {
                    "model": "gpt-4o",
                    "metadata": {
                        "agent_id": "metadata-agent",
                        "environment": "#456/production",
                    },
                },
                "metadata-agent",
                456,
                VersionEnvironment.PRODUCTION,
                id="metadata_with_environment_deployment",
            ),
            pytest.param(
                {
                    "model": "gpt-4o",
                    "metadata": {
                        "agent_id": "metadata-agent",
                        "environment": "#789/prod",
                    },
                },
                "metadata-agent",
                789,
                VersionEnvironment.PRODUCTION,
                id="metadata_with_environment_alias",
            ),
            pytest.param(
                {
                    "model": "gpt-4o",
                    "metadata": {
                        "agent_id": "metadata-agent",
                        "environment": "#101/development",
                    },
                },
                "metadata-agent",
                101,
                VersionEnvironment.DEV,
                id="metadata_with_development_env",
            ),
        ],
    )
    def test_environment_ref(
        self,
        req: dict[str, Any],
        expected_agent_id: str,
        expected_schema_id: int,
        expected_environment: VersionEnvironment,
    ):
        """Test cases where the request points to an environment deployment"""
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                **req,
            },
        )
        refs = payload.extract_references()
        assert isinstance(refs, EnvironmentRef)
        assert refs.agent_id == expected_agent_id
        assert refs.schema_id == expected_schema_id
        assert refs.environment == expected_environment

    def test_invalid_model(self):
        """Test with invalid model"""
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "invalid-model",
            },
        )
        with pytest.raises(MissingModelError):
            payload.extract_references()

    @pytest.mark.parametrize(
        ("req", "expected_error_message"),
        [
            pytest.param(
                {
                    "model": "",  # model is empty here otherwise we fallback on the model in the body
                    "agent_id": "my-agent",
                    "schema_id": 123,
                    "environment": "invalid-env",
                },
                "is not a valid environment",
                id="invalid_environment",
            ),
            pytest.param(
                {
                    "model": "gpt-4o",
                    "agent_id": "my-agent",
                    "environment": "production",
                    # schema_id is missing
                },
                "agent_id, environment and schema_id must be provided",
                id="missing_required_fields",
            ),
            pytest.param(
                {"model": "my-agent/#123/invalid-env"},
                "does not refer to a valid model or deployment",
                id="invalid_deployment_string",
            ),
        ],
    )
    def test_environment_ref_errors(self, req: dict[str, Any], expected_error_message: str):
        """Test cases where environment reference extraction should raise errors"""
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                **req,
            },
        )
        with pytest.raises(BadRequestError) as exc_info:
            payload.extract_references()
        assert expected_error_message in str(exc_info.value)

    def test_metadata_without_agent_id_returns_none(self):
        """Test when metadata exists but has no agent_id"""
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
                "metadata": {"other_field": "value"},
            },
        )
        refs = payload.extract_references()
        assert isinstance(refs, ModelRef)
        assert refs.model == Model.GPT_4O_LATEST
        assert refs.agent_id is None

    def test_metadata_invalid_environment_format(self):
        """Test when metadata contains invalid environment format"""
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
                "metadata": {
                    "agent_id": "metadata-agent",
                    "environment": "invalid-format",
                },
            },
        )
        refs = payload.extract_references()
        assert isinstance(refs, ModelRef)
        assert refs.model == Model.GPT_4O_LATEST
        assert refs.agent_id == "metadata-agent"

    def test_metadata_with_no_metadata(self):
        """Test when no metadata is provided"""
        payload = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
            },
        )
        refs = payload.extract_references()
        assert isinstance(refs, ModelRef)
        assert refs.model == Model.GPT_4O_LATEST
        assert refs.agent_id is None


class TestOpenAIProxyChatCompletionRequestApplyTo:
    @pytest.fixture()
    def completion_request(self):
        return OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
                "temperature": 0.7,
                "top_p": 0.9,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.3,
                "parallel_tool_calls": True,
                "provider": "openai",
                "tool_choice": "auto",
                "max_tokens": 100,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "description": "A test tool",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            },
        )

    def test_apply_to_sets_all_fields(self, completion_request: OpenAIProxyChatCompletionRequest):
        """Test that apply_to sets all fields when none are set in properties"""

        properties = TaskGroupProperties()
        completion_request.apply_to(properties)

        assert properties.temperature == 0.7
        assert properties.top_p == 0.9
        assert properties.frequency_penalty == 0.5
        assert properties.presence_penalty == 0.3
        assert properties.parallel_tool_calls is True
        assert properties.provider == "openai"
        assert properties.tool_choice == "auto"
        assert properties.max_tokens == 100
        assert properties.enabled_tools is not None
        assert len(properties.enabled_tools) == 1
        tool = properties.enabled_tools[0]
        assert isinstance(tool, Tool)
        assert tool.name == "test_tool"

    def test_apply_to_does_not_modify_set_fields(self):
        """Test that apply_to does not modify fields that are already set"""
        completion_request = OpenAIProxyChatCompletionRequest(
            messages=[OpenAIProxyMessage(role="user", content="Hello, world!")],
            model="gpt-4o",
        )

        properties = TaskGroupProperties(
            temperature=0.5,
            top_p=0.8,
            frequency_penalty=0.2,
            presence_penalty=0.1,
            parallel_tool_calls=False,
            provider="anthropic",
            tool_choice="none",
            max_tokens=200,
        )
        copied = properties.model_copy()
        completion_request.apply_to(copied)

        assert copied == properties

    def test_apply_to_sets_default_temperature(self):
        """Test that apply_to sets default temperature when not set in request or properties"""
        completion_request = OpenAIProxyChatCompletionRequest(
            messages=[OpenAIProxyMessage(role="user", content="Hello, world!")],
            model="gpt-4o",
        )
        properties = TaskGroupProperties()
        completion_request.apply_to(properties)
        assert properties.temperature == 1.0

    def test_apply_to_handles_max_completion_tokens(self):
        """Test that apply_to handles max_completion_tokens correctly"""
        request = OpenAIProxyChatCompletionRequest(
            messages=[OpenAIProxyMessage(role="user", content="Hello, world!")],
            model="gpt-4o",
            max_completion_tokens=100,
        )
        properties = TaskGroupProperties()
        request.apply_to(properties)
        assert properties.max_tokens == 100

    def test_apply_to_handles_tools(self):
        """Test that apply_to handles tools correctly"""
        request = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "description": "A test tool",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            },
        )
        properties = TaskGroupProperties()
        request.apply_to(properties)
        assert properties.enabled_tools is not None
        assert len(properties.enabled_tools) == 1
        tool = properties.enabled_tools[0]
        assert isinstance(tool, Tool)
        assert tool.name == "test_tool"

    def test_apply_to_handles_functions(self):
        """Test that apply_to handles deprecated functions correctly"""
        request = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4o",
                "functions": [
                    {
                        "name": "test_function",
                        "description": "A test function",
                        "parameters": {"type": "object", "properties": {}},
                    },
                ],
            },
        )
        properties = TaskGroupProperties()
        request.apply_to(properties)
        assert properties.enabled_tools is not None
        assert len(properties.enabled_tools) == 1
        tool = properties.enabled_tools[0]
        assert isinstance(tool, Tool)
        assert tool.name == "test_function"


class TestDomainTools:
    def test_domain_tools_multiple_definitions(self):
        """Test that domain_tools raises an error if a tool is defined multiple times"""
        request = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [],
                "model": "gpt-4o",
                "tools": [
                    {"type": "function", "function": {"name": "test_tool", "parameters": {}}},
                    {"type": "function", "function": {"name": "test_tool", "parameters": {}}},
                ],
            },
        )
        with pytest.raises(BadRequestError) as e:
            request.domain_tools()
        assert "Tool test_tool is defined multiple times" in str(e.value)

    def test_returns_none_if_no_tools(self):
        """Test that domain_tools returns None if no tools are defined"""
        request = OpenAIProxyChatCompletionRequest.model_validate(
            {"messages": [], "model": "gpt-4o"},
        )
        assert request.domain_tools() is None

    def test_domain_tools_multiple_definitions_with_functions(self):
        """Test that domain_tools raises an error if a tool is defined multiple times"""
        request = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [],
                "model": "gpt-4o",
                "functions": [
                    {"name": "test_tool", "parameters": {}},
                ],
                "tools": [
                    {"type": "function", "function": {"name": "test_tool", "parameters": {}}},
                ],
            },
        )
        with pytest.raises(BadRequestError) as e:
            request.domain_tools()
        assert "Tool test_tool is defined multiple times" in str(e.value)

    def test_valid_tools_and_hosted_tools(self):
        """Test that domain_tools returns valid tools and hosted tools"""
        request = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [],
                "model": "gpt-4o",
                "tools": [
                    {"type": "function", "function": {"name": "test_tool", "parameters": {}}},
                    {"type": "function", "function": {"name": "@search-google"}},
                ],
            },
        )
        tools = request.domain_tools()
        assert tools is not None
        assert len(tools) == 2
        assert isinstance(tools[0], Tool)
        assert tools[0].name == "test_tool"
        assert tools[1] == ToolKind.WEB_SEARCH_GOOGLE

    def test_workflowai_tools_in_instructions(self):
        """Test that workflowai_tools are detected in system message"""
        request = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [
                    {"role": "system", "content": "Use @search-google to find information"},
                    {"role": "user", "content": "Hello, world!"},
                ],
                "model": "gpt-4o",
            },
        )
        tools = request.domain_tools()
        assert tools is not None
        assert len(tools) == 1
        assert tools[0] == ToolKind.WEB_SEARCH_GOOGLE

    def test_workflowai_tools_in_version_system_message(self):
        """Test that workflowai_tools are detected in tools"""
        request = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "messages": [
                    {"role": "user", "content": "Hello, world!"},
                ],
                "model": "gpt-4o",
                "workflowai_internal": {
                    "variant_id": "123",
                    "version_messages": [
                        {"role": "system", "content": [{"text": "Use @search-google to find information"}]},
                    ],
                },
            },
        )
        tools = request.domain_tools()
        assert tools is not None
        assert len(tools) == 1
        assert tools[0] == ToolKind.WEB_SEARCH_GOOGLE

    def test_duplicate_tools_in_system_message(self):
        """Test that duplicate tools are ignored in system message"""
        request = OpenAIProxyChatCompletionRequest.model_validate(
            {
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "Use @search-google to find information"},
                ],
                "tools": [
                    {"type": "function", "function": {"name": "@search-google"}},
                ],
            },
        )
        tools = request.domain_tools()
        assert tools is not None
        assert len(tools) == 1


class TestMapModelString:
    @pytest.mark.parametrize(
        "value, reasoning, expected",
        [
            pytest.param("gpt-4o-mini-latest", None, Model.GPT_4O_MINI_LATEST, id="exists"),
            pytest.param("gpt-4o", None, Model.GPT_4O_LATEST, id="unversioned"),
            pytest.param(
                "o3-mini-2025-01-31",
                "high",
                Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT,
                id="reasoning effort versioned",
            ),
            pytest.param(
                "o3-mini-2025-01-31",
                "high",
                Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT,
                id="reasoning effort versioned",
            ),
        ],
    )
    def test_with_reasoning(self, value: str, reasoning: str | None, expected: Model):
        assert OpenAIProxyChatCompletionRequest._map_model_str(value, reasoning) == expected


class TestCheckSupportedFields:
    @pytest.mark.parametrize(
        ("n", "raises"),
        [
            ("unset", False),
            (None, False),
            (1, False),
            (2, True),
        ],
    )
    def test_with_n(self, n: Any, raises: bool):
        payload: dict[str, Any] = {
            "messages": [],
            "model": "gpt-4o",
        }
        if n != "unset":
            payload["n"] = n
        request = OpenAIProxyChatCompletionRequest.model_validate(payload)
        if raises:
            with pytest.raises(BadRequestError):
                request.check_supported_fields()
        else:
            request.check_supported_fields()

    @pytest.mark.parametrize(
        ("logit_bias", "raises"),
        [
            pytest.param("unset", False, id="unset"),
            pytest.param(None, False, id="none"),
            pytest.param({}, False, id="empty"),
            pytest.param({"a": 1}, False, id="single"),
            pytest.param({"a": 1, "b": 2}, True, id="multiple"),
        ],
    )
    def test_with_logit_bias(self, logit_bias: Any, raises: bool):
        payload: dict[str, Any] = {
            "messages": [],
            "model": "gpt-4o",
        }
        if logit_bias != "unset":
            payload["logit_bias"] = logit_bias
        request = OpenAIProxyChatCompletionRequest.model_validate(payload)
        if raises:
            with pytest.raises(BadRequestError) as e:
                request.check_supported_fields()
            assert "logit_bias" in str(e.value)
