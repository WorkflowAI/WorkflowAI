import pytest

from core.domain.fields.file import File
from core.domain.message import MessageDeprecated
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.providers.anthropic.anthropic_domain import (
    AnthropicMessage,
    CompletionChunk,
    CompletionRequest,
    DocumentContent,
    ErrorDetails,
    FileSource,
    ImageContent,
    SignatureDelta,
    TextContent,
    ThinkingContent,
    ThinkingDelta,
    ToolResultContent,
    ToolUseContent,
)
from core.providers.base.provider_error import (
    MaxTokensExceededError,
    ProviderBadRequestError,
    ProviderError,
    ProviderInternalError,
    UnknownProviderError,
)


def test_anthropic_message_from_domain_user() -> None:
    domain_message = MessageDeprecated(
        role=MessageDeprecated.Role.USER,
        content="Hello, how are you?",
    )

    anthropic_message = AnthropicMessage.from_domain(domain_message)

    assert anthropic_message.role == "user"
    assert anthropic_message.content[0].type == "text"
    assert anthropic_message.content[0].text == "Hello, how are you?"


def test_anthropic_message_from_domain_assistant() -> None:
    domain_message = MessageDeprecated(
        role=MessageDeprecated.Role.ASSISTANT,
        content="I'm doing well, thank you!",
    )

    anthropic_message = AnthropicMessage.from_domain(domain_message)

    assert anthropic_message.role == "assistant"
    assert anthropic_message.content[0].type == "text"
    assert anthropic_message.content[0].text == "I'm doing well, thank you!"


def test_anthropic_message_to_standard_with_content_array() -> None:
    anthropic_message = AnthropicMessage(
        role="user",
        content=[
            TextContent(
                type="text",
                text="Which model has the highest human preference win rates?",
            ),
        ],
    )

    standard_message = anthropic_message.to_standard()

    assert standard_message == {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "Which model has the highest human preference win rates?",
            },
        ],
    }


def test_anthropic_message_to_standard_with_document_url() -> None:
    anthropic_message = AnthropicMessage(
        role="user",
        content=[
            DocumentContent(
                type="document",
                source=FileSource(
                    type="base64",
                    media_type="application/pdf",
                    data="bla",
                ),
            ),
        ],
    )

    standard_message = anthropic_message.to_standard()

    assert standard_message == {
        "role": "user",
        "content": [{"type": "document_url", "source": {"url": "data:application/pdf;base64,bla"}}],
    }


def test_anthropic_message_to_standard_with_image_file() -> None:
    anthropic_message = AnthropicMessage(
        role="user",
        content=[ImageContent(type="image", source=FileSource(type="base64", media_type="image/png", data="bla"))],
    )

    standard_message = anthropic_message.to_standard()

    assert standard_message == {
        "role": "user",
        "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,bla"}}],
    }


def test_anthropic_message_from_domain_text_before_files() -> None:
    message = MessageDeprecated(
        role=MessageDeprecated.Role.USER,
        content="Hello world",
        files=[File(data="test_data", content_type="image/png")],
    )

    anthropic_message = AnthropicMessage.from_domain(message)
    assert len(anthropic_message.content) == 2
    assert isinstance(anthropic_message.content[0], TextContent)
    assert anthropic_message.content[0].text == "Hello world"
    assert isinstance(anthropic_message.content[1], ImageContent)


def test_anthropic_message_from_domain_with_tool_call_requests() -> None:
    message = MessageDeprecated(
        role=MessageDeprecated.Role.ASSISTANT,
        content="Let me check the weather for you.",
        tool_call_requests=[
            ToolCallRequestWithID(
                id="weather_1",
                tool_name="WeatherCheckTask",
                tool_input_dict={"location": {"latitude": 48.8566, "longitude": 2.3522}},
            ),
        ],
    )

    anthropic_message = AnthropicMessage.from_domain(message)
    assert anthropic_message == AnthropicMessage(
        role="assistant",
        content=[
            TextContent(type="text", text="Let me check the weather for you."),
            ToolUseContent(
                type="tool_use",
                id="weather_1",
                name="WeatherCheckTask",
                input={"location": {"latitude": 48.8566, "longitude": 2.3522}},
            ),
        ],
    )


def test_anthropic_message_from_domain_with_tool_call_results() -> None:
    message = MessageDeprecated(
        role=MessageDeprecated.Role.USER,
        content="Here's what I found:",
        tool_call_results=[
            ToolCall(
                id="weather_1",
                tool_name="WeatherCheckTask",
                tool_input_dict={"location": {"latitude": 48.8566, "longitude": 2.3522}},
                result={"temperature": 20, "condition": "sunny"},
                error=None,
            ),
        ],
    )

    anthropic_message = AnthropicMessage.from_domain(message)
    assert anthropic_message == AnthropicMessage(
        role="user",
        content=[
            TextContent(type="text", text="Here's what I found:"),
            ToolResultContent(
                type="tool_result",
                tool_use_id="weather_1",
                content=str({"temperature": 20, "condition": "sunny"}),
            ),
        ],
    )


def test_anthropic_message_from_domain_with_tool_call_error() -> None:
    message = MessageDeprecated(
        role=MessageDeprecated.Role.USER,
        content="I encountered an error:",
        tool_call_results=[
            ToolCall(
                id="weather_1",
                tool_name="WeatherCheckTask",
                tool_input_dict={"location": {"latitude": 48.8566, "longitude": 2.3522}},
                result=None,
                error="API unavailable",
            ),
        ],
    )

    anthropic_message = AnthropicMessage.from_domain(message)
    assert anthropic_message == AnthropicMessage(
        role="user",
        content=[
            TextContent(type="text", text="I encountered an error:"),
            ToolResultContent(
                type="tool_result",
                tool_use_id="weather_1",
                content="Error: API unavailable",
            ),
        ],
    )


class TestThinkingContent:
    def test_thinking_content_to_standard(self) -> None:
        """Test ThinkingContent conversion to standard format."""
        thinking_content = ThinkingContent(
            type="thinking",
            thinking="Let me think about this problem step by step...",
            signature="thinking_signature_123",
        )

        standard = thinking_content.to_standard()

        assert standard == {
            "type": "text",
            "text": "Let me think about this problem step by step...",
        }

    def test_thinking_content_to_standard_without_signature(self) -> None:
        """Test ThinkingContent conversion without signature."""
        thinking_content = ThinkingContent(
            type="thinking",
            thinking="Analyzing the user's request...",
        )

        standard = thinking_content.to_standard()

        assert standard == {
            "type": "text",
            "text": "Analyzing the user's request...",
        }

    def test_anthropic_message_with_thinking_content(self) -> None:
        """Test AnthropicMessage with ThinkingContent."""
        message = AnthropicMessage(
            role="assistant",
            content=[
                ThinkingContent(
                    type="thinking",
                    thinking="I need to analyze this request...",
                    signature="sig_123",
                ),
                TextContent(type="text", text="Here's my response."),
            ],
        )

        standard = message.to_standard()

        assert standard == {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I need to analyze this request..."},
                {"type": "text", "text": "Here's my response."},
            ],
        }


class TestCompletionRequestThinking:
    def test_completion_request_thinking_enabled(self) -> None:
        """Test CompletionRequest with thinking enabled."""
        thinking_config = CompletionRequest.Thinking(
            type="enabled",
            budget_tokens=1000,
        )

        request = CompletionRequest(
            messages=[],
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.7,
            stream=False,
            thinking=thinking_config,
        )

        request_dict = request.model_dump()
        assert request_dict["thinking"] == {
            "type": "enabled",
            "budget_tokens": 1000,
        }

    def test_completion_request_without_thinking(self) -> None:
        """Test CompletionRequest without thinking configuration."""
        request = CompletionRequest(
            messages=[],
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.7,
            stream=False,
        )

        request_dict = request.model_dump()
        assert request_dict["thinking"] is None


class TestThinkingDeltas:
    def test_thinking_delta_creation(self) -> None:
        """Test ThinkingDelta creation and attributes."""
        delta = ThinkingDelta(
            type="thinking_delta",
            thinking="First, I need to understand...",
        )

        assert delta.type == "thinking_delta"
        assert delta.thinking == "First, I need to understand..."

    def test_signature_delta_creation(self) -> None:
        """Test SignatureDelta creation and attributes."""
        delta = SignatureDelta(
            type="signature_delta",
            signature="signature_abc123",
        )

        assert delta.type == "signature_delta"
        assert delta.signature == "signature_abc123"

    def test_completion_chunk_extract_delta_with_thinking(self) -> None:
        """Test CompletionChunk.extract_delta with thinking delta."""
        chunk = CompletionChunk(
            type="content_block_delta",
            delta=ThinkingDelta(
                type="thinking_delta",
                thinking="Let me consider this approach...",
            ),
        )

        delta_text = chunk.extract_delta()
        assert delta_text == "Let me consider this approach..."

    def test_completion_chunk_extract_delta_with_signature(self) -> None:
        """Test CompletionChunk.extract_delta with signature delta."""
        chunk = CompletionChunk(
            type="content_block_delta",
            delta=SignatureDelta(
                type="signature_delta",
                signature="sig_456",
            ),
        )

        delta_text = chunk.extract_delta()
        assert delta_text == ""  # Signature deltas don't contribute to text output

    def test_completion_chunk_extract_delta_with_text(self) -> None:
        """Test CompletionChunk.extract_delta with text delta (existing behavior)."""
        from core.providers.anthropic.anthropic_domain import TextDelta

        chunk = CompletionChunk(
            type="content_block_delta",
            delta=TextDelta(
                type="text_delta",
                text="This is regular text content.",
            ),
        )

        delta_text = chunk.extract_delta()
        assert delta_text == "This is regular text content."


class TestErrorDetails:
    @pytest.mark.parametrize(
        "message, expected_error_cls, expected_capture",
        [
            pytest.param("Invalid base64 data", ProviderBadRequestError, True, id="invalid_base64_data"),
            pytest.param("Image exceeds", ProviderBadRequestError, False, id="image_exceeds"),
            pytest.param(
                "Image does not match the provided media type",
                ProviderBadRequestError,
                False,
                id="image_does_not_match_media_type",
            ),
            pytest.param("Prompt is too long", MaxTokensExceededError, False, id="prompt_is_too_long"),
            pytest.param(
                "Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.",
                ProviderInternalError,
                True,
                id="credit_balance_too_low",
            ),
            # Make sure we always default to an unknown provider error
            pytest.param("whatever blabla", UnknownProviderError, True, id="unknown_error"),
        ],
    )
    def test_invalid_request_error_to_domain(
        self,
        message: str,
        expected_error_cls: type[ProviderError],
        expected_capture: bool,
    ) -> None:
        error_details = ErrorDetails(message=message, type="invalid_request_error")
        error = error_details.to_domain(None)
        assert isinstance(error, expected_error_cls)
        assert error.capture == expected_capture
