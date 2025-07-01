from unittest.mock import Mock

import httpx
import pytest

from core.domain.tool_call import ToolCallRequestWithID
from core.providers.base.provider_error import ProviderInvalidFileError
from core.providers.google.google_provider_base import GoogleProviderBase
from core.providers.google.google_provider_domain import Candidate, CompletionResponse, Content, Part, UsageMetadata


@pytest.mark.parametrize(
    "instructions, expected",
    [
        (
            "You can use @browser-text to search, and external-tool to send an email to some email@example.com",
            "You can use browser-text to search, and external-tool to send an email to some email@example.com",
        ),
    ],
)
def test_sanitize_agent_instructions(instructions: str, expected: str) -> None:
    result = GoogleProviderBase.sanitize_agent_instructions(instructions)
    assert result == expected


def test_extract_native_tool_calls_empty_response() -> None:
    response = CompletionResponse(
        candidates=[
            Candidate(
                content=None,
            ),
        ],
        usageMetadata=UsageMetadata(),
    )
    result = GoogleProviderBase._extract_native_tool_calls(response)  # pyright: ignore[reportPrivateUsage]
    assert result == []


def test_extract_native_tool_calls_no_function_calls() -> None:
    response = CompletionResponse(
        candidates=[
            Candidate(
                content=Content(
                    role="model",
                    parts=[Part(text="some text")],
                ),
            ),
        ],
        usageMetadata=UsageMetadata(),
    )
    result = GoogleProviderBase._extract_native_tool_calls(response)  # pyright: ignore[reportPrivateUsage]
    assert result == []


def test_extract_native_tool_calls_with_function_calls() -> None:
    response = CompletionResponse(
        candidates=[
            Candidate(
                content=Content(
                    role="model",
                    parts=[
                        Part(
                            functionCall=Part.FunctionCall(
                                name="browser-text",
                                args={"url": "https://example.com"},
                            ),
                        ),
                        Part(
                            functionCall=Part.FunctionCall(
                                name="external-tool",
                                args={"param1": "value1"},
                            ),
                        ),
                    ],
                ),
            ),
        ],
        usageMetadata=UsageMetadata(),
    )
    result = GoogleProviderBase._extract_native_tool_calls(response)  # pyright: ignore[reportPrivateUsage]
    assert result == [
        ToolCallRequestWithID(
            tool_name="@browser-text",
            tool_input_dict={"url": "https://example.com"},
        ),
        ToolCallRequestWithID(
            tool_name="external-tool",
            tool_input_dict={"param1": "value1"},
        ),
    ]


def test_extract_native_tool_calls_missing_tool_name() -> None:
    response = CompletionResponse(
        candidates=[
            Candidate(
                content=Content(
                    role="model",
                    parts=[
                        Part(
                            functionCall=Part.FunctionCall(
                                name="non-existent-tool",
                                args={},
                            ),
                        ),
                    ],
                ),
            ),
        ],
        usageMetadata=UsageMetadata(),
    )
    result = GoogleProviderBase._extract_native_tool_calls(response)  # pyright: ignore[reportPrivateUsage]
    assert result == [
        ToolCallRequestWithID(
            tool_name="non-existent-tool",
            tool_input_dict={},
        ),
    ]


@pytest.mark.parametrize(
    "error_message",
    [
        "Failed to fetch the file from the provided URL: url_error-error_not_found. Please check if the URL is accessible.",
        "Request failed due to url_timeout-timeout_fetchproxy. The server did not respond within the expected time.",
        "Unable to reach the provided URL: url_unreachable-unreachable_no_response. Please verify the URL is correct.",
        "The request was rejected: url_rejected-rejected_rpc_app_error. The server refused the connection.",
        "File upload failed: base64 decoding failed. The provided data is not valid base64.",
        "Processing failed: the document has no pages to analyze.",
        "Image processing error: unable to process input image. The image format may be unsupported or corrupted.",
        "Network error: url_unreachable-unreachable_5xx. The server returned an error status.",
        "Access denied: url_rejected by the target server.",
        "The requested URL is blocked: url_roboted. Access is restricted by robots.txt.",
        "File retrieval failed. Please ensure the url is valid and accessible from our servers.",
        "Unable to submit request because it has a mimeType parameter with value application/msword, which is not supported. Update the mimeType and try again. Learn more: https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/gemini",
    ],
)
def test_handle_invalid_argument_raises_provider_invalid_file_error(error_message: str) -> None:
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 400

    with pytest.raises(ProviderInvalidFileError):
        GoogleProviderBase._handle_invalid_argument(error_message, mock_response)  # pyright: ignore[reportPrivateUsage]


def test_structured_output_logic_with_tools() -> None:
    """Test that structured output is disabled when tools are enabled."""
    from unittest.mock import Mock, patch
    from core.domain.message import MessageDeprecated
    from core.domain.models import Model
    from core.providers.base.provider_options import ProviderOptions
    from core.domain.tool import Tool

    # Mock the model data to support structured output
    mock_model_data = Mock()
    mock_model_data.supports_structured_output = True
    mock_model_data.supports_json_mode = True
    mock_model_data.supports_system_messages = True
    mock_model_data.reasoning = None

    # Create provider options with both tools and output schema
    mock_tool = Mock(spec=Tool)
    mock_tool.name = "test_tool"
    mock_tool.description = "Test tool"
    mock_tool.input_schema = {}
    mock_tool.output_schema = None
    
    options = Mock(spec=ProviderOptions)
    options.enabled_tools = [mock_tool]  # Tools are enabled
    options.output_schema = {"type": "object", "properties": {"test": {"type": "string"}}}
    options.structured_generation = True
    options.model = Model.GEMINI_2_5_FLASH
    options.temperature = 0.7
    options.max_tokens = 1000
    options.tool_choice = None
    options.presence_penalty = None
    options.frequency_penalty = None
    options.top_p = None
    
    def mock_final_reasoning_budget(reasoning):
        return None
    options.final_reasoning_budget = mock_final_reasoning_budget

    messages = [Mock(spec=MessageDeprecated)]
    messages[0].role = MessageDeprecated.Role.USER
    messages[0].image_options = None

    # Create a mock provider instance
    class MockGoogleProvider(GoogleProviderBase):
        def _request_url(self, model, stream):
            return "https://mock.url"
    
    provider = MockGoogleProvider(Mock())

    with patch('core.providers.google.google_provider_base.get_model_data', return_value=mock_model_data), \
         patch.object(provider, '_convert_messages', return_value=([Mock()], None)), \
         patch.object(provider, '_safety_settings', return_value=None), \
         patch.object(provider, '_add_native_tools'):
        
        request = provider._build_request(messages, options, stream=False)
        
        # When tools are enabled, structured output should be disabled
        # responseMimeType should be "text/plain" and responseSchema should be None
        assert request.generationConfig.responseMimeType == "text/plain"
        assert request.generationConfig.responseSchema is None


def test_structured_output_logic_without_tools() -> None:
    """Test that structured output is enabled when tools are disabled."""
    from unittest.mock import Mock, patch
    from core.domain.message import MessageDeprecated
    from core.domain.models import Model
    from core.providers.base.provider_options import ProviderOptions

    # Mock the model data to support structured output
    mock_model_data = Mock()
    mock_model_data.supports_structured_output = True
    mock_model_data.supports_json_mode = True
    mock_model_data.supports_system_messages = True
    mock_model_data.reasoning = None

    # Create provider options without tools but with output schema
    options = Mock(spec=ProviderOptions)
    options.enabled_tools = []  # No tools enabled
    options.output_schema = {"type": "object", "properties": {"test": {"type": "string"}}}
    options.structured_generation = True
    options.model = Model.GEMINI_2_5_FLASH
    options.temperature = 0.7
    options.max_tokens = 1000
    options.tool_choice = None
    options.presence_penalty = None
    options.frequency_penalty = None
    options.top_p = None
    
    def mock_final_reasoning_budget(reasoning):
        return None
    options.final_reasoning_budget = mock_final_reasoning_budget

    messages = [Mock(spec=MessageDeprecated)]
    messages[0].role = MessageDeprecated.Role.USER
    messages[0].image_options = None

    # Create a mock provider instance
    class MockGoogleProvider(GoogleProviderBase):
        def _request_url(self, model, stream):
            return "https://mock.url"
    
    provider = MockGoogleProvider(Mock())

    with patch('core.providers.google.google_provider_base.get_model_data', return_value=mock_model_data), \
         patch.object(provider, '_convert_messages', return_value=([Mock()], None)), \
         patch.object(provider, '_safety_settings', return_value=None), \
         patch.object(provider, '_add_native_tools'), \
         patch('core.providers.google.google_provider_base.prepare_google_json_schema', return_value={"cleaned": "schema"}) as mock_prepare:
        
        request = provider._build_request(messages, options, stream=False)
        
        # When tools are disabled, structured output should be enabled
        # responseMimeType should be "application/json" and responseSchema should be set
        assert request.generationConfig.responseMimeType == "application/json"
        assert request.generationConfig.responseSchema == {"cleaned": "schema"}
        
        # Verify that the schema preparation function was called
        mock_prepare.assert_called_once()
