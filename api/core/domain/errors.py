from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, override

from httpx import Response
from pydantic import ValidationError
from sentry_sdk import Scope, capture_exception, new_scope

from core.domain.agent_run_result import AgentRunResult
from core.domain.error_response import ErrorCode, ErrorResponse, ProviderErrorCode
from core.domain.models import Model, Provider
from core.domain.types import TaskOutputDict
from core.providers.base.provider_options import ProviderOptions


class UnparsableChunkError(Exception):
    pass


class ScopeConfigurableError(Exception, ABC):
    @abstractmethod
    def configure_scope(self, scope: Scope):
        pass


class DefaultError(ScopeConfigurableError):
    """An error that is automatically caught and converted to a proper response"""

    code: ErrorCode = "internal_error"
    default_status_code: int | None = None
    default_capture: bool = True
    default_message: str = "An error occurred"

    def __init__(
        self,
        msg: str | None = None,
        code: ErrorCode | None = None,
        status_code: int | None = None,
        capture: bool | None = None,
        # Details are passed along in the response
        details: dict[str, Any] | None = None,
        # Extras are sent to sentry and not included in the response
        **extras: Any,
    ):
        super().__init__(msg or self.default_message)
        self.code = code or self.__class__.code
        self.status_code = status_code or self.default_status_code or 500
        self.capture = capture if capture is not None else self.default_capture
        self.extras = extras or {}
        self.details = details or {}

    @override
    def configure_scope(self, scope: Scope):
        if not self.capture:
            scope.set_level("info")

        if self.extras:
            for k, v in self.extras.items():
                scope.set_extra(k, v)

    def capture_if_needed(self):
        if self.capture:
            with new_scope() as scope:
                self.configure_scope(scope)

                capture_exception(self)

    def error_response(self):
        return ErrorResponse(
            error=ErrorResponse.Error(
                status_code=self.status_code,
                code=self.code,
                message=str(self),
                details=self.details or None,
            ),
        )


class BadRequestError(DefaultError):
    default_status_code = 400
    default_message = "Bad request"
    code = "bad_request"
    default_capture = False


# TODO: merge with ObjectNotFoundException
class ObjectNotFoundError(DefaultError):
    default_status_code = 404
    default_message = "Object not found"
    code = "object_not_found"
    default_capture = False


class EntityTooLargeError(DefaultError):
    default_status_code = 413
    default_message = "Entity too large"
    code = "entity_too_large"
    default_capture = False


class NoDefinedRunnerError(DefaultError):
    default_capture = True  # this should never happen
    default_status_code = 400
    default_message = "No defined runner"


class NoDefinedEvaluatorError(Exception):
    pass


class MissingEnvVariablesError(Exception):
    def __init__(self, names: list[str]):
        self.names = names

    def __str__(self) -> str:
        return f"Missing environment variables: {', '.join(self.names)}"


class MissingCacheError(DefaultError):
    default_status_code = 400
    default_message = "Missing cache"
    code = "object_not_found"


class OperationTimeout(DefaultError):
    default_status_code = 504
    default_message = "Operation timed out"
    default_capture = True


class InvalidRunnerOptionsError(Exception):
    def __init__(self, validation_error: ValidationError):
        self.validation_error = validation_error


class ProviderDoesNotSupportModelError(DefaultError):
    default_capture = False
    default_status_code = 400
    default_message = "Provider does not support model"
    code = "provider_does_not_support_model"

    def __init__(self, model: Model, provider: Provider):
        super().__init__(details={"model": model, "provider": provider})

        self.model = model
        self.provider = provider

    def __str__(self) -> str:
        return f"Provider '{self.provider.value}' does not support '{self.model.value}'"


class NoProviderSupportingModelError(DefaultError):
    default_capture = False
    default_status_code = 400
    default_message = "No configured providers support model"
    code = "no_provider_supporting_model"

    def __init__(self, model: str, available_providers: list[str] | None = None):
        super().__init__(details={"model": model, "available_providers": available_providers})

        self.model = model
        self.available_providers = available_providers


class NoProviderIsConfiguredError(Exception):
    def __str__(self) -> str:
        return "No provider is configured"


class SunsetModelWithoutReplacementError(Exception):
    def __init__(self, model: str, provider: str, days_before: int):
        self.model = model
        self.provider = provider
        self.days_before = days_before

    def __str__(self) -> str:
        return f"Model {self.model} has no replacement model {self.provider}, days before sunset: {self.days_before}"


class TaskRunHasNoExampleError(Exception):
    pass


class ExampleNotFoundError(Exception):
    pass


class InvalidMetadata(Exception):
    pass


class MissingContextWorklowAI(Exception):
    pass


class DuplicateValueError(Exception):
    pass


class NoopError(DefaultError):
    default_status_code = 400
    default_message = "No operation to perform"
    code = "bad_request"


class InternalError(ScopeConfigurableError):
    default_fatal = True

    def __init__(self, msg: str | None = None, fatal: bool | None = None, **extras: Any):
        super().__init__(msg)
        self.extras = extras or {}
        self.fatal = self.default_fatal if fatal is None else fatal

    @override
    def configure_scope(self, scope: Scope):
        if self.fatal:
            scope.set_level("fatal")

        if self.extras:
            for k, v in self.extras.items():
                scope.set_extra(k, v)


class UnpriceableRunError(InternalError):
    # Raise when we can't calculate the token count for a run, ex: image in the message
    pass


class InvalidFileError(DefaultError):
    code = "invalid_file"
    default_status_code = 400
    default_message = "File not available"

    def __init__(
        self,
        msg: str | None = None,
        status_code: int | None = None,
        capture: bool | None = None,
        file_url: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            msg or self.default_message,
            status_code=status_code,
            capture=capture,
            details={"file_url": file_url, **(details or {})},
        )


# There is some overlap between DefaultError and ProviderError but better to keep as is for now
# since the logic / types are slightly different
class ProviderError(ScopeConfigurableError):
    default_title = "Error"
    code: ProviderErrorCode = "unknown_provider_error"
    default_status_code: int | None = None
    default_capture = True
    default_message = "An error occurred"
    default_retry = False
    default_store_task_run = True
    should_try_next_provider = False

    def __init__(
        self,
        msg: str | None = None,
        title: str | None = None,
        provider_status_code: int | None = None,
        provider_error: Any | None = None,
        provider_options: ProviderOptions | None = None,
        provider: Provider | None = None,
        retry: bool | None = None,
        max_attempt_count: int = 2,  # only active is retry is true
        status_code: int | None = None,
        retry_after: float | datetime | None = 0,
        capture: bool | None = None,
        response: Response | None = None,
        # A possibly created task run
        task_run_id: str | None = None,
        store_task_run: bool | None = None,
        # TODO: this should be a dict[str, Any] once we remove generic tasks
        partial_output: TaskOutputDict | None = None,
        # To customize the grouping of Sentry errors
        fingerprint: list[str] | None = None,
        **extras: Any,
    ):
        """
        Initialize a new ProviderError instance.

        Args:
            msg (str): The error message.
            usage (LLMUsage): the LLM usage for the completion.
            retry (bool, optional): Indicates if the task should be retried. Defaults to False.
            retry_after (int | datetime | None, optional): The time to wait before retrying the task. Defaults to 0.
            **extras (Any): Additional information or data associated with the error.

        """
        super().__init__(msg or self.default_message)
        self.title = title or self.default_title
        self.retry = retry if retry is not None else self.default_retry
        self.retry_after = retry_after
        self.capture = capture if capture is not None else self.default_capture
        self._status_code = status_code or self.default_status_code or None
        self.provider_options = provider_options
        self.provider = provider
        self.provider_status_code = provider_status_code

        self.provider_error = provider_error

        self.task_run_id = task_run_id

        self.extras = extras or {}
        self.max_attempt_count = max_attempt_count
        self.store_task_run = store_task_run if store_task_run is not None else self.default_store_task_run
        self.partial_output = partial_output
        self.fingerprint = fingerprint or self.default_fingerprint()

        if response:
            self.set_response(response)

    @property
    def status_code(self) -> int:
        return self._status_code or 500

    def set_response(self, response: Response):
        # We don't set the status code if the provider status code is not an error
        # self.status_code is the status code returned by the API so we should
        # Not return a success status code on error
        if not self._status_code and response.status_code >= 400:
            self._status_code = response.status_code
        if not self.provider_status_code:
            self.provider_status_code = response.status_code
        if not self.provider_error:
            self.provider_error = self._extract_provider_error(response)

    def default_fingerprint(self):
        return [self.code, self.provider]

    @classmethod
    def _extract_provider_error(cls, response: Response):
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def retry_after_str(self) -> str | None:
        if self.retry_after is None:
            return None
        if isinstance(self.retry_after, datetime):
            return self.retry_after.isoformat()
        return str(self.retry_after)

    def retry_after_date(self) -> datetime | None:
        if isinstance(self.retry_after, float) or isinstance(self.retry_after, int):
            return datetime.now() + timedelta(seconds=self.retry_after)
        return self.retry_after

    def retry_delay(self) -> float | None:
        if isinstance(self.retry_after, datetime):
            return (self.retry_after - datetime.now()).total_seconds()
        return self.retry_after

    def serialized_details(self) -> dict[str, Any]:
        return {
            "provider_status_code": getattr(self, "provider_status_code", None),
            "provider_error": getattr(self, "provider_error", None),
            "provider_options": self.provider_options.model_dump(mode="json", exclude_none=True)
            if self.provider_options
            else None,
            "provider": self.provider,
        }

    @override
    def configure_scope(self, scope: Scope):
        if self.provider:
            scope.set_tag("provider", self.provider)
        if self.provider_options:
            scope.set_tag("model", self.provider_options.model)
        # We use the fingerprint to group errors in Sentry
        if self.fingerprint:
            scope.fingerprint = self.fingerprint

        if self.task_run_id:
            scope.set_extra("task_run_id", self.task_run_id)

    def capture_if_needed(self):
        if self.capture:
            with new_scope() as scope:
                self.configure_scope(scope)
                capture_exception(self)

    def error_response(self):
        return ErrorResponse(
            error=ErrorResponse.Error(
                title=self.title,
                status_code=self.status_code,
                code=self.code,
                message=str(self),
                details=self.serialized_details() or None,
            ),
            id=self.task_run_id,
            task_output=self.partial_output,
        )


class JSONSchemaValidationError(ValueError):
    def __init__(self, *args: Any, json_str: str | None = None):
        super().__init__(*args)

        self.json_str = json_str


class MaxToolCallIterationError(ProviderError):
    code = "max_tool_call_iteration"
    default_status_code = 400


class FailedGenerationError(ProviderError):
    code = "failed_generation"
    default_status_code = 400


class InvalidGenerationError(ProviderError):
    code = "invalid_generation"
    default_status_code = 400
    default_retry = True


class InvalidProviderConfig(ProviderError):
    code = "invalid_provider_config"
    default_status_code = 400
    default_message = "Invalid provider configuration"


class MaxTokensExceededError(ProviderError):
    """
    This error is raised when the maximum number of tokens is exceeded for a given model.
    This is not a 'preventive' check, but rather a 'reactive' error, as it raised if we
    receive an error response from the LLM provider.
    """

    default_status_code = 413  # 413: Entity Too Large
    code = "max_tokens_exceeded"
    default_capture = False

    def __init__(
        self,
        msg: str = "Model max tokens limit exceeded",
        retry: bool = False,
        retry_after: float | datetime | None = 0,
        **extras: Any,
    ):
        super().__init__(msg=msg, retry=retry, retry_after=retry_after, **extras)


class ProviderRateLimitError(ProviderError):
    code = "rate_limit"
    default_status_code = 429
    default_message = "Rate limit exceeded"
    default_capture = False
    default_store_task_run = False
    should_try_next_provider = True


class ProviderTimeoutError(ProviderError):
    code = "timeout"
    default_status_code = 408
    default_message = "Provider request timed out"
    default_capture = True  # Monitor to increase request timeout if needed
    default_store_task_run = False
    should_try_next_provider = True


class AgentRunFailedError(ProviderError):
    code = "agent_run_failed"
    default_status_code = 424  # 424: Failed Dependency
    default_message = "Agent run failed"
    default_capture = False
    default_store_task_run = True
    should_try_next_provider = False

    def __init__(
        self,
        agent_run_error_code: str,
        agent_run_error_message: str,
        **extras: Any,
    ):
        super().__init__(**extras)
        self.agent_run_error_code = agent_run_error_code
        self.agent_run_error_message = agent_run_error_message

    def __str__(self) -> str:
        str_value = self.default_message
        if self.agent_run_error_code:
            str_value += f" ({self.agent_run_error_code})"
        if self.agent_run_error_message:
            str_value += f": {self.agent_run_error_message}"
        return str_value

    @classmethod
    def from_agent_run_result(cls, agent_run_result: AgentRunResult, partial_output: TaskOutputDict | None = None):
        return cls(
            agent_run_error_code=(agent_run_result.error and agent_run_result.error.error_code) or "",
            agent_run_error_message=(agent_run_result.error and agent_run_result.error.error_message) or "",
            store_task_run=True,
            partial_output=partial_output,
        )


class ServerOverloadedError(ProviderError):
    code = "server_overloaded"
    default_status_code = 424  # 424: Failed Dependency
    default_message = "Provider server is over capacity"
    default_capture = False
    default_store_task_run = False
    should_try_next_provider = True


class ProviderUnavailableError(ProviderError):
    code = "provider_unavailable"
    default_status_code = 424  # 424: Failed Dependency
    default_message = "Provider is unavailable"
    default_capture = False
    default_store_task_run = False
    should_try_next_provider = True


class InvalidRunOptionsError(DefaultError):
    default_status_code = 400
    default_message = "Invalid run options"
    code = "invalid_run_properties"


class ProviderInternalError(ProviderError):
    code = "provider_internal_error"
    default_message = "Provider returned an internal error"
    default_status_code = 424  # 424: Failed Dependency
    default_capture = False
    default_store_task_run = False
    should_try_next_provider = True


class UnknownProviderError(ProviderError):
    code = "unknown_provider_error"
    default_status_code = 400
    should_try_next_provider = True

    @override
    def default_fingerprint(self):
        return [self.code, self.provider, str(self.provider_error) if self.provider_error else str(self)]

    @override
    def configure_scope(self, scope: Scope):
        super().configure_scope(scope)
        # Adding the entire response as extra when available
        if self.provider_error:
            scope.set_extra("provider_error", self.provider_error)


class ReadTimeOutError(ProviderError):
    code = "read_timeout"
    default_status_code = 408
    default_message = "Read timeout"


class ModelDoesNotSupportMode(ProviderError):
    code = "model_does_not_support_mode"
    default_status_code = 400
    default_message = "Model does not support mode"
    default_capture = False
    # We retry the next provider when possible
    # Some times, different providers support different modes
    should_try_next_provider = True


class ContentModerationError(ProviderError):
    code = "content_moderation"
    default_status_code = 400
    default_message = "Content moderation"
    default_capture = True
    default_store_task_run = True


class TaskBannedError(ProviderError):
    code = "task_banned"
    default_status_code = 400
    default_message = "Task banned, please contact support WorkflowAI (contact@workflowai.com) for more details"
    default_capture = True
    default_store_task_run = False


class UnfixableSchemaError(DefaultError):
    code = "unsupported_json_schema"
    default_status_code = 422
    default_message = "Unsupported JSON schema"


class StructuredGenerationError(ProviderError):
    code = "structured_generation_error"
    default_status_code = 400
    default_message = "Structured generation error"
    default_capture = True
    default_store_task_run = False


class ProviderBadRequestError(ProviderError):
    code = "bad_request"
    default_status_code = 400
    default_message = "Bad request"
    default_capture = False
    default_store_task_run = False


class ProviderInvalidFileError(ProviderBadRequestError):
    code = "invalid_file"
    default_message = "Cannot fetch content from the provided URL"


class ToolNotFoundError(Exception):
    pass


def message_from_validation_error(validation_error: ValidationError) -> str:
    errors = validation_error.errors()
    if not errors or len(errors) > 1:
        return str(validation_error)

    if ctx := errors[0].get("ctx"):
        if err := ctx.get("error"):
            return str(err)
    return errors[0]["msg"]


class MissingModelError(ProviderError):
    """
    Raised when a provider responds that it does not support the model.
    This is different from a ProviderDoesNotSupportModelError, which is raised way before
    when we try to select a provider for the model.

    We should really never have MissingModelError, as it means that our configuration is messed up.
    """

    code = "missing_model"
    default_status_code = 400
    default_message = "The requested provider does not support the model"
    default_capture = True
    should_try_next_provider = True
