import logging
import random
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any, NoReturn, Protocol

from core.domain.error_response import ProviderErrorCode
from core.domain.errors import InternalError, NoProviderSupportingModelError, ProviderError, StructuredGenerationError
from core.domain.models.model_data import FinalModelData, ModelData
from core.domain.models.providers import Provider
from core.domain.models.utils import get_model_data
from core.domain.tenant_data import ProviderSettings
from core.providers.base.abstract_provider import AbstractProvider
from core.providers.base.provider_options import ProviderOptions
from core.providers.factory.abstract_provider_factory import AbstractProviderFactory
from core.runners.workflowai.templates import TemplateName
from core.runners.workflowai.workflowai_options import WorkflowAIRunnerOptions

PipelineProviderData = tuple[AbstractProvider[Any, Any], TemplateName, ProviderOptions, ModelData]


class ProviderPipelineBuilder(Protocol):
    def __call__(
        self,
        provider: AbstractProvider[Any, Any],
        model_data: FinalModelData,
        is_structured_generation_enabled: bool,
    ) -> PipelineProviderData: ...


# By default we try providers in order
# This allows maxing out the first key before attacking the following ones
# which is good to create grounds to request quota increase. The downside is that
# there is some added latency when the first providers return 429s but it should
# be minimal.
#
# However, some providers do not return an immediate 429 on quota reached but instead
# start throttling requests or treating them with a lower priority, making inference
# way longer. To circumvent that, we use a round robin strategy, aka we shuffle the array
# before iterating over it.
_round_robin_similar_providers: set[Provider] = {
    Provider.FIREWORKS,
}

_logger = logging.getLogger("ProviderPipeline")


class ProviderPipeline:
    def __init__(
        self,
        options: WorkflowAIRunnerOptions,
        custom_configs: list[ProviderSettings] | None,
        factory: AbstractProviderFactory,
        builder: ProviderPipelineBuilder,
    ):
        self._factory = factory
        self._options = options
        self.model_data = get_model_data(options.model)
        self._custom_configs = custom_configs
        self.errors: list[ProviderError] = []
        self.builder = builder
        self._force_structured_generation = options.is_structured_generation_enabled
        self._last_error_was_structured_generation = False

    @property
    def last_error_code(self) -> ProviderErrorCode | None:
        if not self.errors:
            return None
        return self.errors[-1].code

    def raise_on_end(self, task_id: str) -> NoReturn:
        # TODO: metric
        raise (
            self.errors[0]
            if self.errors
            else InternalError(
                "No provider found",
                extras={"task_id": task_id, "options": self._options.model_dump()},
            )
        )

    @contextmanager
    def wrap_provider_call(self, provider: AbstractProvider[Any, Any]):
        try:
            yield
        except StructuredGenerationError as e:
            self._last_error_was_structured_generation = True
            e.capture_if_needed()
            if self._force_structured_generation is None:
                # In this case we will retry without structured generation
                return
            raise e
        except ProviderError as e:
            e.capture_if_needed()
            self.errors.append(e)

            if provider.is_custom_config:
                # In case of custom configs, we always retry
                return

            if e.should_try_next_provider:
                # Otherwise we retry only if the error should be retried
                return

            raise e

    def _should_retry_without_structured_generation(self):
        # We pop the flag and set the force structured generation to false to
        # trigger a provider without structured gen only
        if self._last_error_was_structured_generation and self._force_structured_generation is None:
            self._force_structured_generation = False
            self._last_error_was_structured_generation = False
            return True

        return False

    def _use_structured_output(self):
        if self._force_structured_generation is not None:
            return self._force_structured_generation
        return self.model_data.supports_structured_output

    def _build(self, provider: AbstractProvider[Any, Any], model_data: FinalModelData) -> PipelineProviderData:
        return self.builder(provider, model_data, self._use_structured_output())

    def _iter_with_structured_gen(
        self,
        provider: AbstractProvider[Any, Any],
        model_data: FinalModelData,
    ) -> Iterator[PipelineProviderData]:
        yield self._build(provider, model_data)

        if self._should_retry_without_structured_generation():
            yield self._build(provider, model_data)

    def _single_provider_iterator(
        self,
        providers: Iterable[AbstractProvider[Any, Any]],
        model_data: FinalModelData,
        provider_type: Provider,
    ) -> Iterator[PipelineProviderData]:
        providers = iter(providers)
        if provider_type not in _round_robin_similar_providers:
            # We yield the first provider first in order to max out quotas
            try:
                provider = next(providers)
            except StopIteration:
                raise NoProviderSupportingModelError(model=self._options.model)
            yield from self._iter_with_structured_gen(provider, model_data)

            # No point in retrying on the same provider if the last error code was not a rate limit
            if self.last_error_code != "rate_limit":
                return

        # Then we shuffle the rest
        shuffled = list(providers)
        if not shuffled:
            return

        random.shuffle(shuffled)

        for provider in shuffled:
            # We can safely call _iter_with_structured_gen multiple times
            # if the structured generation fails the first time, the retries
            # Without the structured gen will not happen
            yield from self._iter_with_structured_gen(provider, model_data)

            # No point in retrying on the same provider if the last error code was not a rate limit
            if self.last_error_code != "rate_limit":
                return

    def _build_custom_providers(self, configs: list[ProviderSettings]) -> Iterable[AbstractProvider[Any, Any]]:
        for config in configs:
            try:
                decrypted = config.decrypt()
                provider = self._factory.build_provider(decrypted, config.id, preserve_credits=config.preserve_credits)
                yield provider
            except Exception:
                _logger.exception("Failed to build provider with custom config", extra={"config_id": config.id})
                continue

    def _custom_configs_iterator(self) -> Iterator[PipelineProviderData]:
        if not self._custom_configs:
            return

        configs_by_provider: dict[Provider, list[ProviderSettings]] = {}
        for config in self._custom_configs:
            configs_by_provider.setdefault(config.provider, []).append(config)

        for provider, configs in configs_by_provider.items():
            if not self.model_data.supported_by_provider(provider):
                pass
            yield from self._single_provider_iterator(self._build_custom_providers(configs), self.model_data, provider)

    def provider_iterator(self) -> Iterator[PipelineProviderData]:
        yield from self._custom_configs_iterator()

        if self._options.provider:
            yield from self._single_provider_iterator(
                providers=self._factory.get_providers(self._options.provider),
                model_data=self.model_data,
                provider_type=self._options.provider,
            )
            return

        for provider, provider_data in self.model_data.providers:
            # We only use the override for the default pipeline
            # We assume that
            provider_model_data = provider_data.override(self.model_data)

            yield from self._single_provider_iterator(
                providers=self._factory.get_providers(provider),
                model_data=provider_model_data,
                provider_type=provider,
            )
