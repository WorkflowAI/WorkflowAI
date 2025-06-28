import datetime

import pytest

from core.domain.models import Model, Provider

from .model_provider_data import (
    LifecycleData,
    ModelProviderData,
    TextPricePerToken,
)
from .model_provider_data_mapping import (
    MODEL_PROVIDER_DATAS,
    ProviderDataByModel,
    ProviderModelDataMapping,
)


def assert_model_and_provider_are_in_mapping(
    mapping: ProviderModelDataMapping,
    provider: Provider,
    model: Model,
):
    assert provider in mapping, f"Provider {provider} not found in mapping"
    assert model in mapping[provider], f"Model {model} not found in mapping for provider {provider}"


def test_assert_model_is_in_mapping_should_not_raise() -> None:
    assert_model_and_provider_are_in_mapping(
        mapping={
            Provider.GOOGLE: {
                Model.GEMINI_1_5_PRO_PREVIEW_0514: ModelProviderData(
                    text_price=TextPricePerToken(
                        prompt_cost_per_token=0.000005,
                        completion_cost_per_token=0.000015,
                        source="https://cloud.google.com/vertex-ai/generative-ai/pricing",
                    ),
                ),
            },
        },
        provider=Provider.GOOGLE,
        model=Model.GEMINI_1_5_PRO_PREVIEW_0514,
    )


def test_assert_model_is_in_mapping_should_raise_when_provider_is_missing() -> None:
    with pytest.raises(AssertionError):
        assert_model_and_provider_are_in_mapping(
            mapping={
                Provider.GOOGLE: {
                    Model.GEMINI_1_5_PRO_PREVIEW_0514: ModelProviderData(
                        text_price=TextPricePerToken(
                            prompt_cost_per_token=0.000005,
                            completion_cost_per_token=0.000015,
                            source="https://cloud.google.com/vertex-ai/generative-ai/pricing",
                        ),
                    ),
                },
            },
            provider=Provider.OPEN_AI,
            model=Model.GPT_4O_2024_05_13,
        )


def test_assert_model_is_in_mapping_should_raise_when_model_is_missing() -> None:
    with pytest.raises(AssertionError):
        assert_model_and_provider_are_in_mapping(
            mapping={
                Provider.GOOGLE: {
                    Model.GEMINI_1_5_PRO_PREVIEW_0514: ModelProviderData(
                        text_price=TextPricePerToken(
                            prompt_cost_per_token=0.000005,
                            completion_cost_per_token=0.000015,
                            source="https://cloud.google.com/vertex-ai/generative-ai/pricing",
                        ),
                    ),
                },
            },
            provider=Provider.GOOGLE,
            model=Model.GEMINI_1_5_FLASH_PREVIEW_0514,
        )


def test_MODEL_PROVIDER_DATAS_thresholded_prices_only_contain_one_price() -> None:
    """
    We do not support multiple thresholded prices for now
    """
    for provider in MODEL_PROVIDER_DATAS:
        for model in MODEL_PROVIDER_DATAS[provider]:
            model_provider_data = MODEL_PROVIDER_DATAS[provider][model]

            if model_provider_data.text_price.thresholded_prices is not None:
                assert len(model_provider_data.text_price.thresholded_prices) == 1, (
                    f"Thresholded prices for {provider} {model} should only contain one price"
                )

            if model_provider_data.image_price and model_provider_data.image_price.thresholded_prices is not None:
                assert len(model_provider_data.image_price.thresholded_prices) == 1, (
                    f"Thresholded image prices for {provider} {model} should only contain one price"
                )


class TestSunsetModels:
    @pytest.fixture
    def now(self) -> datetime.date:
        # Somewhat timezone sensitive, but will be run by the CI in UTC so we should be good
        return datetime.date.today()

    def test_models_sunset_in_1_month_have_replacement_model(self, now: datetime.date):
        one_month_from_now = now + datetime.timedelta(days=30)
        for provider_data in MODEL_PROVIDER_DATAS.values():
            for model, model_data in provider_data.items():
                if model_data.lifecycle_data and model_data.lifecycle_data.is_sunset(one_month_from_now):
                    assert model_data.replacement_model(one_month_from_now), (
                        f"Model {model} should have a replacement model"
                    )

    @pytest.mark.parametrize("provider_data", MODEL_PROVIDER_DATAS.values())
    def test_sunset_models_are_not_sunset(
        self,
        now: datetime.date,
        provider_data: ProviderDataByModel,
    ):
        for data in provider_data.values():
            if replacement_model := data.replacement_model(now):
                replacement_data = provider_data[replacement_model]
                assert not (replacement_data.lifecycle_data and replacement_data.lifecycle_data.is_sunset(now))


class TestReplacementModels:
    @pytest.fixture
    def model_data(self):
        return ModelProviderData(
            text_price=TextPricePerToken(
                prompt_cost_per_token=0.000_005,
                completion_cost_per_token=0.000_015,
                source="https://openai.com/api/pricing/",
            ),
            lifecycle_data=LifecycleData(
                sunset_date=datetime.date(2023, 12, 31),
                post_sunset_replacement_model=Model.GPT_3_5_TURBO_1106,
                source="",
            ),
        )

    def test_model_available_before_sunset_date(self, model_data: ModelProviderData):
        current_date = datetime.date(2023, 6, 1)
        replacement_model = model_data.replacement_model(current_date)
        assert replacement_model is None

    def test_model_not_available_after_sunset_date(self, model_data: ModelProviderData):
        current_date = datetime.date(2024, 1, 1)
        replacement_model = model_data.replacement_model(current_date)
        assert replacement_model == Model.GPT_3_5_TURBO_1106

    def test_model_not_available_on_sunset_date(self, model_data: ModelProviderData):
        current_date = datetime.date(2023, 12, 31)
        replacement_model = model_data.replacement_model(current_date)
        assert replacement_model == Model.GPT_3_5_TURBO_1106

    def test_model_always_available_without_lifecycle_data(self):
        data = ModelProviderData(
            text_price=TextPricePerToken(
                prompt_cost_per_token=0.000_005,
                completion_cost_per_token=0.000_015,
                source="https://openai.com/api/pricing/",
            ),
        )
        assert data.replacement_model(datetime.date(2025, 12, 31)) is None
