import logging
from collections.abc import AsyncIterator
from typing import Any

from pydantic import ValidationError
from workflowai import Run

from core.agents.custom_tool.custom_tool_creation_agent import (
    CustomToolCreationAgentInput,
    stream_custom_tool_creation_agent,
)
from core.agents.custom_tool.custom_tool_example_input_agent import (
    ToolInputExampleAgentInput,
    tool_input_example_agent,
)
from core.agents.custom_tool.custom_tool_example_output_agent import (
    ToolOuptutExampleAgentInput,
    ToolOutputExampleAgentOutput,
    tool_output_example_agent,
)
from core.domain.fields.custom_tool_creation_chat_message import CustomToolCreationChatMessage

_logger = logging.getLogger(__name__)


class ToolOutputExampleAgentOutputWithRunId(ToolOutputExampleAgentOutput):
    run_id: str


class CustomToolService:
    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    async def stream_creation_agent(
        cls,
        messages: list[CustomToolCreationChatMessage],
    ) -> AsyncIterator[CustomToolCreationChatMessage]:
        async for output in stream_custom_tool_creation_agent(
            CustomToolCreationAgentInput(
                chat_messages=messages,
            ),
        ):
            if answer := output.answer:
                if type(answer) is dict:  # pyright: ignore[reportUnnecessaryComparison]
                    try:
                        # answer is sometimes returns as a dict, SDK bug ?
                        yield CustomToolCreationChatMessage.model_validate(answer)
                    except ValidationError as e:
                        _logger.error("Error validating ToolCreationChatMessage answer", exc_info=e)
                else:
                    yield answer

    @classmethod
    async def stream_example_input(
        cls,
        tool_name: str,
        tool_description: str,
        tool_schema: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        async for output in tool_input_example_agent(
            ToolInputExampleAgentInput(
                tool_name=tool_name,
                tool_description=tool_description,
                tool_schema=tool_schema,
            ),
        ):
            if output.example_tool_input:
                yield output.example_tool_input

    @classmethod
    async def stream_example_output(
        cls,
        tool_name: str,
        tool_description: str,
        tool_input: dict[str, Any] | None,
        previous_run_id: str | None,
        new_user_message: str | None,
    ) -> AsyncIterator[ToolOutputExampleAgentOutputWithRunId]:
        if previous_run_id and new_user_message:
            # TODO: fix typing in SDK to get Run[AgentOutput] instead of None
            follow_up_output: Run[ToolOutputExampleAgentOutput] = await tool_output_example_agent.reply(  # type: ignore
                previous_run_id,
                new_user_message,
            )
            yield ToolOutputExampleAgentOutputWithRunId(
                run_id=follow_up_output.id,
                **follow_up_output.output.model_dump(),
            )
        else:
            async for first_output in tool_output_example_agent.stream(
                ToolOuptutExampleAgentInput(
                    tool_name=tool_name,
                    tool_description=tool_description,
                    tool_input=tool_input,
                ),
            ):
                yield ToolOutputExampleAgentOutputWithRunId(
                    run_id=first_output.id,
                    **first_output.output.model_dump(),
                )
