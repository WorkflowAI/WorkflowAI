import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional, TypeVar, Union

from sentry_sdk import capture_exception, new_scope

from core.domain.errors import DefaultError, ScopeConfigurableError

logger = logging.getLogger(__name__)

T = TypeVar("T")
E = TypeVar("E", bound=BaseException)


class ErrorHandler:
    """Enhanced error handler with better Sentry integration and context management."""

    @staticmethod
    @contextmanager
    def capture_context(
        error_type: str,
        operation: str,
        tags: Optional[Dict[str, Union[str, bool, int, float]]] = None,
        extras: Optional[Dict[str, Any]] = None,
    ):
        """Context manager for capturing errors with enhanced context."""
        with new_scope() as scope:
            scope.set_tag("error_type", error_type)
            scope.set_tag("operation", operation)

            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)

            if extras:
                for key, value in extras.items():
                    scope.set_extra(key, value)

            try:
                yield scope
            except Exception as e:
                # Enhance the exception with context if it's a ScopeConfigurableError
                if isinstance(e, ScopeConfigurableError):
                    e.configure_scope(scope)

                logger.exception(
                    "Error in %s operation",
                    operation,
                    extra={
                        "error_type": error_type,
                        "operation": operation,
                        **(extras or {}),
                    },
                )
                raise

    @staticmethod
    def safe_execute(
        operation: callable,
        fallback_value: T = None,
        error_message: str = "Operation failed",
        capture_errors: bool = True,
        operation_context: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Safely execute an operation with error handling and fallback."""
        try:
            return operation()
        except Exception as e:
            if capture_errors:
                with ErrorHandler.capture_context(
                    error_type="safe_execution_error",
                    operation=operation.__name__ if hasattr(operation, "__name__") else "unknown",
                    extras=operation_context,
                ):
                    capture_exception(e)

            logger.warning(
                "%s: %s",
                error_message,
                str(e),
                extra={
                    "operation": operation.__name__ if hasattr(operation, "__name__") else "unknown",
                    "fallback_used": True,
                    **(operation_context or {}),
                },
            )
            return fallback_value

    @staticmethod
    async def safe_execute_async(
        operation: callable,
        fallback_value: T = None,
        error_message: str = "Async operation failed",
        capture_errors: bool = True,
        operation_context: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Safely execute an async operation with error handling and fallback."""
        try:
            return await operation()
        except Exception as e:
            if capture_errors:
                with ErrorHandler.capture_context(
                    error_type="safe_async_execution_error",
                    operation=operation.__name__ if hasattr(operation, "__name__") else "unknown",
                    extras=operation_context,
                ):
                    capture_exception(e)

            logger.warning(
                "%s: %s",
                error_message,
                str(e),
                extra={
                    "operation": operation.__name__ if hasattr(operation, "__name__") else "unknown",
                    "fallback_used": True,
                    "async_operation": True,
                    **(operation_context or {}),
                },
            )
            return fallback_value

    @staticmethod
    def handle_validation_error(
        error: Exception,
        context: str,
        user_friendly_message: str = "Invalid input provided",
        capture: bool = True,
    ) -> DefaultError:
        """Handle validation errors with better user messaging."""
        error_details = {
            "original_error": str(error),
            "error_type": type(error).__name__,
            "context": context,
        }

        if capture:
            with ErrorHandler.capture_context(
                error_type="validation_error",
                operation=context,
                extras=error_details,
            ):
                capture_exception(error)

        return DefaultError(
            msg=user_friendly_message,
            code="validation_error",
            status_code=400,
            capture=False,  # Already captured above
            details=error_details,
        )

    @staticmethod
    def handle_not_found_error(
        resource_type: str,
        resource_id: str,
        context: str = "",
        capture: bool = False,
    ) -> DefaultError:
        """Handle not found errors with consistent messaging."""
        message = f"{resource_type.title()} not found"
        if resource_id:
            message += f": {resource_id}"

        error_details = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "context": context,
        }

        return DefaultError(
            msg=message,
            code="object_not_found",
            status_code=404,
            capture=capture,
            details=error_details,
        )

    @staticmethod
    def handle_rate_limit_error(
        resource: str,
        retry_after: Optional[int] = None,
        context: str = "",
    ) -> DefaultError:
        """Handle rate limit errors with retry information."""
        message = f"Rate limit exceeded for {resource}"
        if retry_after:
            message += f". Please retry after {retry_after} seconds"

        return DefaultError(
            msg=message,
            code="rate_limit_exceeded",
            status_code=429,
            capture=False,  # Rate limits are expected, don't spam Sentry
            details={
                "resource": resource,
                "retry_after": retry_after,
                "context": context,
            },
        )

    @staticmethod
    def handle_timeout_error(
        operation: str,
        timeout_seconds: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> DefaultError:
        """Handle timeout errors with operation context."""
        message = f"Operation '{operation}' timed out after {timeout_seconds} seconds"

        error_details = {
            "operation": operation,
            "timeout_seconds": timeout_seconds,
            **(context or {}),
        }

        with ErrorHandler.capture_context(
            error_type="timeout_error",
            operation=operation,
            extras=error_details,
        ):
            # Create a synthetic timeout exception for Sentry
            timeout_exception = TimeoutError(message)
            capture_exception(timeout_exception)

        return DefaultError(
            msg=message,
            code="operation_timeout",
            status_code=408,
            capture=False,  # Already captured above
            details=error_details,
        )

    @staticmethod
    def sanitize_error_data(data: Any, max_length: int = 1000) -> Any:
        """Sanitize error data to prevent sensitive information leakage."""
        if isinstance(data, str):
            if len(data) > max_length:
                return data[:max_length] + "... (truncated)"
            return data

        if isinstance(data, dict):
            sanitized = {}
            sensitive_keys = {"password", "token", "secret", "key", "auth", "credential"}

            for k, v in data.items():
                key_lower = str(k).lower()
                if any(sensitive in key_lower for sensitive in sensitive_keys):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = ErrorHandler.sanitize_error_data(v, max_length)
            return sanitized

        if isinstance(data, (list, tuple)):
            return [ErrorHandler.sanitize_error_data(item, max_length) for item in data]

        return data


# Convenient decorators
def handle_errors(
    fallback_value: T = None,
    error_message: str = "Operation failed",
    capture_errors: bool = True,
):
    """Decorator for automatic error handling."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            return ErrorHandler.safe_execute(
                lambda: func(*args, **kwargs),
                fallback_value=fallback_value,
                error_message=error_message,
                capture_errors=capture_errors,
                operation_context={"function": func.__name__, "args": len(args), "kwargs": len(kwargs)},
            )

        return wrapper

    return decorator


def handle_async_errors(
    fallback_value: T = None,
    error_message: str = "Async operation failed",
    capture_errors: bool = True,
):
    """Decorator for automatic async error handling."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await ErrorHandler.safe_execute_async(
                lambda: func(*args, **kwargs),
                fallback_value=fallback_value,
                error_message=error_message,
                capture_errors=capture_errors,
                operation_context={"function": func.__name__, "args": len(args), "kwargs": len(kwargs)},
            )

        return wrapper

    return decorator
