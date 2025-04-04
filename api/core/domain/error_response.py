from typing import Any, Literal

from pydantic import BaseModel, Field

ProviderErrorCode = Literal[
    # Max number of tokens were exceeded in the prompt
    "max_tokens_exceeded",
    # The model failed to generate a response
    "failed_generation",
    # The model generated a response but it was not valid
    "invalid_generation",
    # The model returned an error that we currently do not handle
    # The returned status code will match the provider status code and the entire
    # provider response will be provided the error details.
    #
    # This error is intended as a fallback since we do not control what the providers
    # return. We track this error on our end and the error should eventually
    # be assigned a different status code
    "unknown_provider_error",
    # The provider returned a rate limit error
    "rate_limit",
    # The provider returned a server overloaded error
    "server_overloaded",
    # The requested provider does not support the model
    "invalid_provider_config",
    # The provider returned a 500
    "provider_internal_error",
    # The provider returned a 502 or 503
    "provider_unavailable",
    # The request timed out
    "read_timeout",
    # The requested model does not support the requested generation mode
    # (e-g a model that does not support images generation was sent an image)
    "model_does_not_support_mode",
    # Invalid file provided
    "invalid_file",
    # The maximum number of tool call iterations was reached
    "max_tool_call_iteration",
    # The current configuration does not support structured generation
    "structured_generation_error",
    # The content was moderated
    "content_moderation",
    # Task banned
    "task_banned",
    # The request timed out
    "timeout",
    # Agent run failed
    "agent_run_failed",
    # The request was invalid
    "bad_request",
    # The requested provider does not support the model
    "missing_model",
]

ErrorCode = (
    ProviderErrorCode
    | Literal[
        # The object was not found
        "object_not_found",
        # Agent version not found
        "version_not_found",
        # Agent not found
        "agent_not_found",
        # Agent input not found
        "agent_input_not_found",
        # Agent run not found
        "agent_run_not_found",
        # Example not found
        "example_not_found",
        # Schema not found
        "schema_not_found",
        # Score not found
        "score_not_found",
        # Evaluator not found
        "evaluator_not_found",
        # Organization not found
        "organization_not_found",
        # Config not found
        "config_not_found",
        # There are no configured providers supporting the requested model
        # This error will never happen when using WorkflowAI keys
        "no_provider_supporting_model",
        # The requested provider does not support the model
        "provider_does_not_support_model",
        # Run properties are invalid, for example the model does not exist
        "invalid_run_properties",
        # An internal error occurred
        "internal_error",
        # The request was invalid
        "bad_request",
        # A file url that was provided is not available
        "invalid_file",
        # The entity is too large
        "entity_too_large",
        # The JSON schema is invalid
        "unsupported_json_schema",
        # The credit card is invalid
        "card_validation_error",
        # The payment failed
        "payment_failed",
    ]
)


class ErrorResponse(BaseModel):
    class Error(BaseModel):
        title: str | None = None
        details: dict[str, Any] | None = None
        message: str = ""
        status_code: int = 0
        code: ErrorCode | str = ""

    error: Error

    # Aliased to id to match the task run payload
    task_run_id: str | None = Field(alias="id", default=None)

    task_output: dict[str, Any] | None = None

    @classmethod
    def internal_error(cls, msg: str = "An unexpected error occurred"):
        return cls(error=cls.Error(details={}, message=msg, status_code=500, code="internal_error"))

    @classmethod
    def with_status_code(cls, status_code: int, msg: str, code: ErrorCode, details: dict[str, Any] | None = None):
        return cls(error=cls.Error(details=details, message=msg, status_code=status_code, code=code))
