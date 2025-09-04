import logging
from copy import deepcopy
from enum import StrEnum
from typing import Any, Literal, cast

import httpx
from pydantic import BaseModel, Field

from api.services.runs._stored_message import StoredMessages
from api.services.runs.runs_service import RunsService
from core.domain.agent_run import AgentRun
from core.domain.consts import ANOTHERAI_API_URL
from core.domain.error_response import ErrorResponse
from core.domain.errors import InternalError
from core.domain.fields.file import File
from core.domain.llm_completion import LLMCompletion
from core.domain.message import Message, MessageContent
from core.domain.reasoning_effort import ReasoningEffort
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties, ToolChoice, ToolChoiceFunction
from core.domain.task_io import RawJSONMessageSchema, RawStringMessageSchema, SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tool import Tool
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.providers.base.models import (
    AudioContentDict,
    DocumentContentDict,
    ImageContentDict,
    StandardMessage,
    TextContentDict,
    ToolCallRequestDict,
    ToolCallResultDict,
)
from core.runners.workflowai.utils import extract_files, remove_keys_from_input
from core.storage.backend_storage import BackendStorage
from core.tools import ToolKind
from core.utils.coroutines import capture_errors
from core.utils.templates import TemplateManager

_logger = logging.getLogger(__name__)


class _ToolCallRequest(BaseModel):
    id: str = Field(description="The id of the tool call request")
    name: str = Field(description="The name of the tool")
    arguments: dict[str, Any] = Field(description="The arguments of the tool")

    @classmethod
    def from_domain(cls, tool_call_request: ToolCallRequestWithID):
        return cls(
            id=tool_call_request.id,
            name=tool_call_request.tool_name,
            arguments=tool_call_request.tool_input_dict,
        )

    @classmethod
    def from_standard(cls, tool_call_request: ToolCallRequestDict):
        return cls(
            id=tool_call_request["id"] or "",
            name=tool_call_request["tool_name"],
            arguments=tool_call_request["tool_input_dict"] or {},
        )


class _ToolCallResult(BaseModel):
    id: str = Field(description="The id of the tool call result")
    output: Any | None = Field(description="The output of the tool")
    error: str | None = Field(description="The error of the tool")

    @classmethod
    def from_domain(cls, tool_call_result: ToolCall):
        return cls(
            id=tool_call_result.id,
            output=tool_call_result.result,
            error=tool_call_result.error,
        )

    @classmethod
    def from_standard(cls, tool_call_result: ToolCallResultDict):
        return cls(
            id=tool_call_result["id"] or "",
            output=tool_call_result["result"],
            error=tool_call_result["error"],
        )


class _Message(BaseModel):
    role: Literal["system", "user", "assistant", "developer", "tool"]

    class Content(BaseModel):
        """A content of a message. Only a single field can be present at a time."""

        text: str | None = None
        object: dict[str, Any] | list[Any] | None = None
        image_url: str | None = None
        audio_url: str | None = None
        tool_call_request: _ToolCallRequest | None = None  # function_call in response API
        tool_call_result: _ToolCallResult | None = None  # function_call_output in response API
        reasoning: str | None = None

        @classmethod
        def from_domain(cls, content: MessageContent):
            if content.file:
                return cls.from_file(content.file)
            return cls(
                text=content.text,
                tool_call_request=_ToolCallRequest.from_domain(content.tool_call_request)
                if content.tool_call_request
                else None,
                tool_call_result=_ToolCallResult.from_domain(content.tool_call_result)
                if content.tool_call_result
                else None,
            )

        @classmethod
        def from_file(cls, file: File):
            if file.is_image:
                return cls(image_url=file.url)
            if file.is_audio:
                return cls(audio_url=file.url)
            if file.is_pdf:
                return cls(image_url=file.url)
            raise InternalError("Unknown file type", capture=True)

        @classmethod
        def from_standard(
            cls,
            content: TextContentDict
            | ImageContentDict
            | AudioContentDict
            | DocumentContentDict
            | ToolCallRequestDict
            | ToolCallResultDict,
        ):
            match content["type"]:
                case "text":
                    return cls(text=content["text"])
                case "image_url":
                    return cls(image_url=content["image_url"]["url"])
                case "audio_url":
                    return cls(audio_url=content["audio_url"]["url"])
                case "document_url":
                    return cls(image_url=content["source"]["url"])
                case "tool_call_request":
                    return cls(tool_call_request=_ToolCallRequest.from_standard(content))
                case "tool_call_result":
                    return cls(tool_call_result=_ToolCallResult.from_standard(content))
            raise InternalError("Unknown content type", capture=True)

    # Never a list[Any] to avoid conflicts with the list[Content]
    content: list[Content] | str | dict[str, Any]

    @classmethod
    def from_domain(cls, message: Message):
        return cls(
            role=message.role,
            content=[cls.Content.from_domain(c) for c in message.content],
        )

    @classmethod
    def from_standard(cls, message: StandardMessage):
        content = message["content"]
        return cls(
            role=message.get("role") or "user",
            content=content if isinstance(content, str) else [cls.Content.from_standard(c) for c in content],
        )


class _OutputSchema(BaseModel):
    id: str = Field(description="The id of the output schema. Auto generated from the json schema", default="")
    json_schema: dict[str, Any] = Field(description="The JSON schema of the output")

    @classmethod
    def from_domain(cls, task_io: SerializableTaskIO):
        if task_io == RawStringMessageSchema:
            return None
        if task_io == RawJSONMessageSchema:
            return _OutputSchema(json_schema={})
        return cls(
            id="",
            json_schema=task_io.json_schema,
        )


class _Tool(BaseModel):
    name: str = Field(description="The name of the tool")
    description: str | None = Field(
        default=None,
        description="The description of the tool",
    )
    input_schema: dict[str, Any] = Field(description="The input class of the tool")

    @classmethod
    def from_domain(cls, tool: Tool | ToolKind):
        if isinstance(tool, ToolKind):
            return cls(
                name=tool.value,
                input_schema={},
            )
        return cls(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
        )


class _ToolChoiceFunction(BaseModel):
    name: str

    @classmethod
    def from_domain(cls, tool_choice: ToolChoiceFunction):
        return cls(
            name=tool_choice.name,
        )


type _ToolChoice = Literal["auto", "none", "required"] | _ToolChoiceFunction


def _tool_choice_from_domain(tool_choice: ToolChoice | None):
    if not tool_choice:
        return None
    if isinstance(tool_choice, ToolChoiceFunction):
        return _ToolChoiceFunction.from_domain(tool_choice)
    return tool_choice


class _ReasoningEffort(StrEnum):
    DISABLED = "disabled"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @classmethod
    def from_domain(cls, reasoning_effort: ReasoningEffort):
        return cls(reasoning_effort.value)


class _Version(BaseModel):
    id: str = Field(description="The id of the version. Auto generated.", default="")
    model: str
    temperature: float | None = None
    top_p: float | None = None
    tools: list[_Tool] | None = Field(
        default=None,
        description="A list of tools that the model can use. If empty, no tools are used.",
    )

    prompt: list[_Message] | None = Field(
        default=None,
        description="A list of messages that will begin the message list sent to the model"
        "The message content can be a Jinja2 template, in which case the input_variables_schema will be set"
        "to describe the variables used and the prompt will be rendered with the input variables before"
        "being sent to the model",
    )

    input_variables_schema: dict[str, Any] | None = Field(
        default=None,
        description="A JSON schema for the variables used to template the instructions during the inference."
        "Auto generated from the prompt if the prompt is a Jinja2 template",
    )
    output_schema: _OutputSchema | None = Field(
        default=None,
        description="A JSON schema for the output of the model, aka the schema in the response format",
    )

    max_output_tokens: int | None = Field(
        default=None,
        description="The maximum number of tokens to generate in the prompt",
    )

    tool_choice: _ToolChoice | None = None

    presence_penalty: float | None = None

    frequency_penalty: float | None = None

    parallel_tool_calls: bool | None = None

    reasoning_effort: _ReasoningEffort | None = None

    reasoning_budget: int | None = None

    use_structured_generation: bool | None = None

    provider: str | None = None

    @classmethod
    def from_domain(
        cls,
        group: TaskGroup,
        task_variant: SerializableTaskVariant,
        prompt: list[_Message] | None,
        variables_schema: dict[str, Any] | None,
    ):
        return cls(
            id="",
            model=group.properties.model or "",
            temperature=group.properties.temperature,
            tools=[_Tool.from_domain(t) for t in group.properties.enabled_tools]
            if group.properties.enabled_tools
            else None,
            prompt=prompt,
            input_variables_schema=variables_schema,
            output_schema=_OutputSchema.from_domain(task_variant.output_schema),
            max_output_tokens=group.properties.max_tokens,
            tool_choice=_tool_choice_from_domain(group.properties.tool_choice),
            presence_penalty=group.properties.presence_penalty,
            frequency_penalty=group.properties.frequency_penalty,
            parallel_tool_calls=group.properties.parallel_tool_calls,
            reasoning_effort=_ReasoningEffort.from_domain(group.properties.reasoning_effort)
            if group.properties.reasoning_effort
            else None,
            reasoning_budget=group.properties.reasoning_budget,
            provider=group.properties.provider,
        )


class _Error(BaseModel):
    error: str

    @classmethod
    def from_domain(cls, error: ErrorResponse.Error):
        return cls(
            error=error.message,
        )


class _Input(BaseModel):
    id: str = Field(
        default="",
        description="The id of the input. Auto generated.",
    )
    messages: list[_Message] | None = Field(
        default=None,
        description="Optional, messages part of the conversation appended to the rendered (if needed) prompt",
    )
    variables: dict[str, Any] | None = Field(
        default=None,
        description="Optional, variables used to template the prompt when the prompt is a template",
    )

    @classmethod
    def from_raw_input(cls, input: Any):
        validated = StoredMessages.model_validate(input)
        return cls(
            messages=[_Message.from_domain(m) for m in validated.messages] if validated.messages else None,
            variables=validated.model_extra or None,
        )


class _Output(BaseModel):
    messages: list[_Message] | None = Field(
        default=None,
        description="The messages sent to the model. This is the messages that are returned to the user. None if the inference failed.",
    )
    error: _Error | None = Field(
        default=None,
        description="The error that occurred during the inference. None if the inference succeeded.",
    )

    @classmethod
    def from_domain(cls, agent_run: AgentRun):
        contents: list[_Message.Content] = []
        if isinstance(agent_run.task_output, (dict, list)):
            contents.append(_Message.Content(object=agent_run.task_output))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        elif isinstance(agent_run.task_output, str):
            contents.append(_Message.Content(text=agent_run.task_output))

        if agent_run.tool_call_requests:
            contents.extend(
                _Message.Content(tool_call_request=_ToolCallRequest.from_domain(tool_call_request))
                for tool_call_request in agent_run.tool_call_requests
            )

        return cls(
            messages=[_Message(role="assistant", content=contents)] if contents else None,
            error=_Error.from_domain(agent_run.error) if agent_run.error else None,
        )


class _Completion(BaseModel):
    id: str = Field(
        default="",
        description="The id of the completion. Must be a UUID7. Auto generated if not provided.",
    )
    agent_id: str

    version: _Version = Field(
        description="The version of the model used for the inference.",
    )

    conversation_id: str | None = Field(
        default=None,
        description="The unique identifier of the conversation that the completion is associated with, if any. "
        "None if the completion is not part of a conversation.",
    )

    input: _Input = Field(
        description="The input of the inference, combining the appended messages and the variables",
    )

    output: _Output = Field(description="The output of the inference")

    messages: list[_Message] = Field(
        default_factory=list,
        description="The full list of message sent to the model, includes the messages in the version prompt "
        "(rendered with the input variables if needed), the appended messages and the messages returned by the model",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Metadata associated with the completion. Can be used to store additional information about the completion.",
    )

    cost_usd: float = Field(description="The cost of the inference in USD.")
    duration_seconds: float | None = Field(
        description="The duration of the inference in seconds.",
    )

    @classmethod
    def from_domain(
        cls,
        run: AgentRun,
        task_variant: SerializableTaskVariant,
        final_input: _Input,
        prompt: list[_Message] | None,
        variables_schema: dict[str, Any] | None,
    ):
        return cls(
            id=run.id,
            agent_id=run.task_id,
            version=_Version.from_domain(
                run.group,
                task_variant,
                prompt=prompt,
                variables_schema=variables_schema,
            ),
            input=final_input,
            output=_Output.from_domain(run),
            cost_usd=run.cost_usd or 0,
            duration_seconds=run.duration_seconds,
            messages=_last_completion_to_messages(run.llm_completions),
        )


def _last_completion_to_messages(completions: list[LLMCompletion] | None) -> list[_Message]:
    if not completions:
        return []

    last_completion = completions[-1]
    last_messages = cast(list[StandardMessage], last_completion.messages)
    with capture_errors(_logger, "Failed to convert last completion to messages"):
        return [_Message.from_standard(m) for m in last_messages]
    return []


class AnotherAIService:
    template_manager: TemplateManager = TemplateManager()

    @classmethod
    def is_enabled(cls) -> bool:
        return ANOTHERAI_API_URL is not None

    def __init__(self, storage: BackendStorage, runs_service: RunsService):
        self._storage = storage
        self._runs_service = runs_service

    @classmethod
    def _extract_files(cls, json_schema: dict[str, Any], input: dict[str, Any]) -> list[File]:
        # Remove all files from the input and move to messages
        # Update the input variable schema to match
        _, _, files = extract_files(json_schema, input)
        # Files are handled as separate messages in AnotherAI
        # So they need to be remove from both the input and the input schema
        remove_keys_from_input(json_schema, input, {str(file.key_path[0]) for file in files})
        # We will add files as separate input messages at the end
        return cast(list[File], files)

    @classmethod
    def _user_message_content(cls, input_keys: set[str]):
        return "\n\n".join([f"{key}: {{{{{key}}}}}" for key in input_keys])

    @classmethod
    async def _prompt_from_instructions(cls, instructions: str, input: dict[str, Any]):
        # Instructions go into the first system message
        prompt: list[_Message] = []
        prompt.append(_Message(role="system", content=instructions))
        _, extracted_keys = await cls.template_manager.render_template(instructions, input)
        # Extracted keys will be handled by the system message template
        # We remove them from the input copy to see if there is anything left

        remaining_keys = set(input) - extracted_keys
        if remaining_keys:
            # that means there are still some keys that need to be added as a user message
            prompt.append(_Message(role="user", content=cls._user_message_content(remaining_keys)))
        return prompt

    async def _split_input_and_prompt(
        self,
        task_input: Any,
        task_input_schema: SerializableTaskIO,
        version_properties: TaskGroupProperties,
    ) -> tuple[_Input, list[_Message] | None, dict[str, Any] | None]:
        if version_properties.messages or task_input_schema.uses_messages:
            # In this case we can use everything as is.
            # TODO: there might be some edge cases with files since we used to perform
            # some magic with inlining. Not sure it was ever used so not tackling for now
            if task_input_schema.has_files:
                raise NotImplementedError("Files are not supported in this case")
            return (
                _Input.from_raw_input(task_input),
                [_Message.from_domain(m) for m in version_properties.messages or []] or None,
                task_input_schema.json_schema or None,
            )

        # Here we are dealing with a "pure" WorkflowAI agent

        json_schema = deepcopy(task_input_schema.json_schema)
        # Files need to be removed from the original input
        files = self._extract_files(json_schema, task_input) if task_input_schema.has_files else []
        # Now we need to extract templated keys from the instructions
        prompt = (
            await self._prompt_from_instructions(version_properties.instructions, task_input)
            if version_properties.instructions
            else None
        )

        final_input = _Input(variables=task_input or None)
        if files:
            final_input.messages = [_Message(role="user", content=[_Message.Content.from_file(f) for f in files])]
        if not json_schema.get("properties"):
            json_schema = None
        return final_input, prompt, json_schema

    async def _convert_run(self, agent_run: AgentRun, task_variant: SerializableTaskVariant):
        # Replace completions dict with the OpenAI dict
        self._runs_service._sanitize_run(agent_run)  # pyright: ignore[reportPrivateUsage]

        final_input, prompt, json_schema = await self._split_input_and_prompt(
            task_input=agent_run.task_input,
            task_input_schema=task_variant.input_schema,
            version_properties=agent_run.group.properties,
        )

        return _Completion.from_domain(
            run=agent_run,
            task_variant=task_variant,
            final_input=final_input,
            prompt=prompt,
            variables_schema=json_schema,
        )

    async def import_run(self, agent_run: AgentRun):
        if not ANOTHERAI_API_URL:
            raise InternalError("AnotherAI is not enabled", fatal=True)

        tenant = await self._storage.organizations.get_organization()
        if not tenant.anotherai_api_key:
            return
        if not agent_run.group.properties.task_variant_id:
            raise InternalError("Task variant not found", fatal=True)
        task_variant = await self._storage.task_version_resource_by_id(
            task_id=agent_run.task_id,
            version_id=agent_run.group.properties.task_variant_id,
        )
        if not task_variant:
            raise InternalError("Task variant not found", fatal=True)

        # Replace completions dict with the OpenAI dict
        completion = await self._convert_run(agent_run, task_variant)
        async with httpx.AsyncClient(
            base_url=ANOTHERAI_API_URL,
            headers={"Authorization": f"Bearer {tenant.anotherai_api_key}"},
        ) as client:
            response = await client.post(
                "/v1/completions",
                json=completion.model_dump(exclude_none=True),
            )
        response.raise_for_status()
