from abc import abstractmethod
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from typing import TypeVar

import httpx
from httpx import USE_CLIENT_DEFAULT, Response
from pydantic import BaseModel
from typing_extensions import override

from core.domain.errors import InternalError, JSONSchemaValidationError
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.structured_output import StructuredOutput
from core.providers.base.abstract_provider import AbstractProvider, ProviderConfigVar, ProviderRequestVar, RawCompletion
from core.providers.base.provider_error import (
    ContentModerationError,
    FailedGenerationError,
    InvalidGenerationError,
    InvalidProviderConfig,
    ProviderError,
    ProviderInternalError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ReadTimeOutError,
    ServerOverloadedError,
    UnknownProviderError,
)
from core.providers.base.provider_options import ProviderOptions
from core.providers.base.streaming_context import StreamingContext
from core.utils.background import add_background_task
from core.utils.dicts import InvalidKeyPathError, set_at_keypath_str
from core.utils.streams import JSONStreamError

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


def _timeout_object(value: float):
    return httpx.Timeout(read=value, connect=10.0, pool=10.0, write=10.0)


# TODO: The fact that the HTTPXProvider class uses a plain dict as a request is blocking for OpenAIImageProvider
# Ultimately HTTPXProvider should also use a templated request type
class HTTPXProviderBase(AbstractProvider[ProviderConfigVar, ProviderRequestVar]):
    _shared_client = httpx.AsyncClient(
        # 5 minutes timeout by default
        timeout=_timeout_object(300.0),
        # max_connections are per origin
        limits=httpx.Limits(max_connections=500, max_keepalive_connections=100),
    )

    @classmethod
    async def close(cls):
        await cls._shared_client.aclose()

    @classmethod
    def _invalid_json_error(
        cls,
        response: Response | None,
        exception: Exception | None,
        raw_completion: str,
        error_msg: str,
        retry: bool = False,
    ) -> Exception:
        moderation_patterns = ["inappropriate", "offensive"]
        if "apologize" in raw_completion.lower() and any(
            pattern in raw_completion.lower() for pattern in moderation_patterns
        ):
            return ContentModerationError(retry=retry, provider_error=raw_completion)

        # Ok to have a wide catch since this is only called on failed generation
        if "sorry" in raw_completion.lower():
            return FailedGenerationError(
                msg=f"Model refused to generate a response: {raw_completion}",
                response=response,
            )
        return FailedGenerationError(msg=error_msg, raw_completion=raw_completion, retry=retry)

    def _provider_rate_limit_error(self, response: Response):
        return ProviderRateLimitError(retry_after=10, response=response)

    def _provider_timeout_error(self, response: Response):
        return ProviderTimeoutError(retry_after=10, response=response)

    def _provider_internal_error(self, response: Response):
        return ProviderInternalError(retry_after=10, response=response)

    def _server_overloaded_error(self, response: Response):
        return ServerOverloadedError(retry_after=10, response=response)

    def _provider_unavailable_error(self, response: Response):
        return ProviderInternalError(retry_after=10, response=response)

    def _unknown_error_message(self, response: Response):
        """Method called to extract the error message from the response when"""
        return f"Unknown error status {response.status_code}"

    def _unknown_error(self, response: Response) -> ProviderError:
        return UnknownProviderError(msg=self._unknown_error_message(response), response=response)

    def _handle_error_status_code(self, response: Response):
        match response.status_code:
            case 401 | 403:
                err = InvalidProviderConfig(f"Config {self._config_id} seems invalid", response=response)
                if not self._config_id:
                    # if no config id is provided, then it's the local config that is invalid
                    # so it should still log to sentry

                    self.logger.exception(err, extra={"response": response.text})
                raise err
            case 402:
                # Payment required, let's raise an invalid config so the provider pipeline knows to go to the next provider
                raise InvalidProviderConfig(
                    f"Payment required for provider {self._config_id}",
                    response=response,
                    capture=True,
                )
            case 408:
                raise self._provider_timeout_error(response)
            case 429:
                raise self._provider_rate_limit_error(response)
            case 500 | 520 | 530:
                raise self._provider_internal_error(response)
            case 502 | 503 | 522 | 524:
                raise self._provider_unavailable_error(response)
            case 529:
                raise self._server_overloaded_error(response)
            case _:
                # if no exception is raised, then it's an unknown error
                # which will be handled by the caller
                pass

    def _assign_raw_completion_response_on_error(self, raw_completion: RawCompletion, error: httpx.HTTPStatusError):
        """Set raw completion to None on status error. Usually non 200 status codes from providers means that the
        call did not succeed and we should not have a cost"""
        raw_completion.response = None

    @contextmanager
    def _wrap_errors(
        self,
        options: ProviderOptions,
        raw_completion: RawCompletion,
        finally_block: Callable[..., None] | None = None,
    ):
        """Remap errors for proper handling."""
        # TODO: this method is called in this file for completion but in httpx_provider for streaming
        try:
            yield
        except (httpx.ConnectError, httpx.ReadError) as e:
            raise ProviderUnavailableError(
                msg=f"Failed to reach provider: {e}",
                retry=True,
                capture=True,
                max_attempt_count=3,
            ) from e
        except httpx.HTTPStatusError as e:
            self._assign_raw_completion_response_on_error(raw_completion, e)
            self._handle_error_status_code(response=e.response)
            # if no exception is raised, then it's an unknown error
            raise self._unknown_error(e.response)
        except ProviderError as e:
            # Just forward provider errors
            e.provider_options = options
            e.provider = self.name()
            raise e
        except (JSONSchemaValidationError, JSONStreamError) as e:
            raise InvalidGenerationError(
                msg=f"Model failed to generate a valid json: {e}",
                provider_status_code=200,
            ) from e
        except httpx.TimeoutException as e:
            self._get_logger().warning("Provider request timed out", extra={"request_url": e.request.url}, exc_info=e)
            raise ReadTimeOutError(retry=True, retry_after=10)
        except httpx.RemoteProtocolError:
            raise ProviderInternalError(msg="Provider has disconnected without sending a response.", retry_after=10)
        finally:
            if finally_block:
                finally_block()

    @asynccontextmanager
    async def _open_client(self, url: str):
        # We don't open or close the client here
        # Since we re-use them from a shared pool
        yield self._shared_client

    @classmethod
    def timeout_or_default(cls, value: float | None):
        if not value:
            return USE_CLIENT_DEFAULT
        return _timeout_object(value)

    @classmethod
    def _initial_usage(cls, messages: list[MessageDeprecated]) -> LLMUsage:
        image_count = 0
        has_audio = False
        for m in messages:
            if m.files:
                for f in m.files:
                    if f.is_image or f.is_pdf:
                        image_count += 1
                    if f.is_audio:
                        has_audio = True
        usage = LLMUsage(prompt_image_count=image_count)
        if not has_audio:
            usage.prompt_audio_duration_seconds = 0
            usage.prompt_audio_token_count = 0
        return usage

    async def _extract_and_log_rate_limits(self, response: Response, options: ProviderOptions):
        """Use _log_rate_limit from the base class to track rate limits"""
        pass

    @abstractmethod
    async def _execute_request(self, request: ProviderRequestVar, options: ProviderOptions) -> Response:
        pass

    @abstractmethod
    def _parse_response(
        self,
        response: Response,
        output_factory: Callable[[str, bool], StructuredOutput],
        raw_completion: RawCompletion,
        request: ProviderRequestVar,
    ) -> StructuredOutput:
        pass

    def _assign_usage_from_structured_output(self, raw_completion: RawCompletion, structured_output: StructuredOutput):
        if raw_completion.usage.completion_image_count is None:
            raw_completion.usage.completion_image_count = len(structured_output.files) if structured_output.files else 0

    @override
    async def _single_complete(
        self,
        request: ProviderRequestVar,
        output_factory: Callable[[str, bool], StructuredOutput],
        raw_completion: RawCompletion,
        options: ProviderOptions,
    ) -> StructuredOutput:
        with self._wrap_errors(options=options, raw_completion=raw_completion):
            response = await self._execute_request(request, options)
            response.raise_for_status()
            add_background_task(self._extract_and_log_rate_limits(response, options=options))
            parsed_response = self._parse_response(
                response,
                output_factory=output_factory,
                raw_completion=raw_completion,
                request=request,
            )
            self._assign_usage_from_structured_output(raw_completion, parsed_response)
            return parsed_response

    def _handle_chunk_output(self, context: StreamingContext, content: str) -> bool:
        updates = context.streamer.process_chunk(content)
        if not updates:
            return False

        for keypath, value in updates:
            try:
                set_at_keypath_str(context.agg_output, keypath, value)
            except InvalidKeyPathError as e:
                raise InternalError(
                    f"Invalid keypath in stream: {e}",
                    extras={
                        "aggregate": context.streamer.aggregate,
                        "output": context.agg_output,
                        "keypath": keypath,
                        "value": value,
                    },
                ) from e
        return True

    # TODO: we should likely handle streaming here as well, maybe when we merge this class
    # with httpx_provider.py

    async def check_valid(self) -> bool:
        options = ProviderOptions(model=self.default_model(), max_tokens=100, temperature=0)

        try:
            await self.complete(
                messages=[MessageDeprecated(role=MessageDeprecated.Role.USER, content="Respond with an empty json")],
                options=options,
                output_factory=lambda x, _: StructuredOutput(x),
            )
            return True
        except InvalidProviderConfig:
            return False
