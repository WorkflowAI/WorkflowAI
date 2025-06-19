from unittest.mock import Mock, patch

import pytest

from core.domain.errors import DefaultError
from core.utils.error_handler import ErrorHandler, handle_async_errors, handle_errors


class TestErrorHandler:
    def test_safe_execute_success(self):
        """Test successful operation execution."""

        def successful_operation():
            return "success"

        result = ErrorHandler.safe_execute(successful_operation)
        assert result == "success"

    def test_safe_execute_with_fallback(self):
        """Test operation failure with fallback value."""

        def failing_operation():
            raise ValueError("Test error")

        result = ErrorHandler.safe_execute(
            failing_operation,
            fallback_value="fallback",
            capture_errors=False,  # Don't capture in tests
        )
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_safe_execute_async_success(self):
        """Test successful async operation execution."""

        async def successful_async_operation():
            return "async_success"

        result = await ErrorHandler.safe_execute_async(successful_async_operation)
        assert result == "async_success"

    @pytest.mark.asyncio
    async def test_safe_execute_async_with_fallback(self):
        """Test async operation failure with fallback value."""

        async def failing_async_operation():
            raise ValueError("Test async error")

        result = await ErrorHandler.safe_execute_async(
            failing_async_operation,
            fallback_value="async_fallback",
            capture_errors=False,  # Don't capture in tests
        )
        assert result == "async_fallback"

    def test_handle_validation_error(self):
        """Test validation error handling."""
        validation_error = ValueError("Invalid field")

        result = ErrorHandler.handle_validation_error(
            validation_error,
            context="user_input",
            user_friendly_message="Please check your input",
            capture=False,  # Don't capture in tests
        )

        assert isinstance(result, DefaultError)
        assert result.status_code == 400
        assert result.code == "validation_error"
        assert "Please check your input" in str(result)
        assert result.details["original_error"] == "Invalid field"
        assert result.details["context"] == "user_input"

    def test_handle_not_found_error(self):
        """Test not found error handling."""
        result = ErrorHandler.handle_not_found_error(
            resource_type="task",
            resource_id="task_123",
            context="task_lookup",
        )

        assert isinstance(result, DefaultError)
        assert result.status_code == 404
        assert result.code == "object_not_found"
        assert "Task not found: task_123" in str(result)
        assert result.details["resource_type"] == "task"
        assert result.details["resource_id"] == "task_123"

    def test_handle_rate_limit_error(self):
        """Test rate limit error handling."""
        result = ErrorHandler.handle_rate_limit_error(
            resource="api_calls",
            retry_after=60,
            context="user_request",
        )

        assert isinstance(result, DefaultError)
        assert result.status_code == 429
        assert result.code == "rate_limit_exceeded"
        assert "Rate limit exceeded for api_calls" in str(result)
        assert "retry after 60 seconds" in str(result)
        assert result.details["retry_after"] == 60

    def test_handle_timeout_error(self):
        """Test timeout error handling."""
        result = ErrorHandler.handle_timeout_error(
            operation="data_processing",
            timeout_seconds=30,
            context={"user_id": "123", "job_id": "job_456"},
        )

        assert isinstance(result, DefaultError)
        assert result.status_code == 408
        assert result.code == "operation_timeout"
        assert "data_processing" in str(result)
        assert "30 seconds" in str(result)
        assert result.details["timeout_seconds"] == 30
        assert result.details["user_id"] == "123"

    def test_sanitize_error_data_string_truncation(self):
        """Test string data sanitization and truncation."""
        long_string = "a" * 1500
        sanitized = ErrorHandler.sanitize_error_data(long_string, max_length=1000)

        assert len(sanitized) == 1000 + len("... (truncated)")
        assert sanitized.endswith("... (truncated)")

    def test_sanitize_error_data_sensitive_fields(self):
        """Test sensitive field redaction."""
        sensitive_data = {
            "username": "john_doe",
            "password": "secret123",
            "api_token": "abc123def456",
            "user_secret": "hidden",
            "normal_field": "visible_data",
            "auth_key": "should_be_hidden",
        }

        sanitized = ErrorHandler.sanitize_error_data(sensitive_data)

        assert sanitized["username"] == "john_doe"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_token"] == "[REDACTED]"
        assert sanitized["user_secret"] == "[REDACTED]"
        assert sanitized["normal_field"] == "visible_data"
        assert sanitized["auth_key"] == "[REDACTED]"

    def test_sanitize_error_data_nested_structures(self):
        """Test sanitization of nested data structures."""
        nested_data = {
            "level1": {
                "level2": {
                    "password": "secret",
                    "data": "safe_data",
                },
                "tokens": ["token1", "token2"],
            },
            "list_data": [
                {"secret": "hidden", "public": "visible"},
                "normal_string",
            ],
        }

        sanitized = ErrorHandler.sanitize_error_data(nested_data)

        assert sanitized["level1"]["level2"]["password"] == "[REDACTED]"
        assert sanitized["level1"]["level2"]["data"] == "safe_data"
        assert sanitized["list_data"][0]["secret"] == "[REDACTED]"
        assert sanitized["list_data"][0]["public"] == "visible"
        assert sanitized["list_data"][1] == "normal_string"


class TestErrorDecorators:
    def test_handle_errors_decorator_success(self):
        """Test error handling decorator with successful operation."""

        @handle_errors(fallback_value="fallback", capture_errors=False)
        def successful_function(x, y):
            return x + y

        result = successful_function(2, 3)
        assert result == 5

    def test_handle_errors_decorator_failure(self):
        """Test error handling decorator with failing operation."""

        @handle_errors(fallback_value="fallback", capture_errors=False)
        def failing_function():
            raise ValueError("Test error")

        result = failing_function()
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_handle_async_errors_decorator_success(self):
        """Test async error handling decorator with successful operation."""

        @handle_async_errors(fallback_value="async_fallback", capture_errors=False)
        async def successful_async_function(x, y):
            return x * y

        result = await successful_async_function(3, 4)
        assert result == 12

    @pytest.mark.asyncio
    async def test_handle_async_errors_decorator_failure(self):
        """Test async error handling decorator with failing operation."""

        @handle_async_errors(fallback_value="async_fallback", capture_errors=False)
        async def failing_async_function():
            raise ValueError("Async test error")

        result = await failing_async_function()
        assert result == "async_fallback"


class TestErrorContextManager:
    @patch("core.utils.error_handler.capture_exception")
    @patch("core.utils.error_handler.new_scope")
    def test_capture_context_success(self, mock_new_scope, mock_capture_exception):
        """Test successful execution within error context."""
        mock_scope = Mock()
        mock_new_scope.return_value.__enter__.return_value = mock_scope

        with ErrorHandler.capture_context(
            error_type="test_error",
            operation="test_operation",
            tags={"tag1": "value1"},
            extras={"extra1": "extra_value"},
        ) as scope:
            # Simulate successful operation
            pass

        # Verify context was set up correctly
        mock_scope.set_tag.assert_any_call("error_type", "test_error")
        mock_scope.set_tag.assert_any_call("operation", "test_operation")
        mock_scope.set_tag.assert_any_call("tag1", "value1")
        mock_scope.set_extra.assert_called_with("extra1", "extra_value")

        # No exception should be captured on success
        mock_capture_exception.assert_not_called()

    @patch("core.utils.error_handler.capture_exception")
    @patch("core.utils.error_handler.new_scope")
    def test_capture_context_with_exception(self, mock_new_scope, mock_capture_exception):
        """Test exception handling within error context."""
        mock_scope = Mock()
        mock_new_scope.return_value.__enter__.return_value = mock_scope

        test_exception = ValueError("Test exception")

        with pytest.raises(ValueError):
            with ErrorHandler.capture_context(
                error_type="test_error",
                operation="test_operation",
            ) as scope:
                raise test_exception

        # Verify context was set up
        mock_scope.set_tag.assert_any_call("error_type", "test_error")
        mock_scope.set_tag.assert_any_call("operation", "test_operation")


class TestIntegrationScenarios:
    def test_file_processing_error_scenario(self):
        """Test error handling in a file processing scenario."""

        def process_file(file_path: str):
            if not file_path:
                raise ValueError("File path is required")
            if file_path.endswith(".invalid"):
                raise IOError("Invalid file format")
            return f"Processed: {file_path}"

        # Test successful processing
        result = ErrorHandler.safe_execute(
            lambda: process_file("document.pdf"),
            fallback_value="Processing failed",
            capture_errors=False,
        )
        assert result == "Processed: document.pdf"

        # Test error handling
        result = ErrorHandler.safe_execute(
            lambda: process_file("document.invalid"),
            fallback_value="Processing failed",
            capture_errors=False,
        )
        assert result == "Processing failed"

    @pytest.mark.asyncio
    async def test_api_request_error_scenario(self):
        """Test error handling in an API request scenario."""

        async def make_api_request(endpoint: str):
            if endpoint == "/error":
                raise ConnectionError("Network error")
            if endpoint == "/slow":
                raise TimeoutError("Request timeout")
            return {"status": "success", "endpoint": endpoint}

        # Test successful request
        result = await ErrorHandler.safe_execute_async(
            lambda: make_api_request("/users"),
            fallback_value={"status": "error"},
            capture_errors=False,
        )
        assert result["status"] == "success"
        assert result["endpoint"] == "/users"

        # Test error handling
        result = await ErrorHandler.safe_execute_async(
            lambda: make_api_request("/error"),
            fallback_value={"status": "error"},
            capture_errors=False,
        )
        assert result["status"] == "error"
