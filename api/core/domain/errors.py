from abc import ABC, abstractmethod
from typing import Any, override

from pydantic import ValidationError
from sentry_sdk import Scope, capture_exception, new_scope

from core.domain.consts import WORKFLOWAI_APP_URL
from core.domain.error_response import ErrorCode, ErrorResponse
from core.domain.models import Model, Provider
from core.utils.strings import obfuscate


class UnparsableChunkError(Exception):
    pass


class ScopeConfigurableError(Exception, ABC):
    @abstractmethod
    def configure_scope(self, scope: Scope):
        pass


class DefaultError(ScopeConfigurableError):
    """An error that is automatically caught and converted to a proper response"""

    code: ErrorCode | str = "internal_error"
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

    def __init__(self, model: Model | str, provider: Provider):
        super().__init__(details={"model": model, "provider": provider})

        self.model = model
        self.provider = provider

    def __str__(self) -> str:
        model_str = self.model.value if isinstance(self.model, Model) else self.model
        return f"Provider '{self.provider.value}' does not support '{model_str}'"


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
    default_capture = False

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


class JSONSchemaValidationError(ValueError):
    def __init__(self, *args: Any, json_str: str | None = None, validation_errors: list[Any] | None = None):
        super().__init__(*args)
        self.json_str = json_str
        self.validation_errors = validation_errors or []


class InvalidRunOptionsError(DefaultError):
    default_status_code = 400
    default_message = "Invalid run options"
    code = "invalid_run_properties"


class UnfixableSchemaError(DefaultError):
    code = "unsupported_json_schema"
    default_status_code = 422
    default_message = "Unsupported JSON schema"


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


class InvalidToken(DefaultError):
    default_status_code = 401
    default_capture: bool = True
    default_message = "Invalid token"
    code = "authentication_failed"

    @classmethod
    def from_invalid_api_key(cls, api_key: str):
        return InvalidToken(
            f"""Invalid API key provided: {obfuscate(api_key, 5)}.
Grab a fresh one (plus $5 in free LLM credits for new users) at {WORKFLOWAI_APP_URL}/keys 🚀""",
        )
