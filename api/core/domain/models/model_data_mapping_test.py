import datetime

import pytest
from pydantic import BaseModel

from core.domain.models import Model, Provider
from core.domain.models.model_data_supports import ModelDataSupports
from core.domain.models.model_provider_data import ModelProviderData
from core.domain.models.utils import get_model_data
from core.domain.task_typology import SchemaTypology, TaskTypology
from core.providers.openai.openai_provider import OpenAIProvider

from .model_data import DeprecatedModel, FinalModelData, LatestModel, ModelData
from .model_data_mapping import MODEL_DATAS
from .model_provider_data_mapping import MODEL_PROVIDER_DATAS

_FILTERED_MODEL_DATA = sorted(
    [pytest.param(m, id=m.model.value) for m in MODEL_DATAS.values() if isinstance(m, FinalModelData)],
    key=lambda x: x.values[0].model,  # type:ignore
)


def test_MODEL_DATAS_is_exhaustive() -> None:
    """
    Test that all provider x model combinations are defined in 'MODEL_DATAS'
    """
    for model in Model:
        assert model in MODEL_DATAS


def assert_model_data_has_all_fields_defined(obj: BaseModel, exclude: set[str] | None = None) -> None:
    fields = [field for field, _ in type(obj).model_fields.items()]
    for field in fields:
        if exclude and field in exclude:
            continue
        assert getattr(obj, field) is not None, f"Field '{field}' is not defined for model {obj}"


def test_assert_model_data_has_all_fields_defined_should_not_raise() -> None:
    class Model(BaseModel):
        display_name: str
        some_other_field: str | None = None

    # Test that 'assert_model_data_has_all_fields_defined' does not raise an error when all fields are defined
    assert_model_data_has_all_fields_defined(
        Model(display_name="test", some_other_field="test"),
    )

    # Test that 'assert_model_data_has_all_fields_defined' raise an error when a field is not defined
    with pytest.raises(AssertionError):
        assert_model_data_has_all_fields_defined(
            Model(display_name="test"),
        )


@pytest.fixture
def today():
    return datetime.date.today()


class TestDeprecatedModels:
    # TODO: We should allow nested replacement and compute them at build
    def test_no_nested_replacement(self):
        # Check all replacement models do not have a replacement model themselves
        for value in MODEL_DATAS.values():
            if not isinstance(value, DeprecatedModel):
                continue

            replacement_data = MODEL_DATAS[value.replacement_model]
            assert isinstance(
                replacement_data,
                ModelData,
            ), f"Replacement model {value.replacement_model} is not a ModelData"

    def test_that_all_models_that_are_fully_sunset_have_a_replacement_model(self, today: datetime.date):
        """Check that if a model is fully sunset on all providers, it is a deprecated model and not a ModelData"""

        def _check(model: Model):
            for provider_data_by_model in MODEL_PROVIDER_DATAS.values():
                if model not in provider_data_by_model:
                    continue

                provider_data = provider_data_by_model[model]
                if provider_data.replacement_model(today) is None:
                    # We have found a model that has no replacement
                    # So the model is not sunset on all providers
                    return
            raise AssertionError(f"Model {model} is fully sunset but has no replacement model")

        for model in Model:
            model_data = MODEL_DATAS[model]
            if not isinstance(model_data, ModelData):
                continue

            _check(model)

    def test_deprecated_models_have_no_provider_data(self):
        # Check that we do not store data for non active models
        for model in Model:
            model_data = MODEL_DATAS[model]
            if isinstance(model_data, ModelData):
                continue

            for provider, provider_data_by_model in MODEL_PROVIDER_DATAS.items():
                assert model not in provider_data_by_model, (
                    f"Model {model} is deprecated but has provider data with provider {provider}"
                )


def _versioned_models():
    for model, model_data in MODEL_DATAS.items():
        if isinstance(model_data, ModelData):
            yield model, model_data


def test_openai_supported_models_use_openai_as_primary():
    found = False
    for model in OpenAIProvider.all_supported_models():
        model_data = MODEL_DATAS[model]
        if not isinstance(model_data, FinalModelData):
            continue
        found = True
        assert model_data.providers[0][0] == Provider.OPEN_AI, f"Model {model} should use OpenAI as primary provider"
    assert found


class TestProviders:
    def test_providers_is_set(self):
        for model, model_data in _versioned_models():
            assert model_data.providers, f"Providers for model {model} are not set"

    def test_providers_is_accurate(self):
        for model, model_data in _versioned_models():
            found: list[tuple[Provider, ModelProviderData]] = []
            for provider, provider_data_by_model in MODEL_PROVIDER_DATAS.items():
                if model not in provider_data_by_model:
                    continue

                provider_data = provider_data_by_model[model]
                found.append((provider, provider_data))

            for f in found:
                assert f in model_data.providers, f"Provider {f} is not in model {model} providers"


class TestImageURL:
    def test_image_url_is_set(self):
        for model, model_data in _versioned_models():
            assert model_data.icon_url, f"Icon url for model {model} is not set"

    def test_all_gemini_models_have_google_icon_url(self):
        for model, model_data in _versioned_models():
            if "gemini" in model_data.display_name.lower():
                assert "google" in model_data.icon_url, f"Icon url for model {model} is not set"

    def test_all_mistral_models_have_mistral_icon_url(self):
        for model, model_data in _versioned_models():
            if "istral" in model_data.display_name.lower():
                assert "mistral" in model_data.icon_url, f"Icon url for model {model} is not set"

    def test_all_claude_models_have_anthropic_icon_url(self):
        for model, model_data in _versioned_models():
            if "claude" in model_data.display_name.lower():
                assert "anthropic" in model_data.icon_url, f"Icon url for model {model} is not set"

    def test_all_groq_models_have_meta_icon_url(self):
        for model, model_data in _versioned_models():
            if "llama" in model_data.display_name.lower():
                assert "meta" in model_data.icon_url, f"Icon url for model {model} is not set"


class TestLatestModels:
    def test_all_latest_models_are_mapped(self):
        for model, model_data in MODEL_DATAS.items():
            if not isinstance(model_data, LatestModel):
                continue
            assert "latest" in model.value

            mapped_model = MODEL_DATAS[model_data.model]
            assert isinstance(mapped_model, ModelData), f"Mapped model {model_data.model} is not a ModelData"
            assert mapped_model.latest_model == model, f"Mapped model {model_data.model} is not the latest model"

    def test_latel_models_all_have_an_icon_url(self):
        for model, model_data in MODEL_DATAS.items():
            if not isinstance(model_data, LatestModel):
                continue
            assert model_data.icon_url, f"Icon url for model {model} is not set"

    def test_latest_model_field(self):
        # Check that all latest_model fields map to a LatestModel object
        for model, model_data in MODEL_DATAS.items():
            if not isinstance(model_data, ModelData):
                continue
            if model_data.latest_model is None:
                continue
            assert isinstance(
                MODEL_DATAS[model_data.latest_model],
                LatestModel,
            ), f"Latest model {model_data.latest_model} is not a LatestModel for model {model}"

    def test_latest_model_is_more_permissive(self):
        # Check that all latest models are more permissive than the model they replace
        # This is a sanity check because we do not want to replace a model by one that supports less to avoid breaking
        # existing tasks
        for model, model_data in MODEL_DATAS.items():
            if not isinstance(model_data, ModelData) or not model_data.latest_model:
                continue

            latest_model_data = MODEL_DATAS[model_data.latest_model]
            assert isinstance(latest_model_data, LatestModel), "sanity"

            actual_model_data = MODEL_DATAS[latest_model_data.model]

            # Extracting model_data_supports from both objects
            model_data_supports = ModelDataSupports.model_validate(model_data.model_dump()).model_dump()
            latest_model_data_supports = ModelDataSupports.model_validate(actual_model_data.model_dump()).model_dump()

            # Keys for which being more tolerant is reversed
            negative_keys = {"supports_audio_only"}

            for k, latest_model_value in latest_model_data_supports.items():
                assert isinstance(latest_model_value, bool), "sanity"
                current_model_value = model_data_supports[k]
                assert isinstance(current_model_value, bool), "sanity"

                if latest_model_value == current_model_value:
                    continue

                # If the 2 are not the same we expect the latest model to be more permissive, i-e:
                # - "true" when the property is not negative
                # - "false" when the property is negative
                is_negative = k in negative_keys

                assert latest_model_value is not is_negative, (
                    f"Latest model {model_data.latest_model} is not more permissive than model {model} for key {k}"
                )


class TestDefaultModels:
    @pytest.mark.parametrize(
        "typology",
        [
            pytest.param(
                TaskTypology(input=SchemaTypology(has_image=False, has_audio=False)),
                id="text",
            ),
            pytest.param(
                TaskTypology(input=SchemaTypology(has_image=True, has_audio=False)),
                id="image",
            ),
            pytest.param(
                TaskTypology(input=SchemaTypology(has_image=False, has_audio=True)),
                id="audio",
            ),
        ],
    )
    def test_minimum_models_per_typology(self, typology: TaskTypology):
        # Count models that support this typology
        supported_models: list[ModelData | LatestModel] = []
        for model_data in MODEL_DATAS.values():
            if isinstance(model_data, DeprecatedModel):
                continue

            if isinstance(model_data, LatestModel):
                model_data_for_check = MODEL_DATAS[model_data.model]
                assert isinstance(model_data_for_check, ModelData), "sanity"
            else:
                model_data_for_check = model_data

            if model_data_for_check.is_not_supported_reason(typology) is not None:
                continue
            supported_models.append(model_data)

        # Build description of typology for error message
        default_models = [model for model in supported_models if model.is_default]
        # Assert we have at least 3 models supporting this typology
        assert len(default_models) >= 3

    @pytest.mark.parametrize("model", list(Model)[:3])
    def test_first_three_models_are_default(self, model: Model):
        model_data = MODEL_DATAS[model]
        assert isinstance(model_data, ModelData) or isinstance(model_data, LatestModel), "sanity"
        assert model_data.is_default, f"Model {model} is not default"


class TestUniqueness:
    def test_all_models_have_unique_display_names(self):
        display_names: set[str] = set()
        for model, model_data in MODEL_DATAS.items():
            if isinstance(model_data, ModelData):
                assert model_data.display_name is not None, f"Display name for model {model} is not set"
                display_names.add(model_data.display_name)

        # Check that all display names are unique
        assert len(display_names) == len(
            [m for m in MODEL_DATAS.values() if isinstance(m, ModelData)],
        ), "Some models have duplicate display names"


class TestMaxTokens:
    def test_max_tokens_is_set(self):
        for model, model_data in MODEL_DATAS.items():
            if not isinstance(model_data, ModelData):
                continue

            assert model_data.max_tokens_data.max_tokens > 0, f"Model {model} has no max tokens"


def test_no_duplicate_aliases():
    aliases: set[str] = set()
    for model, model_data in MODEL_DATAS.items():
        if isinstance(model_data, ModelData):
            if model_data.aliases:
                for alias in model_data.aliases:
                    assert alias not in aliases, f"Alias {alias} is already defined for model {model}"
                    aliases.add(alias)


class TestModelFallback:
    _IGNORE_PRICE = {
        # Model is way to cheap so we cannot find a model that is less than 3x cheaper
        Model.GEMINI_1_5_FLASH_8B,
        Model.GEMINI_2_5_FLASH_PREVIEW_0417,
        Model.GEMINI_2_5_FLASH_PREVIEW_0520,
        Model.GEMINI_2_5_FLASH_THINKING_PREVIEW_0417,
    }

    _IGNORE_PROVIDERS = {
        # LLama is supported by vertex but we use gemini for content moderation
        Model.LLAMA_3_1_405B,
        # These models are super cheap so they fallback to a Gemini Flash lite which is alqo on google
        Model.GEMINI_1_5_FLASH_8B,
        Model.GEMINI_2_5_FLASH,
        Model.GEMINI_2_5_FLASH_PREVIEW_0520,
    }

    @pytest.mark.parametrize("model_data", _FILTERED_MODEL_DATA)
    def test_fallback_models(self, model_data: FinalModelData):
        """Check that the pricing of the fallback model is no more than twice the price of the model"""

        if not model_data.fallback:
            pytest.skip("Model has no fallback")

        fallback_models: dict[str, Model] = model_data.fallback.model_dump(exclude_none=True, exclude={"pricing_tier"})

        current_provider_data = model_data.providers[0][1]
        current_providers = set(provider for provider, _ in model_data.providers)
        current_text_price = current_provider_data.text_price

        for fallback_type, fallback_model in fallback_models.items():
            fallback_model_data = get_model_data(fallback_model)
            assert isinstance(fallback_model_data, FinalModelData), "sanity"

            assert fallback_model_data.model != model_data.model, (
                "Fallback model should be different from the current model"
            )

            # ------------------------------------------------------------
            # Check providers

            if model_data.model not in self._IGNORE_PROVIDERS:
                # Check that the first provider is not in any of the current providers
                assert fallback_model_data.providers[0][0] not in current_providers, (
                    f"Fallback model {fallback_model} has the same provider as the current model {model_data.model}"
                )

            # ------------------------------------------------------------
            # Check context exceeded
            if fallback_type == "context_exceeded":
                assert fallback_model_data.max_tokens_data.max_tokens >= 2 * model_data.max_tokens_data.max_tokens, (
                    f"Fallback model {fallback_model} has a lower than twice themax tokens than the current model {model_data.model}"
                )

            # ------------------------------------------------------------
            # Check supports

            # TODO: fix missing support for pdf and audio
            missing_supports = fallback_model_data.missing_io_supports(
                model_data,
                # OpenAI does not support Audio :(
                exclude={"supports_input_pdf", "supports_input_audio"},
            )

            assert not missing_supports, f"Model {fallback_model} is missing io supports: {missing_supports}"

            # ------------------------------------------------------------
            # Check price

            fallback_text_price = fallback_model_data.providers[0][1].text_price

            max_price = 2 * current_text_price.prompt_cost_per_token

            # We never ignore the price for rate limit
            if model_data.model in self._IGNORE_PRICE and fallback_type not in {"rate_limit", "default"}:
                assert model_data.fallback.pricing_tier == "cheapest", (
                    "Fallback pricing tier should be cheapest when pricing is ignored"
                )
            else:
                assert fallback_text_price.prompt_cost_per_token <= max_price, (
                    f"Fallback model {fallback_model} has a higher prompt cost per token than the current model {model_data.model}"
                )
