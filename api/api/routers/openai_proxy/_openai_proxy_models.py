import json
import logging
import re
import time
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Literal, NamedTuple, TypeAlias

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel, to_pascal
from workflowai import CacheUsage

from api.routers._common import SkipJsonSchema
from core.domain.agent_run import AgentRun
from core.domain.consts import METADATA_KEY_INTEGRATION
from core.domain.errors import BadRequestError
from core.domain.fields.file import File, FileKind
from core.domain.llm_completion import LLMCompletion
from core.domain.message import (
    Message,
    MessageContent,
    MessageRole,
)
from core.domain.models.model_data_mapping import MODEL_ALIASES
from core.domain.models.models import Model
from core.domain.models.providers import Provider
from core.domain.run_output import RunOutput
from core.domain.task_group_properties import TaskGroupProperties, ToolChoice, ToolChoiceFunction
from core.domain.tenant_data import PublicOrganizationData
from core.domain.tool import Tool
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.domain.types import AgentOutput
from core.domain.version_environment import VersionEnvironment
from core.providers.base.provider_error import MissingModelError
from core.tools import ToolKind, get_tools_in_instructions

# Goal of these models is to be as flexible as possible
# We definitely do not want to reject calls without being sure
# for example if OpenAI decides to change their API or we missed some param in the request
#
# Also all models have extra allowed so we can track extra values that we may have missed

_logger = logging.getLogger(__name__)


_UNSUPPORTED_FIELDS = {
    "logit_bias",
    "logprobs",
    "modalities",
    "prediction",
    "seed",
    "stop",
    "top_logprobs",
    "web_search_options",
}

_role_mapping: dict[str, MessageRole] = {
    "user": "user",
    "assistant": "assistant",
    "system": "system",
    "developer": "system",
    "tool": "user",
    "function": "user",
}


class OpenAIAudioInput(BaseModel):
    data: str
    format: str

    def to_domain(self) -> File:
        content_type = self.format
        if "/" not in content_type:
            content_type = f"audio/{content_type}"
        if not self.format or self.data.startswith("https://"):
            # Special case for when the format is not provided or when the data is in fact a URL
            return File(url=self.data, format=FileKind.AUDIO)
        return File(data=self.data, content_type=content_type, format=FileKind.AUDIO)


class OpenAIProxyImageURL(BaseModel):
    url: str
    detail: Literal["low", "high", "auto"] | None = None

    model_config = ConfigDict(extra="allow")


class OpenAIProxyContent(BaseModel):
    type: str
    text: str | None = None
    image_url: OpenAIProxyImageURL | None = None
    input_audio: OpenAIAudioInput | None = None

    def to_domain(self) -> MessageContent:
        match self.type:
            case "text":
                if not self.text:
                    raise BadRequestError("Text content is required")
                return MessageContent(text=self.text.strip())
            case "image_url":
                if not self.image_url:
                    raise BadRequestError("Image URL content is required")
                return MessageContent(file=File(url=self.image_url.url, format=FileKind.IMAGE))
            case "input_audio":
                if not self.input_audio:
                    raise BadRequestError("Input audio content is required")

                return MessageContent(file=self.input_audio.to_domain())
            case _:
                raise BadRequestError(f"Unknown content type: {self.type}", capture=True)

    model_config = ConfigDict(extra="allow")


class OpenAIProxyFunctionCall(BaseModel):
    name: str
    arguments: str | None = None

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_domain(cls, tool_call: ToolCallRequestWithID):
        return cls(
            name=tool_call.tool_name,
            # The OpenAI SDK does not like None here so we send an empty string instead
            arguments=json.dumps(tool_call.tool_input_dict) if tool_call.tool_input_dict else "",
        )

    def safely_parsed_argument(self) -> dict[str, Any]:
        if not self.arguments:
            return {}
        try:
            return json.loads(self.arguments)
        except json.JSONDecodeError:
            _logger.warning("Failed to parse arguments", extra={"arguments": self.arguments})
            return {"arguments": self.arguments}

    def to_domain(self, id: str):
        return ToolCallRequestWithID(
            id=id,
            tool_name=self.name,
            tool_input_dict=self.safely_parsed_argument(),
        )


class OpenAIProxyToolDefinition(BaseModel):
    description: str | None = None
    name: str = Field(
        description="The name of the tool. A tool can also reference a hosted WorkflowAI tool. Hosted "
        "WorkflowAI tools should always have a name that starts with `@` and have no description or parameters.",
    )
    parameters: dict[str, Any] | None = None
    strict: bool | None = None

    model_config = ConfigDict(extra="allow")

    def to_domain(self) -> Tool | ToolKind:
        if not self.parameters and not self.description and self.name.startswith("@"):
            try:
                return ToolKind.from_str(self.name)
            except ValueError:
                pass
        return Tool(
            name=self.name,
            description=self.description,
            input_schema=self.parameters or {},
            output_schema={},
            strict=self.strict,
        )


class OpenAIProxyTool(BaseModel):
    type: Literal["function"]
    function: OpenAIProxyToolDefinition

    model_config = ConfigDict(extra="allow")


class OpenAIProxyToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: OpenAIProxyFunctionCall  # Reusing FunctionCall structure for name/arguments

    @classmethod
    def from_domain(cls, tool_call: ToolCallRequestWithID):
        return cls(
            id=tool_call.id,
            function=OpenAIProxyFunctionCall.from_domain(tool_call),
        )

    def to_domain(self) -> ToolCallRequestWithID:
        return self.function.to_domain(self.id)

    model_config = ConfigDict(extra="allow")


class OpenAIProxyMessage(BaseModel):
    content: list[OpenAIProxyContent] | str | None = None
    name: str | None = None
    role: str

    tool_calls: list[OpenAIProxyToolCall] | None = None
    function_call: OpenAIProxyFunctionCall | None = None  # Deprecated
    tool_call_id: str | None = None

    @classmethod
    def from_run(cls, run: AgentRun, output_mapper: Callable[[AgentOutput], str | None], deprecated_function: bool):
        return cls(
            role="assistant",
            content=output_mapper(run.task_output),
            tool_calls=[OpenAIProxyToolCall.from_domain(t) for t in run.tool_call_requests]
            if run.tool_call_requests and not deprecated_function
            else None,
            function_call=OpenAIProxyFunctionCall.from_domain(run.tool_call_requests[0])
            if run.tool_call_requests and deprecated_function
            else None,
        )

    @property
    def first_string_content(self) -> str | None:
        if isinstance(self.content, str):
            return self.content
        if self.content and self.content[0].type == "text":
            return self.content[0].text
        return None

    def _content_iterator(self) -> Iterator[MessageContent]:
        # When the role is tool we know that the message only contains the tool call result

        if self.content:
            if isinstance(self.content, str):
                yield MessageContent(text=self.content)
            else:
                for c in self.content:
                    yield c.to_domain()

        if self.function_call:
            yield MessageContent(tool_call_request=self.function_call.to_domain(""))
        if self.tool_calls:
            for t in self.tool_calls:
                yield MessageContent(tool_call_request=t.to_domain())

    def _to_tool_call_result_message(self) -> Message:
        if self.content is None:
            raise BadRequestError("Content is required when providing a tool call result", capture=True)
        if not self.tool_call_id:
            raise BadRequestError("tool_call_id is required when providing a tool call result", capture=True)
        return Message(
            content=[
                MessageContent(
                    tool_call_result=ToolCall(
                        id=self.tool_call_id,
                        tool_name="",
                        tool_input_dict={},
                        result=self.content,
                    ),
                ),
            ],
            role="user",
        )

    def to_domain(self) -> Message | None:
        # When the role is tool we know that the message only contains the tool call result
        if self.role == "tool" or self.role == "function":
            return self._to_tool_call_result_message()

        if self.tool_call_id:
            raise BadRequestError("tool_call_id is only allowed when the role is tool", capture=True)

        content = list(self._content_iterator())
        if not content:
            # We just received a completely empty message
            # It would be better to raise an error here but OpenAI tolerates empty messages for some reason
            # so we need to accept them as well
            # For now we simply just completly ignore them. Some users used to send empty messages
            # to account for specificites of models/providers (e-g a provider always requiring a user message, etc.)
            # This is handled dynamically by each provider object in WorkflowAI so we should be able to safely skip them
            return None
        try:
            role = _role_mapping[self.role]
        except KeyError:
            raise BadRequestError(f"Unknown role: {self.role}", capture=True)

        return Message(content=content, role=role)

    model_config = ConfigDict(extra="allow")


class OpenAIProxyResponseFormat(BaseModel):
    type: str

    class JsonSchema(BaseModel):
        schema_: dict[str, Any] = Field(alias="schema")

    json_schema: JsonSchema | None = None

    model_config = ConfigDict(extra="allow")


class OpenAIProxyStreamOptions(BaseModel):
    include_usage: bool | None = None

    valid_json_chunks: bool | None = Field(
        default=None,
        description="Whether to only send valid JSON chunks when streaming. When set to true, the delta aggregation "
        "is performed by WorkflowAI and only valid aggregated JSON strings are sent in place of the content delta. "
        "valid_json_chunks is only relevant when using a json based response format (either `json_object` or "
        "`json_schema`).",
    )

    model_config = ConfigDict(extra="allow")


class OpenAIProxyToolChoiceFunction(BaseModel):
    name: str


class OpenAIProxyToolChoice(BaseModel):
    type: Literal["function"]
    function: OpenAIProxyToolChoiceFunction


class OpenAIProxyPredicatedOutput(BaseModel):
    content: str | list[OpenAIProxyContent]
    type: str


class OpenAIProxyWebSearchOptions(BaseModel):
    search_context_size: str

    # TODO:
    user_location: dict[str, Any] | None = None


class EnvironmentRef(NamedTuple):
    """A reference to a deployed environment"""

    agent_id: str
    schema_id: int
    environment: VersionEnvironment


class ModelRef(NamedTuple):
    """A reference to a model with an optional agent id"""

    model: Model
    agent_id: str | None


_environment_aliases = {
    "prod": VersionEnvironment.PRODUCTION,
    "development": VersionEnvironment.DEV,
}
_agent_schema_env_regex = re.compile(
    rf"^([^/]+)/#(\d+)/({'|'.join([*VersionEnvironment, *_environment_aliases.keys()])})$",
)
_metadata_env_regex = re.compile(
    rf"^#(\d+)/({'|'.join([*VersionEnvironment, *_environment_aliases.keys()])})$",
)


def _alias_generator(field_name: str):
    aliases = {field_name, to_pascal(field_name), to_camel(field_name)}
    aliases.remove(field_name)
    return AliasChoices(field_name, *aliases)


class _OpenAIProxyExtraFields(BaseModel):
    input: dict[str, Any] | None = Field(
        default=None,
        description="An input to template the messages with.This field is not defined by the default OpenAI api."
        "When provided, an input schema is generated and the messages are used as a template.",
        validation_alias=_alias_generator("input"),
    )

    provider: str | None = Field(
        default=None,
        description="A specific provider to use for the request. When provided, multi provider fallback is disabled."
        "The attribute is ignored if the provider is not supported.",
        validation_alias=_alias_generator("provider"),
    )

    agent_id: str | None = Field(
        default=None,
        description="The id of the agent to use for the request. If not provided, the default agent is used.",
        validation_alias=_alias_generator("agent_id"),
    )

    environment: str | None = Field(
        default=None,
        description="A reference to an environment where the agent is deployed. It can also be provided in the model "
        "with the format `agent_id/#schema_id/environment`",
        validation_alias=_alias_generator("environment"),
    )

    schema_id: int | None = Field(
        default=None,
        description="The agent schema id. Required when using a deployment. It can also be provided in the model "
        "with the format `agent_id/#schema_id/environment`",
        validation_alias=_alias_generator("schema_id"),
    )

    use_cache: CacheUsage | None = Field(
        default=None,
        validation_alias=_alias_generator("use_cache"),
    )

    use_fallback: Literal["auto", "never"] | list[str] | None = Field(
        default=None,
        description="A way to configure the fallback behavior",
        validation_alias=_alias_generator("use_fallback"),
    )

    conversation_id: str | None = Field(
        default=None,
        description="The conversation id to associate with the run. If not provided, WorkflowAI will attempt to "
        "match the message history to an existing conversation. If no conversation is found, a new "
        "conversation will be created.",
        validation_alias=_alias_generator("conversation_id"),
    )


class OpenAIProxyChatCompletionRequest(_OpenAIProxyExtraFields):
    messages: list[OpenAIProxyMessage] = Field(default_factory=list)
    model: str
    frequency_penalty: float | None = None
    function_call: str | OpenAIProxyToolChoiceFunction | None = None
    functions: list[OpenAIProxyToolDefinition] | None = None

    logit_bias: dict[str, float] | None = None
    logprobs: bool | None = None

    max_completion_tokens: int | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] | None = None
    modalities: list[Literal["text", "audio"]] | None = None
    n: int | None = None
    parallel_tool_calls: bool | None = None
    prediction: OpenAIProxyPredicatedOutput | None = None
    presence_penalty: float | None = None
    reasoning_effort: str | None = None
    response_format: OpenAIProxyResponseFormat | None = None

    seed: int | None = None
    service_tier: str | None = None
    stop: str | list[str] | None = None
    store: bool | None = None
    stream: bool | None = None
    stream_options: OpenAIProxyStreamOptions | None = None
    temperature: float | None = None  # default OAI temperature differs from own default
    tool_choice: str | OpenAIProxyToolChoice | None = None
    tools: list[OpenAIProxyTool] | None = None
    top_logprobs: int | None = None
    top_p: float | None = None
    user: str | None = None
    web_search_options: OpenAIProxyWebSearchOptions | None = None

    # Internal workflowai properties, allowing the playground to trigger runs
    # by providing a variant id and version messages
    class WorkflowAIInternal(BaseModel):
        variant_id: str
        version_messages: list[Message] | None = None

    # Not in extra fields because we don't want to expose them or add an alias
    workflowai_internal: SkipJsonSchema[WorkflowAIInternal | None] = None

    model_config = ConfigDict(extra="allow")

    @property
    def uses_deprecated_functions(self) -> bool:
        return self.functions is not None

    @property
    def _first_system_content(self) -> str | None:
        """Returns the text content of the first system message if the first message is a system message
        The first message can either come from the version or the input messages
        """
        if self.workflowai_internal and self.workflowai_internal.version_messages:
            message = self.workflowai_internal.version_messages[0]
            try:
                return next(c.text for c in message.content if c.text)
            except StopIteration:
                return None
        if self.messages and self.messages[0].role == "system":
            return self.messages[0].first_string_content
        return None

    def _raw_tool_iterator(self) -> Iterator[OpenAIProxyToolDefinition]:
        if self.tools:
            for t in self.tools:
                if t.type == "function":
                    yield t.function
        if self.functions:
            yield from self.functions

    def domain_tools(self) -> list[Tool | ToolKind] | None:
        """Returns a tuple of the tools and a boolean indicating if the function call is deprecated"""

        def _iterator() -> Iterator[Tool | ToolKind]:
            used_tool_names = set[str]()
            for t in self._raw_tool_iterator():
                d = t.to_domain()
                if d.name in used_tool_names:
                    raise BadRequestError(f"Tool {d.name} is defined multiple times", capture=True)
                used_tool_names.add(d.name)
                yield d

            if first_content := self._first_system_content:
                for tool in get_tools_in_instructions(first_content):
                    # Ignoring potential duplicates
                    if tool.name in used_tool_names:
                        continue
                    used_tool_names.add(tool.name)
                    yield tool

        return list(_iterator()) or None

    def register_metadata(self, d: dict[str, Any]):
        if self.metadata:
            self.metadata = {**self.metadata, **d}
        else:
            self.metadata = d

    def full_metadata(self, headers: Mapping[str, Any]) -> dict[str, Any] | None:
        base = self.metadata or {}
        base[METADATA_KEY_INTEGRATION] = "openai_chat_completions"
        if self.user:
            base["user"] = self.user
        if browser_agent := headers.get("user-agent"):
            base["user-agent"] = browser_agent
        return base

    def check_supported_fields(self):
        set_fields = self.model_fields_set
        used_unsupported_fields = set_fields.intersection(_UNSUPPORTED_FIELDS)
        if used_unsupported_fields:
            # Ignoring all set None fields
            fields = [f for f in used_unsupported_fields if getattr(self, f, None) is not None]
            if not fields:
                return

            plural = len(fields) > 1
            fields.sort()
            raise BadRequestError(
                f"Field{'s' if plural else ''} `{'`, `'.join(fields)}` {'are' if plural else 'is'} not supported",
                capture=True,
            )

        if self.n and self.n > 1:
            raise BadRequestError(
                "An n value greated than 1 is not supported",
            )

    @property
    def workflowai_provider(self) -> Provider | None:
        if self.provider:
            try:
                return Provider(self.provider)
            except ValueError:
                # Logging for now just in case
                _logger.warning("Received an unsupported provider", extra={"provider": self.provider})
                return None
        return None

    @property
    def worflowai_tool_choice(self) -> ToolChoice | None:
        tool_choice = self.tool_choice or self.function_call
        if not tool_choice:
            return None

        if isinstance(tool_choice, OpenAIProxyToolChoice):
            return ToolChoiceFunction(name=tool_choice.function.name)
        if isinstance(tool_choice, OpenAIProxyToolChoiceFunction):
            return ToolChoiceFunction(name=tool_choice.name)
        match tool_choice:
            case "auto":
                return "auto"
            case "none":
                return "none"
            case "required":
                return "required"
            case _:
                _logger.warning("Received an unsupported tool choice", extra={"tool_choice": self.tool_choice})
        return None

    def _env_from_model_str(self) -> EnvironmentRef | None:
        if match := _agent_schema_env_regex.match(self.model):
            try:
                return EnvironmentRef(
                    agent_id=match.group(1),
                    schema_id=int(match.group(2)),
                    environment=VersionEnvironment(_environment_aliases.get(match.group(3), match.group(3))),
                )
            except Exception:
                # That should really not happen. It would be pretty bad because it might mean that our regexp
                # is broken
                _logger.exception(
                    "Model matched regexp but we failed to parse the values",
                    extra={"model": self.model},
                )
        return None

    def _env_from_fields(self, agent_id: str | None, model: Model | None) -> EnvironmentRef | None:
        if not (self.environment or self.schema_id):
            return None
        if not (self.environment and self.schema_id and agent_id):
            raise BadRequestError(
                "When an environment or schema_id is provided, agent_id, environment and schema_id must be provided",
                capture=True,
                extras={"model": self.model, "environment": self.environment, "schema_id": self.schema_id},
            )

        try:
            environment = VersionEnvironment(self.environment)
        except Exception:
            if model:
                # That's ok. It could mean that someone passed an extra body parameter that's also called
                # environment. We can probably ignore it.
                _logger.warning(
                    "Received an invalid environment",
                    extra={"environment": self.environment, "model": self.model},
                )
                return None
            # We don't have a model. Meaning that it's likely a user error
            raise BadRequestError(
                f"Environment {self.environment} is not a valid environment. Valid environments are: {', '.join(VersionEnvironment)}",
                capture=True,
                extras={"model": self.model, "environment": self.environment, "schema_id": self.schema_id},
            )
        return EnvironmentRef(
            agent_id=agent_id,
            schema_id=self.schema_id,
            environment=environment,
        )

    @classmethod
    def _map_model_str(cls, model: str, reasoning_effort: str | None) -> Model | None:
        if m := MODEL_ALIASES.get(model):
            return m
        if reasoning_effort:
            try:
                return Model(f"{model}-{reasoning_effort}")
            except ValueError:
                pass
        try:
            return Model(model)
        except ValueError:
            return None

    def parsed_use_fallback(self) -> Literal["auto", "never"] | list[Model] | None:
        if isinstance(self.use_fallback, list):
            out: list[Model] = []
            for model in self.use_fallback:
                if parsed := self._map_model_str(model, None):
                    out.append(parsed)
                else:
                    raise MissingModelError(model=model)
            return out
        return self.use_fallback

    def _reference_from_metadata(self, model: Model, agent_id: str | None) -> EnvironmentRef | ModelRef | None:
        if not self.metadata or "agent_id" not in self.metadata:
            return None

        # Overriding if the agent_id is None or not provided directly in the request
        if not agent_id or not self.agent_id:
            agent_id = self.metadata.get("agent_id")
        if not agent_id:
            return None

        if "environment" in self.metadata:
            match = _metadata_env_regex.match(self.metadata["environment"])
            if match:
                try:
                    return EnvironmentRef(
                        agent_id=self.metadata["agent_id"],
                        schema_id=int(match.group(1)),
                        environment=VersionEnvironment(_environment_aliases.get(match.group(2), match.group(2))),
                    )
                except Exception:
                    _logger.exception("Failed to parse environment from metadata", extra={"metadata": self.metadata})
                    return None

        return ModelRef(
            model=model,
            agent_id=agent_id,
        )

    def extract_references(self) -> EnvironmentRef | ModelRef:
        """Extracts the model, agent_id, schema_id and environment from the model string
        and other body optional parameters.
        References can come from either:
        - the model string with a format either "<model>", "<agent_id>/<model>" or "<agent_id>/#<schema_id>/<environment>"
        - the body parameters environment, schema_id and agent_id
        """

        if env := self._env_from_model_str():
            return env

        splits = self.model.split("/")
        agent_id = self.agent_id or (splits[0] if len(splits) > 1 else None)
        # Getting the model from the last component. This is to support cases like litellm that
        # prefix the model string with the provider
        model = self._map_model_str(splits[-1], self.reasoning_effort)

        if env := self._env_from_fields(agent_id, model):
            return env

        if not model:
            if len(splits) > 2:
                # This is very likely an invalid environment error so we should raise an explicit BadRequestError
                raise BadRequestError(
                    f"'{self.model}' does not refer to a valid model or deployment. Use either the "
                    "'<agent-id>/#<schema-id>/<environment>' format to target a deployed environment or "
                    "<agent-id>/<model> to target a specific model. If the model cannot be changed, it is also "
                    "possible to pass the agent_id, schema_id and environment at the root of the completion request. "
                    "See https://run.workflowai.com/docs#/openai/chat_completions_v1_chat_completions_post for more "
                    "information.",
                    capture=True,
                    extras={"model": self.model},
                )
            raise MissingModelError(model=splits[-1])

        if from_metadata := self._reference_from_metadata(model=model, agent_id=agent_id):
            return from_metadata

        return ModelRef(
            model=model,
            agent_id=agent_id,
        )

    def apply_to(self, properties: TaskGroupProperties):  # noqa: C901
        if self.temperature is not None:
            properties.temperature = self.temperature
        elif properties.temperature is None:
            # If the model does not support temperature, we set it to 1
            # Since 1 is the default temperature for OAI
            properties.temperature = 1

        if self.top_p is not None:
            properties.top_p = self.top_p
        if self.frequency_penalty is not None:
            properties.frequency_penalty = self.frequency_penalty
        if self.presence_penalty is not None:
            properties.presence_penalty = self.presence_penalty
        if self.parallel_tool_calls is not None:
            properties.parallel_tool_calls = self.parallel_tool_calls
        if self.workflowai_provider is not None:
            properties.provider = self.workflowai_provider
        if self.worflowai_tool_choice is not None:
            properties.tool_choice = self.worflowai_tool_choice
        if max_tokens := self.max_completion_tokens or self.max_tokens:
            properties.max_tokens = max_tokens
        if tools := self.domain_tools():
            properties.enabled_tools = tools

    def domain_messages(self) -> Iterator[Message]:
        previous_message: Message | None = None
        for m in self.messages:
            if m.role == "function":
                # When the message is a function, we are missing the tool call ID.
                # But there must be a tool call request in the previous message and we can just
                # re-use the id
                # So we first make sure that the previous message is an assistant message
                if not previous_message or not previous_message.role == "assistant":
                    raise BadRequestError(
                        "Message with role 'function' must be preceded by an assistant message with a function call",
                    )
                # That it has a name since we need to match by name
                if not m.name:
                    raise BadRequestError("Message with role 'function' must have a name")
                # Then we find the tool call request in the previous message that matches the function name
                previous_request = next(
                    (
                        c.tool_call_request
                        for c in previous_message.content
                        if c.tool_call_request and c.tool_call_request.tool_name == m.name
                    ),
                    None,
                )
                if not previous_request:
                    raise BadRequestError(
                        "Message with role 'function' must be preceded by an assistant message with a function call "
                        f"for the function {m.name}",
                    )
                # And then we assign the tool_call_id so that it is properly picked up
                # Here the tool_call_id will probably have been autogenerated when instantiating the
                # ToolCallRequestWithID. See ToolCallRequestWithID.post_validate
                m.tool_call_id = previous_request.id
            if converted := m.to_domain():
                yield converted
                previous_message = converted


# --- Response Models ---


class OpenAIProxyCompletionUsage(BaseModel):
    completion_tokens: int
    prompt_tokens: int
    total_tokens: int

    @classmethod
    def from_domain(cls, completion: LLMCompletion):
        if (
            not completion.usage
            or completion.usage.prompt_token_count is None
            or completion.usage.completion_token_count is None
        ):
            return None

        return cls(
            completion_tokens=int(completion.usage.completion_token_count),
            prompt_tokens=int(completion.usage.prompt_token_count),
            total_tokens=int(completion.usage.prompt_token_count + completion.usage.completion_token_count),
        )


class _ExtraChoiceAttributes(BaseModel):
    cost_usd: float | None = Field(description="The cost of the completion in USD, WorkflowAI specific")
    duration_seconds: float | None = Field(description="The duration of the completion in seconds, WorkflowAI specific")
    feedback_token: str = Field(
        description="WorkflowAI Specific, a token to send feedback from client side without authentication",
    )
    url: str = Field(description="The URL of the run")


class OpenAIProxyChatCompletionChoice(_ExtraChoiceAttributes):
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter", "function_call"]
    index: int
    message: OpenAIProxyMessage

    @classmethod
    def from_domain(
        cls,
        run: AgentRun,
        output_mapper: Callable[[AgentOutput], str | None],
        deprecated_function: bool,
        feedback_generator: Callable[[str], str],
        org: PublicOrganizationData,
    ):
        msg = OpenAIProxyMessage.from_run(run, output_mapper, deprecated_function)
        if run.tool_call_requests:
            finish_reason = "function_call" if deprecated_function else "tool_calls"
        else:
            finish_reason = "stop"

        return cls(
            finish_reason=finish_reason,
            index=0,
            message=msg,
            duration_seconds=run.duration_seconds,
            feedback_token=feedback_generator(run.id),
            cost_usd=run.cost_usd,
            url=org.app_run_url(run.task_id, run.id),
        )


class OpenAIProxyChatCompletionResponse(BaseModel):
    id: str
    choices: list[OpenAIProxyChatCompletionChoice]
    created: int  # Unix timestamp
    model: str
    system_fingerprint: str | None = None
    object: Literal["chat.completion"] = "chat.completion"
    usage: OpenAIProxyCompletionUsage | None = None

    version_id: str = Field(description="The version id of the completion, WorkflowAI specific")
    metadata: dict[str, Any] | None = Field(description="Metadata about the completion, WorkflowAI specific")

    @classmethod
    def from_domain(
        cls,
        run: AgentRun,
        output_mapper: Callable[[AgentOutput], str | None],
        model: str,
        deprecated_function: bool,
        # feedback_generator should take a run id and return a feedback token
        feedback_generator: Callable[[str], str],
        org: PublicOrganizationData,
    ):
        return cls(
            id=f"{run.task_id}/{run.id}",
            choices=[
                OpenAIProxyChatCompletionChoice.from_domain(
                    run,
                    output_mapper,
                    deprecated_function,
                    feedback_generator,
                    org,
                ),
            ],
            created=int(run.created_at.timestamp()),
            model=model,
            usage=OpenAIProxyCompletionUsage.from_domain(run.llm_completions[-1]) if run.llm_completions else None,
            metadata=run.metadata,
            version_id=run.group.id,
        )


_FinishReason: TypeAlias = Literal["stop", "length", "tool_calls", "content_filter", "function_call"]


class OpenAIProxyChatCompletionChunkDelta(BaseModel):
    content: str | None
    function_call: OpenAIProxyFunctionCall | None  # Deprecated
    tool_calls: list[OpenAIProxyToolCall] | None
    role: Literal["user", "assistant", "system", "tool"] | None

    @classmethod
    def from_domain(
        cls,
        output: RunOutput,
        output_mapper: Callable[[AgentOutput], str | None],
        deprecated_function: bool,
        aggregate_content: bool | None,
    ):
        if not aggregate_content and not output.delta and not output.tool_call_requests:
            return None

        return cls(
            role="assistant",
            content=output_mapper(output.task_output) if aggregate_content else output.delta,
            function_call=OpenAIProxyFunctionCall.from_domain(output.tool_call_requests[0])
            if deprecated_function and output.tool_call_requests
            else None,
            tool_calls=[OpenAIProxyToolCall.from_domain(t) for t in output.tool_call_requests]
            if output.tool_call_requests and not deprecated_function
            else None,
        )


class OpenAIProxyChatCompletionChunkChoice(BaseModel):
    delta: OpenAIProxyChatCompletionChunkDelta
    index: int


class OpenAIProxyChatCompletionChunkChoiceFinal(OpenAIProxyChatCompletionChunkChoice, _ExtraChoiceAttributes):
    usage: OpenAIProxyCompletionUsage | None
    finish_reason: _FinishReason | None

    @classmethod
    def _possible_finish_reason(cls, run: AgentRun, deprecated_function: bool) -> _FinishReason | None:
        """Compute the finish reason for a run"""
        if run.tool_call_requests:
            return "tool_calls" if deprecated_function else "function_call"
        return "stop"

    @classmethod
    def _build_delta(
        cls,
        run: AgentRun,
        output_mapper: Callable[[AgentOutput], str | None],
        deprecated_function: bool,
        aggregate_content: bool | None,
    ):
        """Build the final delta based on a run. The final delta contains the full output of the run if the run
        is from cache since there was no previous delta. Otherwise the final delta is empty."""
        if run.from_cache or aggregate_content:
            if chunk := OpenAIProxyChatCompletionChunkDelta.from_domain(
                RunOutput.from_run(run),
                output_mapper,
                deprecated_function,
                True,
            ):
                return chunk
        # Otherwise the final chunk is always empty
        return OpenAIProxyChatCompletionChunkDelta(
            role="assistant",
            content=None,
            function_call=None,
            tool_calls=None,
        )

    @classmethod
    def from_run(
        cls,
        run: AgentRun,
        output_mapper: Callable[[AgentOutput], str | None],
        deprecated_function: bool,
        feedback_generator: Callable[[str], str],
        aggregate_content: bool | None,
        org: PublicOrganizationData,
    ):
        """Compute the final choice chunk from a run"""

        usage = OpenAIProxyCompletionUsage.from_domain(run.llm_completions[-1]) if run.llm_completions else None

        return cls(
            delta=cls._build_delta(run, output_mapper, deprecated_function, aggregate_content),
            finish_reason=cls._possible_finish_reason(run, deprecated_function),
            index=0,
            usage=usage,
            cost_usd=run.cost_usd,
            duration_seconds=run.duration_seconds,
            feedback_token=feedback_generator(run.id),
            url=org.app_run_url(run.task_id, run.id),
        )


class OpenAIProxyChatCompletionChunk(BaseModel):
    id: str
    choices: list[OpenAIProxyChatCompletionChunkChoice | OpenAIProxyChatCompletionChunkChoiceFinal]
    created: int
    model: str
    system_fingerprint: str | None = None
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    usage: OpenAIProxyCompletionUsage | None = None

    # TODO:
    # cost_usd: float | None = Field(description="The cost of the completion in USD, WorkflowAI specific")
    # duration_seconds: float | None = Field(description="The duration of the completion in seconds, WorkflowAI specific")
    # metadata: dict[str, Any] | None = Field(description="Metadata about the completion, WorkflowAI specific")

    @classmethod
    def from_domain(
        cls,
        id: str,
        output: RunOutput,
        output_mapper: Callable[[AgentOutput], str | None],
        model: str,
        deprecated_function: bool,
        aggregate_content: bool | None,
    ):
        chunk_delta = OpenAIProxyChatCompletionChunkDelta.from_domain(
            output,
            output_mapper,
            deprecated_function,
            aggregate_content,
        )
        if not chunk_delta:
            return None
        return cls(
            id=id,
            created=int(time.time()),
            model=model,
            choices=[OpenAIProxyChatCompletionChunkChoice(delta=chunk_delta, index=0)],
        )

    @classmethod
    def stream_serializer(
        cls,
        agent_id: str,
        model: str,
        deprecated_function: bool,
        aggregate_content: bool | None,
        output_mapper: Callable[[AgentOutput], str | None],
    ):
        def _serializer(id: str, output: RunOutput):
            return cls.from_domain(
                f"{agent_id}/{id}",
                output,
                output_mapper,
                model=model,
                deprecated_function=deprecated_function,
                aggregate_content=aggregate_content,
            )

        return _serializer

    @classmethod
    def serializer(
        cls,
        model: str,
        deprecated_function: bool,
        output_mapper: Callable[[AgentOutput], str | None],
        feedback_generator: Callable[[str], str],
        aggregate_content: bool | None,
        org: PublicOrganizationData,
    ):
        # Builds the final chunk containing the usage and feedback token
        def _serializer(run: AgentRun):
            choice = OpenAIProxyChatCompletionChunkChoiceFinal.from_run(
                run,
                output_mapper,
                deprecated_function,
                feedback_generator,
                aggregate_content,
                org,
            )
            if not choice:
                # This is mostly for typing reasons, it should never happen
                _logger.warning("No final choice found for run", extra={"run_id": run.id})
                return None

            return cls(
                id=f"{run.task_id}/{run.id}",
                created=int(time.time()),
                model=model,
                choices=[choice],
            )

        return _serializer
