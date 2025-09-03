from enum import StrEnum
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from api.services.runs._stored_message import StoredMessages
from core.domain.agent_run import AgentRun
from core.domain.error_response import ErrorResponse
from core.domain.message import Message, MessageContent
from core.domain.reasoning_effort import ReasoningEffort
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import ToolChoice, ToolChoiceFunction
from core.domain.task_io import RawJSONMessageSchema, RawStringMessageSchema, SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tool import Tool
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.tools import ToolKind


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
            return cls(
                text=content.text,
                image_url=content.file.url if content.file else None,
                tool_call_request=_ToolCallRequest.from_domain(content.tool_call_request)
                if content.tool_call_request
                else None,
                tool_call_result=_ToolCallResult.from_domain(content.tool_call_result)
                if content.tool_call_result
                else None,
            )

    # Never a list[Any] to avoid conflicts with the list[Content]
    content: list[Content] | str | dict[str, Any]

    @classmethod
    def from_domain(cls, message: Message):
        return cls(
            role=message.role,
            content=[cls.Content.from_domain(c) for c in message.content],
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
    def from_domain(cls, group: TaskGroup, task_variant: SerializableTaskVariant):
        return cls(
            id="",
            model=group.properties.model or "",
            temperature=group.properties.temperature,
            tools=[_Tool.from_domain(t) for t in group.properties.enabled_tools]
            if group.properties.enabled_tools
            else None,
            prompt=[_Message.from_domain(m) for m in group.properties.messages or []],
            input_variables_schema=task_variant.input_schema.json_schema,
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
    def from_domain(cls, run: AgentRun, task_variant: SerializableTaskVariant):
        return cls(
            id=run.id,
            agent_id=run.task_id,
            version=_Version.from_domain(run.group, task_variant),
            input=_Input.from_raw_input(run.task_input),
            output=_Output.from_domain(run),
            cost_usd=run.cost_usd or 0,
            duration_seconds=run.duration_seconds,
            # TODO: handle completions
            messages=[],
        )


async def post_run_to_anotherai(url: str, run: AgentRun, task_variant: SerializableTaskVariant, api_key: str):
    completion = _Completion.from_domain(run, task_variant)
    async with httpx.AsyncClient(base_url=url, headers={"Authorization": f"Bearer {api_key}"}) as client:
        response = await client.post(
            "/v1/completions",
            json=completion.model_dump(exclude_none=True),
        )
        response.raise_for_status()
