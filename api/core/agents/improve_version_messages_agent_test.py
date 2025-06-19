from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.agents.improve_version_messages_agent import (
    ImproveVersionMessagesError,
    ImproveVersionMessagesInput,
    ImproveVersionMessagesOutput,
    _create_response_from_output,
    improve_version_messages_agent,
)


class TestImproveVersionMessagesAgent:
    def test_input_validation_empty_messages(self):
        """Test that empty messages raise appropriate error."""
        input_data = ImproveVersionMessagesInput(
            initial_messages=[],
            run=None,
            improvement_instructions="Test instructions",
        )

        with pytest.raises(ImproveVersionMessagesError) as exc_info:
            # We need to run the async generator to trigger the validation
            gen = improve_version_messages_agent(input_data)
            # This should raise immediately due to validation
            gen.__anext__()

        assert "Cannot improve empty messages" in str(exc_info.value)
        assert exc_info.value.context["input"]["initial_messages"] == []

    @pytest.mark.asyncio
    async def test_successful_message_improvement(self):
        """Test successful message improvement flow."""
        input_data = ImproveVersionMessagesInput(
            initial_messages=[{"role": "user", "content": "Hello"}],
            run=None,
            improvement_instructions="Make it better",
        )

        # Mock the OpenAI client and response
        mock_chunk = Mock()
        mock_chunk.type = "content.delta"
        mock_chunk.delta = '{"improved_messages": [{"role": "user", "content": "Hello there!"}], "changelog": ["Made greeting more enthusiastic"]}'
        mock_chunk.parsed = {
            "improved_messages": [{"role": "user", "content": "Hello there!"}],
            "changelog": ["Made greeting more enthusiastic"],
        }
        mock_chunk.feedback_token = "test_token"

        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_response.__aiter__.return_value = iter([mock_chunk])

        mock_client = Mock()
        mock_client.beta.chat.completions.stream.return_value = mock_response

        with patch("core.agents.improve_version_messages_agent.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client

            responses = []
            async for response in improve_version_messages_agent(input_data):
                responses.append(response)

            assert len(responses) == 1
            assert len(responses[0].improved_messages) == 1
            assert responses[0].improved_messages[0].content == "Hello there!"
            assert responses[0].changelog == ["Made greeting more enthusiastic"]
            assert responses[0].feedback_token == "test_token"

    @pytest.mark.asyncio
    async def test_malformed_json_handling(self):
        """Test handling of malformed JSON in streaming response."""
        input_data = ImproveVersionMessagesInput(
            initial_messages=[{"role": "user", "content": "Test"}],
            run=None,
            improvement_instructions="Improve",
        )

        # Create chunks with malformed JSON
        chunks = [
            Mock(type="content.delta", delta='{"improved_', parsed=None, feedback_token=None),
            Mock(type="content.delta", delta='messages": [{"role":', parsed=None, feedback_token=None),
            Mock(
                type="content.delta",
                delta=' "user", "content": "Better test"}], "changelog": ["Fixed"]}',
                parsed=None,
                feedback_token=None,
            ),
        ]

        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_response.__aiter__.return_value = iter(chunks)

        mock_client = Mock()
        mock_client.beta.chat.completions.stream.return_value = mock_response

        with patch("core.agents.improve_version_messages_agent.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client

            responses = []
            async for response in improve_version_messages_agent(input_data):
                responses.append(response)

            # Should get a valid response when JSON is completed
            assert len(responses) == 1
            assert responses[0].improved_messages[0].content == "Better test"

    @pytest.mark.asyncio
    async def test_no_valid_response_error(self):
        """Test error handling when no valid response is generated."""
        input_data = ImproveVersionMessagesInput(
            initial_messages=[{"role": "user", "content": "Test"}],
            run=None,
            improvement_instructions="Improve",
        )

        # Create chunks that never form valid JSON
        chunks = [
            Mock(type="content.delta", delta="invalid", parsed=None, feedback_token=None),
            Mock(type="content.delta", delta="json", parsed=None, feedback_token=None),
            Mock(type="content.delta", delta="data", parsed=None, feedback_token=None),
        ]

        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_response.__aiter__.return_value = iter(chunks)

        mock_client = Mock()
        mock_client.beta.chat.completions.stream.return_value = mock_response

        with patch("core.agents.improve_version_messages_agent.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client

            with pytest.raises(ImproveVersionMessagesError) as exc_info:
                responses = []
                async for response in improve_version_messages_agent(input_data):
                    responses.append(response)

            assert "Failed to generate valid response" in str(exc_info.value)
            assert exc_info.value.context["chunk_count"] == 3
            assert exc_info.value.context["error_count"] == 3

    @pytest.mark.asyncio
    async def test_too_many_errors_handling(self):
        """Test handling when too many consecutive errors occur."""
        input_data = ImproveVersionMessagesInput(
            initial_messages=[{"role": "user", "content": "Test"}],
            run=None,
            improvement_instructions="Improve",
        )

        # Create chunks that always cause JSON decode errors
        bad_chunks = [
            Mock(type="content.delta", delta="bad_json{", parsed=None, feedback_token=None) for _ in range(10)
        ]

        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_response.__aiter__.return_value = iter(bad_chunks)

        mock_client = Mock()
        mock_client.beta.chat.completions.stream.return_value = mock_response

        with patch("core.agents.improve_version_messages_agent.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client

            with pytest.raises(ImproveVersionMessagesError) as exc_info:
                responses = []
                async for response in improve_version_messages_agent(input_data):
                    responses.append(response)

            assert "Failed to generate valid response" in str(exc_info.value)
            # Should stop after 5 errors (max_errors limit)
            assert exc_info.value.context["error_count"] == 5

    @pytest.mark.asyncio
    async def test_memory_limit_handling(self):
        """Test handling of memory limits for accumulated content."""
        input_data = ImproveVersionMessagesInput(
            initial_messages=[{"role": "user", "content": "Test"}],
            run=None,
            improvement_instructions="Improve",
        )

        # Create chunks that accumulate to large content
        large_content = "x" * 20000
        chunks = [
            Mock(type="content.delta", delta=large_content, parsed=None, feedback_token=None),
            Mock(type="content.delta", delta=large_content, parsed=None, feedback_token=None),
            Mock(
                type="content.delta", delta=large_content, parsed=None, feedback_token=None
            ),  # This should trigger truncation
            Mock(
                type="content.delta",
                delta='{"improved_messages": [{"role": "user", "content": "Final"}], "changelog": []}',
                parsed=None,
                feedback_token=None,
            ),
        ]

        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_response.__aiter__.return_value = iter(chunks)

        mock_client = Mock()
        mock_client.beta.chat.completions.stream.return_value = mock_response

        with patch("core.agents.improve_version_messages_agent.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client

            responses = []
            async for response in improve_version_messages_agent(input_data):
                responses.append(response)

            # Should get final valid response
            assert len(responses) == 1
            assert responses[0].improved_messages[0].content == "Final"

    @pytest.mark.asyncio
    async def test_last_valid_response_fallback(self):
        """Test fallback to last valid response when final processing fails."""
        input_data = ImproveVersionMessagesInput(
            initial_messages=[{"role": "user", "content": "Test"}],
            run=None,
            improvement_instructions="Improve",
        )

        chunks = [
            # First valid response
            Mock(
                type="content.delta",
                delta="",
                parsed={"improved_messages": [{"role": "user", "content": "Good response"}], "changelog": []},
                feedback_token=None,
            ),
            # Then invalid chunks
            Mock(type="content.delta", delta="invalid", parsed=None, feedback_token=None),
            Mock(type="content.delta", delta="json", parsed=None, feedback_token=None),
        ]

        mock_response = AsyncMock()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_response.__aiter__.return_value = iter(chunks)

        mock_client = Mock()
        mock_client.beta.chat.completions.stream.return_value = mock_response

        with patch("core.agents.improve_version_messages_agent.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client

            responses = []
            async for response in improve_version_messages_agent(input_data):
                responses.append(response)

            # Should get the valid response and then the fallback
            assert len(responses) == 2
            assert responses[0].improved_messages[0].content == "Good response"
            assert responses[1].improved_messages[0].content == "Good response"  # Fallback to last valid


class TestCreateResponseFromOutput:
    def test_valid_output(self):
        """Test creating response from valid output."""
        output = ImproveVersionMessagesOutput(
            improved_messages=[
                ImproveVersionMessagesOutput.Message(role="user", content="Hello"),
                ImproveVersionMessagesOutput.Message(role="assistant", content="Hi there!"),
            ],
            changelog=["Made greeting friendlier"],
        )

        response = _create_response_from_output(output, "test_token")

        assert len(response.improved_messages) == 2
        assert response.improved_messages[0].content == "Hello"
        assert response.improved_messages[1].content == "Hi there!"
        assert response.feedback_token == "test_token"
        assert response.changelog == ["Made greeting friendlier"]

    def test_empty_messages_error(self):
        """Test error handling for empty messages."""
        output = ImproveVersionMessagesOutput(
            improved_messages=[],
            changelog=[],
        )

        with pytest.raises(Exception):  # Should raise ValidationError
            _create_response_from_output(output, None)

    def test_invalid_message_roles(self):
        """Test handling of invalid message roles."""
        output = ImproveVersionMessagesOutput(
            improved_messages=[
                ImproveVersionMessagesOutput.Message(role="invalid_role", content="Hello"),
                ImproveVersionMessagesOutput.Message(role="user", content="Valid message"),
            ],
            changelog=[],
        )

        response = _create_response_from_output(output, None)

        # Should have 2 messages with the invalid role defaulted to 'user'
        assert len(response.improved_messages) == 2
        assert response.improved_messages[0].role == "user"  # Defaulted
        assert response.improved_messages[1].role == "user"

    def test_empty_content_filtering(self):
        """Test filtering of empty content messages."""
        output = ImproveVersionMessagesOutput(
            improved_messages=[
                ImproveVersionMessagesOutput.Message(role="user", content=""),
                ImproveVersionMessagesOutput.Message(role="user", content="   "),  # Whitespace only
                ImproveVersionMessagesOutput.Message(role="user", content="Valid content"),
            ],
            changelog=[],
        )

        response = _create_response_from_output(output, None)

        # Should only have the valid message
        assert len(response.improved_messages) == 1
        assert response.improved_messages[0].content == "Valid content"

    def test_no_valid_messages_after_filtering(self):
        """Test error when no valid messages remain after filtering."""
        output = ImproveVersionMessagesOutput(
            improved_messages=[
                ImproveVersionMessagesOutput.Message(role="user", content=""),
                ImproveVersionMessagesOutput.Message(role="user", content="   "),
            ],
            changelog=[],
        )

        with pytest.raises(Exception):  # Should raise ValidationError
            _create_response_from_output(output, None)


class TestImproveVersionMessagesError:
    def test_error_creation(self):
        """Test error creation with context."""
        context = {"test_key": "test_value", "error_count": 5}
        error = ImproveVersionMessagesError("Test error message", context)

        assert str(error) == "Test error message"
        assert error.context == context

    def test_error_without_context(self):
        """Test error creation without context."""
        error = ImproveVersionMessagesError("Test error message")

        assert str(error) == "Test error message"
        assert error.context == {}
