import copy
from datetime import datetime
from typing import Any, Literal, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.domain.models import Model, Provider
from core.domain.models.model_data import FinalModelData, ModelData, ModelFallback
from core.domain.models.model_provider_data import ModelProviderData
from core.domain.task_typology import TaskTypology
from core.domain.tenant_data import ProviderSettings
from core.providers.base.abstract_provider import AbstractProvider
from core.providers.base.config import ProviderConfig
from core.providers.base.provider_error import (
    ContentModerationError,
    FailedGenerationError,
    MaxTokensExceededError,
    ProviderError,
    ProviderRateLimitError,
    UnknownProviderError,
)
from core.providers.factory.abstract_provider_factory import AbstractProviderFactory
from core.providers.factory.local_provider_factory import LocalProviderFactory
from core.runners.workflowai.provider_pipeline import ProviderPipeline, ProviderPipelineBuilder
from core.runners.workflowai.workflowai_options import WorkflowAIRunnerOptions
from tests import models as test_models


@pytest.fixture
def provider_builder():
    builder = Mock(spec=ProviderPipelineBuilder)
    # Last argument is the model data
    builder.side_effect = lambda *args: (args[0], Mock(), Mock(), args[1])  # type: ignore
    return builder


def _mock_provider(name: Provider, complete_side_effect: Any | None = None) -> Mock:
    mock = Mock(spec=AbstractProvider)
    mock.name.return_value = name
    mock.completion = AsyncMock()
    if complete_side_effect is not None:
        mock.complete.side_effect = complete_side_effect
    return mock


def _final_model_data(
    providers: list[Provider],
    model: Model = Model.DEEPSEEK_R1_2501,
    fallback: ModelFallback | None = None,
):
    model_data = test_models.model_data()
    final = FinalModelData.model_validate(
        {
            **model_data.model_dump(),
            "model": model,
            "quality_index": model_data.quality_data.quality_index({}),
            "speed_index": model_data.speed_data.speed_index({}),
            "fallback": fallback,
            "providers": [],
        },
    )
    # Setting to bypass validation
    provider_model_data = Mock(spec=ModelProviderData)
    provider_model_data.override.side_effect = lambda data: data  # type: ignore
    final.providers = [(p, provider_model_data) for p in providers]
    return final


def _provider_settings(provider: Provider) -> ProviderSettings:
    _mock = Mock()
    _mock.provider = provider

    class MockProviderSettings(ProviderSettings):
        def decrypt(self) -> ProviderConfig:
            return _mock

    return MockProviderSettings(
        id="123",
        created_at=datetime.now(),
        provider=provider,
    )


def _build_pipeline(
    provider_builder: Mock,
    mock_provider_factory: Mock,
    model: Model = Model.GPT_4O_MINI_2024_07_18,
    providers: list[Provider] | None = None,
    fallback: ModelFallback | None = None,
    forced_provider: Provider | None = None,
    custom_configs: list[ProviderSettings] | None = None,
    use_fallback: Literal["never", "auto"] | list[Model] | None = None,
    is_structured_generation_enabled: bool | None = None,
):
    if providers is None:
        providers = [Provider.OPEN_AI, Provider.AZURE_OPEN_AI]

    if fallback is None:
        fallback = ModelFallback(
            content_moderation=Model.CLAUDE_4_OPUS_20250514,
            structured_output=Model.CLAUDE_4_OPUS_20250514,
            rate_limit=Model.CLAUDE_4_OPUS_20250514,
            context_exceeded=Model.CLAUDE_4_OPUS_20250514,
        )

    model_data = _final_model_data(
        model=model,
        providers=providers,
        fallback=fallback,
    )
    with patch(
        "core.runners.workflowai.provider_pipeline.get_model_data",
        return_value=model_data,
    ):
        return ProviderPipeline(
            options=WorkflowAIRunnerOptions(
                model=model,
                provider=forced_provider,
                is_structured_generation_enabled=is_structured_generation_enabled,
                instructions="",
            ),
            custom_configs=custom_configs,
            builder=provider_builder,
            factory=mock_provider_factory,
            typology=TaskTypology(),
            use_fallback=copy.deepcopy(use_fallback) if use_fallback is not None else None,
        )


# TODO: The tests are based on the real model data, we should patch
class TestProviderIterator:
    def test_claude_ordering_and_support(self, provider_builder: Mock):
        pipeline = ProviderPipeline(
            options=WorkflowAIRunnerOptions(
                model=Model.CLAUDE_3_5_SONNET_20241022,
                provider=None,
                is_structured_generation_enabled=None,
                instructions="",
            ),
            custom_configs=None,
            builder=provider_builder,
            factory=LocalProviderFactory(),
            typology=TaskTypology(),
        )

        # List all providers
        providers = list(pipeline.provider_iterator())
        assert len(providers) == 2

        assert provider_builder.call_count == 2

        provider_1 = provider_builder.call_args_list[0].args[0]
        assert provider_1.name() == Provider.ANTHROPIC
        # Testing the override
        assert providers[0][-1].supports_input_pdf

        provider_2 = provider_builder.call_args_list[1].args[0]
        assert provider_2.name() == Provider.AMAZON_BEDROCK
        assert not providers[1][-1].supports_input_pdf

    def test_multiple_providers_forced_provider(self, provider_builder: Mock):
        mock_provider_factory = Mock(spec=AbstractProviderFactory)
        # Mock multiple providers of the same type
        mock_provider1 = _mock_provider(Provider.OPEN_AI)
        mock_provider2 = _mock_provider(Provider.OPEN_AI)
        mock_provider_factory.get_providers.return_value = [mock_provider1, mock_provider2]

        """Check that the providers are iterated correctly when a forced provider is set"""
        # Create a model that has multiple providers of the same type
        pipeline = ProviderPipeline(
            options=WorkflowAIRunnerOptions(
                model=Model.GPT_4O_MINI_2024_07_18,
                provider=Provider.OPEN_AI,
                is_structured_generation_enabled=None,
                instructions="",
            ),
            custom_configs=None,
            builder=provider_builder,
            factory=mock_provider_factory,
            typology=TaskTypology(),
        )

        # List all providers
        # By setting the errors we force the pipeline to try all providers
        pipeline.errors = [ProviderRateLimitError()]
        providers = list(pipeline.provider_iterator())
        mock_provider_factory.get_providers.assert_called_once_with(Provider.OPEN_AI)
        assert len(providers) == 2

        assert provider_builder.call_count == 2

        # First provider should be tried first (non-round-robin behavior)
        provider_1 = provider_builder.call_args_list[0].args[0]
        assert provider_1 == mock_provider1

        provider_2 = provider_builder.call_args_list[1].args[0]
        assert provider_2 == mock_provider2

    @patch("random.shuffle")
    def test_round_robin_providers(
        self,
        mock_shuffle: Mock,
        provider_builder: Mock,
    ):
        """Test that providers with a full round robin are shuffled"""
        # Mock multiple providers of the same type
        mock_provider_factory = Mock(spec=AbstractProviderFactory)
        mock_provider1 = _mock_provider(Provider.FIREWORKS)
        mock_provider2 = _mock_provider(Provider.FIREWORKS)
        mock_provider3 = _mock_provider(Provider.FIREWORKS)
        mock_provider_factory.get_providers.return_value = [mock_provider1, mock_provider2, mock_provider3]

        mock_shuffle.side_effect = lambda providers: providers.reverse()  # type: ignore

        # Create a model that has multiple providers of the same type
        with patch(
            "core.runners.workflowai.provider_pipeline.get_model_data",
            return_value=_final_model_data(providers=[Provider.FIREWORKS]),
        ):
            pipeline = ProviderPipeline(
                options=WorkflowAIRunnerOptions(
                    model=Model.DEEPSEEK_R1_2501,
                    provider=None,
                    is_structured_generation_enabled=None,
                    instructions="",
                ),
                custom_configs=None,
                builder=provider_builder,
                factory=mock_provider_factory,
                typology=TaskTypology(),
            )

        # List all providers
        # By setting the errors we force the pipeline to try all providers
        pipeline.errors = [ProviderRateLimitError()]
        # Can't use list comprehension since it will raise at the end
        providers: list[Any] = []
        with pytest.raises(ProviderRateLimitError):
            for provider, _, _, _ in pipeline.provider_iterator():
                providers.append(provider)

        # For round-robin providers, all providers should be shuffled
        assert providers == [mock_provider3, mock_provider2, mock_provider1]
        mock_provider_factory.get_providers.assert_called_once_with(Provider.FIREWORKS)
        mock_shuffle.assert_called_once()

        assert provider_builder.call_count == 3

    def test_mixed_provider_types(
        self,
        provider_builder: Mock,
        mock_provider_factory: Mock,
    ):
        # Create a model that has multiple providers of different types
        with patch(
            "core.runners.workflowai.provider_pipeline.get_model_data",
            return_value=_final_model_data(providers=[Provider.OPEN_AI, Provider.AZURE_OPEN_AI]),
        ):
            pipeline = ProviderPipeline(
                options=WorkflowAIRunnerOptions(
                    model=Model.GPT_4O_MINI_2024_07_18,
                    provider=None,  # So we will be using Azure and OpenAI
                    is_structured_generation_enabled=None,
                    instructions="",
                ),
                custom_configs=None,
                builder=provider_builder,
                factory=mock_provider_factory,
                typology=TaskTypology(),
            )

        # Mock multiple providers of different types
        mock_provider1 = _mock_provider(Provider.OPEN_AI)
        mock_provider2 = _mock_provider(Provider.OPEN_AI)
        mock_provider3 = _mock_provider(Provider.AZURE_OPEN_AI)
        mock_provider4 = _mock_provider(Provider.AZURE_OPEN_AI)

        # Mock the factory to return different providers based on type
        def get_providers(provider_type: Provider) -> list[Mock]:
            if provider_type == Provider.OPEN_AI:
                return [mock_provider1, mock_provider2]
            if provider_type == Provider.AZURE_OPEN_AI:
                return [mock_provider3, mock_provider4]
            return []

        mock_provider_factory.get_providers.side_effect = get_providers

        # List all providers
        # By setting the errors we force the pipeline to try all providers
        pipeline.errors = [ProviderRateLimitError()]
        provider_names: list[Provider] = []
        with pytest.raises(ProviderRateLimitError):
            for provider, _, _, _ in pipeline.provider_iterator():
                provider_names.append(provider.name())

        assert provider_names == [Provider.OPEN_AI, Provider.OPEN_AI, Provider.AZURE_OPEN_AI, Provider.AZURE_OPEN_AI]

        assert provider_builder.call_count == 4

        # First OpenAI provider should be tried first (non-round-robin)
        provider_1 = provider_builder.call_args_list[0].args[0]
        assert provider_1 == mock_provider1

        # Second OpenAI provider should be tried second
        provider_2 = provider_builder.call_args_list[1].args[0]
        assert provider_2 == mock_provider2

        # Fireworks providers should be shuffled
        provider_3 = provider_builder.call_args_list[2].args[0]
        provider_4 = provider_builder.call_args_list[3].args[0]
        assert {provider_3, provider_4} == {mock_provider3, mock_provider4}

    def test_custom_configs_with_unsupported_provider(self, provider_builder: Mock, mock_provider_factory: Mock):
        """Check that a custom config is not returned if the provider is not supported"""
        mock_provider_factory.build_provider.side_effect = lambda *args, **kwargs: _mock_provider(args[0].provider)  # type: ignore
        mock_provider_factory.get_providers.side_effect = lambda provider: [_mock_provider(provider)]  # type: ignore

        pipeline = ProviderPipeline(
            options=WorkflowAIRunnerOptions(
                model=Model.GPT_4O_MINI_2024_07_18,
                provider=None,
                is_structured_generation_enabled=None,
                instructions="",
            ),
            custom_configs=[
                _provider_settings(Provider.GROQ),
                _provider_settings(Provider.OPEN_AI),
            ],
            builder=provider_builder,
            factory=mock_provider_factory,
            typology=TaskTypology(),
        )

        providers = list(pipeline.provider_iterator())
        assert len(providers) == 3
        names = [p[0].name() for p in providers]
        assert names == [Provider.OPEN_AI, Provider.OPEN_AI, Provider.AZURE_OPEN_AI]

    @pytest.mark.parametrize(
        "use_fallback, extra_yield",
        [
            pytest.param("never", [], id="never"),
            pytest.param("auto", [(Provider.ANTHROPIC, Model.CLAUDE_4_OPUS_20250514)], id="auto"),
            pytest.param(None, [(Provider.ANTHROPIC, Model.CLAUDE_4_OPUS_20250514)], id="None"),
            pytest.param(
                # Deepseek will raise
                [Model.DEEPSEEK_R1_2501, Model.GEMINI_2_0_FLASH_001],
                [
                    (Provider.FIREWORKS, Model.DEEPSEEK_R1_2501),
                    (Provider.GOOGLE, Model.GEMINI_2_0_FLASH_001),
                ],
                id="list with first model raising",
            ),
            pytest.param(
                # Haiku will not raise
                [Model.CLAUDE_3_5_HAIKU_20241022, Model.GEMINI_2_0_FLASH_001],
                [
                    (Provider.ANTHROPIC, Model.CLAUDE_3_5_HAIKU_20241022),
                ],
                id="list with first model success",
            ),
        ],
    )
    @pytest.mark.parametrize("error_cls", [ProviderRateLimitError, UnknownProviderError])
    async def test_model_fallback_provider_then_model(
        self,
        provider_builder: Mock,
        mock_provider_factory: Mock,
        error_cls: type[ProviderError],
        use_fallback: Literal["never", "auto"] | list[Model] | None,
        extra_yield: list[tuple[Provider, Model]],
    ):
        """Test model fallback when the error that is raised allow a provider fallback"""
        with patch(
            "core.runners.workflowai.provider_pipeline.get_model_data",
            return_value=_final_model_data(
                model=Model.GPT_4O_MINI_2024_07_18,
                providers=[Provider.OPEN_AI, Provider.AZURE_OPEN_AI],
                # Anthropic fallback
                fallback=ModelFallback(
                    content_moderation=Model.CLAUDE_4_OPUS_20250514,
                    structured_output=Model.CLAUDE_4_OPUS_20250514,
                    rate_limit=Model.CLAUDE_4_OPUS_20250514,
                    context_exceeded=None,
                ),
            ),
        ):
            pipeline = ProviderPipeline(
                options=WorkflowAIRunnerOptions(
                    model=Model.GPT_4O_MINI_2024_07_18,
                    provider=None,
                    is_structured_generation_enabled=None,
                    instructions="",
                ),
                custom_configs=None,
                builder=provider_builder,
                factory=mock_provider_factory,
                typology=TaskTypology(),
                use_fallback=copy.deepcopy(use_fallback),
            )

        def _get_providers(provider_type: Provider) -> list[AbstractProvider[Any, Any]]:
            match provider_type:
                case Provider.AZURE_OPEN_AI | Provider.OPEN_AI | Provider.FIREWORKS:
                    return [_mock_provider(provider_type, complete_side_effect=error_cls())]
                case Provider.ANTHROPIC | Provider.GOOGLE:
                    return [_mock_provider(provider_type, complete_side_effect=lambda: "test")]
                case _:
                    assert False, f"Unexpected provider type: {provider_type}"

        mock_provider_factory.get_providers.side_effect = _get_providers

        yielded: list[tuple[Provider, ModelData]] = []
        for provider, _, _, model_data in pipeline.provider_iterator(raise_at_end=False):
            yielded.append((provider.name(), model_data.model))  # type: ignore

            with pipeline.wrap_provider_call(provider):
                # Re-raise if an exception or break the loop
                try:
                    await cast(Mock, provider).complete()
                except Exception:
                    raise
                break

        assert yielded == [
            (Provider.OPEN_AI, Model.GPT_4O_MINI_2024_07_18),
            (Provider.AZURE_OPEN_AI, Model.GPT_4O_MINI_2024_07_18),
            *extra_yield,
        ]

    @pytest.mark.parametrize("error_cls", [ContentModerationError, FailedGenerationError, MaxTokensExceededError])
    async def test_model_fallback_failed_generation(
        self,
        provider_builder: Mock,
        mock_provider_factory: Mock,
        error_cls: type[ProviderError],
    ):
        """Test model fallback when the error that is raised does not allow a provider fallback"""
        with patch(
            "core.runners.workflowai.provider_pipeline.get_model_data",
            return_value=_final_model_data(
                model=Model.GPT_4O_MINI_2024_07_18,
                providers=[Provider.OPEN_AI, Provider.AZURE_OPEN_AI],
                # Anthropic fallback
                fallback=ModelFallback(
                    content_moderation=Model.CLAUDE_4_OPUS_20250514,
                    structured_output=Model.CLAUDE_4_OPUS_20250514,
                    rate_limit=Model.CLAUDE_4_OPUS_20250514,
                    context_exceeded=Model.CLAUDE_4_OPUS_20250514,
                ),
            ),
        ):
            pipeline = ProviderPipeline(
                options=WorkflowAIRunnerOptions(
                    model=Model.GPT_4O_MINI_2024_07_18,
                    provider=None,
                    is_structured_generation_enabled=None,
                    instructions="",
                ),
                custom_configs=None,
                builder=provider_builder,
                factory=mock_provider_factory,
                typology=TaskTypology(),
            )

        mock_provider1 = _mock_provider(Provider.OPEN_AI)
        mock_provider1.complete.side_effect = error_cls()
        mock_provider2 = _mock_provider(Provider.OPEN_AI)
        mock_provider2.complete.side_effect = error_cls()
        mock_provider3 = _mock_provider(Provider.ANTHROPIC)
        mock_provider3.complete.return_value = "test"

        def _get_providers(provider_type: Provider) -> list[AbstractProvider[Any, Any]]:
            match provider_type:
                case Provider.OPEN_AI:
                    # Only mock_provider2 will be called
                    return [mock_provider2, mock_provider1]
                case Provider.ANTHROPIC:
                    return [mock_provider3]
                case _:
                    assert False, f"Unexpected provider type: {provider_type}"

        mock_provider_factory.get_providers.side_effect = _get_providers

        yielded: list[tuple[Provider, ModelData]] = []
        for provider, _, _, model_data in pipeline.provider_iterator():
            yielded.append((provider.name(), model_data.model))  # type: ignore

            with pipeline.wrap_provider_call(provider):
                # Re-raise if an exception or break the loop
                try:
                    await cast(Mock, provider).complete()
                except Exception:
                    raise
                break

        assert yielded == [
            (Provider.OPEN_AI, Model.GPT_4O_MINI_2024_07_18),
            (Provider.ANTHROPIC, Model.CLAUDE_4_OPUS_20250514),
        ]
        mock_provider1.complete.assert_not_called()

    async def _run_pipeline(
        self,
        pipeline: ProviderPipeline,
        raise_at_end: bool = False,
        return_full_data: bool = False,
        stop_on_success: bool = True,
    ):
        yielded: list[tuple[Provider, Any, Any, ModelData]] | list[tuple[Provider, Model]] = []

        for provider, config, provider_data, model_data in pipeline.provider_iterator(raise_at_end=raise_at_end):
            if return_full_data:
                yielded.append((provider.name(), config, provider_data, model_data))  # type: ignore
            else:
                yielded.append((provider.name(), model_data.model))  # type: ignore

            with pipeline.wrap_provider_call(provider):
                try:
                    await cast(Mock, provider).complete()
                    if stop_on_success:
                        break
                except Exception:
                    raise

        return yielded

    async def test_no_infinite_loop_on_fallback_model_failure(
        self,
        provider_builder: Mock,
        mock_provider_factory: Mock,
    ):
        """Test that we don't get an infinite loop when a fallback model keeps failing with the same error"""

        pipeline = _build_pipeline(provider_builder, mock_provider_factory)

        # Mock providers that always fail with rate limit
        mock_openai = _mock_provider(Provider.OPEN_AI)
        mock_openai.complete.side_effect = FailedGenerationError()
        mock_anthropic = _mock_provider(Provider.ANTHROPIC)
        mock_anthropic.complete.side_effect = FailedGenerationError()

        def _get_providers(provider_type: Provider) -> list[AbstractProvider[Any, Any]]:
            match provider_type:
                case Provider.OPEN_AI:
                    return [mock_openai]
                case Provider.ANTHROPIC:
                    return [mock_anthropic]
                case _:
                    assert False, f"Unexpected provider type: {provider_type}"

        mock_provider_factory.get_providers.side_effect = _get_providers

        yielded = await self._run_pipeline(pipeline)

        # Should try:
        # 1. GPT-4 on OpenAI (fails with rate limit)
        # 2. Claude fallback on Anthropic (fails with rate limit)
        assert yielded == [
            (Provider.OPEN_AI, Model.GPT_4O_MINI_2024_07_18),
            (Provider.ANTHROPIC, Model.CLAUDE_4_OPUS_20250514),
        ]

        # Verify each provider was only called once
        mock_openai.complete.assert_called_once()
        mock_anthropic.complete.assert_called_once()
