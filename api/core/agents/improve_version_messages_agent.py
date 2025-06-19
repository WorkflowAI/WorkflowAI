import json
import logging
import os
from typing import Any, AsyncIterator, Literal, NamedTuple

import workflowai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from core.domain.message import Message

_logger = logging.getLogger(__name__)


class ImproveVersionMessagesInput(NamedTuple):
    initial_messages: list[dict[str, Any]]

    class Run(BaseModel):
        input: str
        output: str

    run: Run | None
    improvement_instructions: str | None


class ImproveVersionMessagesOutput(BaseModel):
    class Message(BaseModel):
        role: Literal["system", "user", "assistant"]
        content: str

    improved_messages: list[Message]
    changelog: list[str] | None = None


class ImproveVersionMessagesResponse(BaseModel):
    improved_messages: list[Message]
    feedback_token: str | None
    changelog: list[str] | None = None


class ImproveVersionMessagesError(Exception):
    """Custom exception for improve version messages errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.context = context or {}


async def improve_version_messages_agent(
    input: ImproveVersionMessagesInput,
) -> AsyncIterator[ImproveVersionMessagesResponse]:
    """
    Improved version with better error handling and state management.
    """
    # Validate input early
    if not input.initial_messages:
        _logger.warning("Empty initial_messages provided to improve_version_messages_agent")
        raise ImproveVersionMessagesError(
            "Cannot improve empty messages",
            {"input": input._asdict()},
        )

    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )

    feedback_token: str | None = None
    yielded_response: ImproveVersionMessagesResponse | None = None
    chunk_count = 0
    error_count = 0
    max_errors = 5  # Limit consecutive errors

    try:
        async with client.beta.chat.completions.stream(
            model=f"improve-version-messages/{workflowai.Model.GEMINI_2_0_FLASH_001.value}",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at improving AI agent input messages. Given initial messages and improvement instructions, return improved messages.\n\nthe improvement instructions are: {{improvement_instructions}}. You must output a concise changelog of the changes you made to the message in the 'changelog' field. Note that changelog should be a list of strings, with each element being an atomic change.",
                },
                {
                    "role": "user",
                    "content": """The messages to improve are: {{initial_messages}}
                    {% if run %}Use this run as additional context on how to improve the messages: {{run}}{% endif %}
                    """,
                },
            ],
            response_format=ImproveVersionMessagesOutput,
            extra_body={
                "input": {
                    "initial_messages": input.initial_messages,
                    "run": input.run.model_dump(mode="json") if input.run else "",
                    "improvement_instructions": input.improvement_instructions,
                },
            },
            temperature=0.0,
        ) as response:
            chunk = None
            agg = ""
            last_valid_response: ImproveVersionMessagesResponse | None = None

            async for chunk in response:
                chunk_count += 1

                try:
                    # Safely extract feedback token
                    feedback_token = getattr(chunk, "feedback_token", None)

                    # Check for valid chunk type and attributes
                    if not (hasattr(chunk, "type") and chunk.type == "content.delta" and hasattr(chunk, "delta")):
                        continue

                    # First, try parsing the chunk.parsed if available
                    if chunk.parsed and isinstance(chunk.parsed, dict):
                        try:
                            parsed_output = ImproveVersionMessagesOutput.model_validate(chunk.parsed)
                            yielded_response = _create_response_from_output(parsed_output, feedback_token)
                            last_valid_response = yielded_response
                            yield yielded_response
                            error_count = 0  # Reset error count on success
                            continue
                        except ValidationError as e:
                            _logger.warning(
                                "Validation error parsing chunk.parsed",
                                extra={
                                    "error": str(e),
                                    "chunk_parsed": chunk.parsed,
                                    "chunk_count": chunk_count,
                                },
                            )
                            # Continue to try delta parsing

                    # Fallback: accumulate delta and parse manually
                    if chunk.delta:
                        try:
                            # Safely append delta
                            delta_content = str(chunk.delta) if chunk.delta else ""
                            agg += delta_content

                            # Limit accumulated content to prevent memory issues
                            if len(agg) > 50000:  # 50KB limit
                                _logger.warning(
                                    "Accumulated content too large, truncating",
                                    extra={"agg_length": len(agg), "chunk_count": chunk_count},
                                )
                                agg = agg[-25000:]  # Keep last 25KB

                            # Try to parse accumulated JSON
                            parsed_output = ImproveVersionMessagesOutput.model_validate(json.loads(agg))
                            yielded_response = _create_response_from_output(parsed_output, feedback_token)
                            last_valid_response = yielded_response
                            yield yielded_response
                            error_count = 0  # Reset error count on success

                        except (json.JSONDecodeError, ValidationError) as e:
                            error_count += 1
                            if error_count >= max_errors:
                                _logger.error(
                                    "Too many consecutive parsing errors, aborting",
                                    extra={
                                        "error_count": error_count,
                                        "last_error": str(e),
                                        "chunk_count": chunk_count,
                                        "agg_preview": agg[:500] if agg else "",
                                    },
                                )
                                break
                            continue

                except Exception as e:
                    error_count += 1
                    _logger.exception(
                        "Unexpected error processing chunk",
                        extra={
                            "error": str(e),
                            "chunk_count": chunk_count,
                            "error_count": error_count,
                        },
                    )

                    if error_count >= max_errors:
                        _logger.error("Too many errors, aborting stream")
                        break
                    continue

            # Final validation
            if yielded_response is None and last_valid_response is not None:
                # Use the last valid response if we have one
                yield last_valid_response
            elif yielded_response is None:
                # No valid response received - this is the InvalidStateError scenario
                error_context = {
                    "input": input._asdict(),
                    "chunk_count": chunk_count,
                    "error_count": error_count,
                    "last_chunk": chunk.model_dump(mode="json") if chunk else None,
                    "agg_length": len(agg) if agg else 0,
                    "agg_preview": agg[:500] if agg else "",
                }

                _logger.error(
                    "No valid response yielded from improve_version_messages_agent",
                    extra=error_context,
                )

                raise ImproveVersionMessagesError(
                    "Failed to generate valid response from improve_version_messages_agent",
                    error_context,
                )

    except Exception as e:
        if isinstance(e, ImproveVersionMessagesError):
            raise

        # Wrap unexpected exceptions
        error_context = {
            "input": input._asdict(),
            "error_type": type(e).__name__,
            "error_message": str(e),
        }

        _logger.exception(
            "Unexpected error in improve_version_messages_agent",
            extra=error_context,
        )

        raise ImproveVersionMessagesError(
            f"Unexpected error in improve_version_messages_agent: {str(e)}",
            error_context,
        ) from e


def _create_response_from_output(
    output: ImproveVersionMessagesOutput,
    feedback_token: str | None,
) -> ImproveVersionMessagesResponse:
    """Helper function to create response from output with validation."""
    try:
        # Validate messages before creating response
        if not output.improved_messages:
            raise ValidationError("No improved messages in output")

        messages = []
        for message in output.improved_messages:
            # Validate message content
            if not message.content or not message.content.strip():
                _logger.warning("Empty message content found, skipping")
                continue

            if message.role not in ["system", "user", "assistant"]:
                _logger.warning(f"Invalid message role: {message.role}, defaulting to 'user'")
                role = "user"
            else:
                role = message.role

            messages.append(Message.with_text(message.content.strip(), role))

        if not messages:
            raise ValidationError("No valid messages after processing")

        return ImproveVersionMessagesResponse(
            improved_messages=messages,
            feedback_token=feedback_token,
            changelog=output.changelog or [],
        )

    except Exception as e:
        _logger.error(
            "Error creating response from output",
            extra={
                "error": str(e),
                "output": output.model_dump(mode="json") if output else None,
            },
        )
        raise
