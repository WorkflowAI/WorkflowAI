from datetime import date
from typing import Any

import pytest

from core.domain.errors import ProviderDoesNotSupportModelError
from core.domain.models import Model, Provider
from core.domain.models._displayed_provider import DisplayedProvider
from core.domain.models.model_data import (
    FinalModelData,
    MaxTokensData,
    ModelData,
    ModelDataMapping,
    QualityData,
)
from core.domain.models.model_provider_data import ModelProviderData, TextPricePerToken
from core.domain.task_typology import SchemaTypology, TaskTypology


@pytest.fixture(scope="session")
def model_data_mapping() -> ModelDataMapping:
    from core.domain.models.model_datas_mapping import MODEL_DATAS

    return MODEL_DATAS


def _md(**kwargs: Any) -> FinalModelData:
    """Create a basic model data object for testing is_not_supported_reason
    The base object supports json mode but that's it
    """
    base = FinalModelData(
        display_name="GPT-3.5 Turbo (1106)",
        supports_json_mode=True,
        supports_input_image=False,
        supports_input_pdf=False,
        supports_input_audio=False,
        max_tokens_data=MaxTokensData(
            max_tokens=16_385,
            max_output_tokens=4096,
            source="https://platform.openai.com/docs/models",
        ),
        provider_for_pricing=Provider.OPEN_AI,
        icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
        release_date=date(2024, 11, 6),
        quality_index=100,
        quality_data=QualityData(index=100),
        provider_name=DisplayedProvider.OPEN_AI.value,
        supports_tool_calling=False,
        model=Model.GPT_3_5_TURBO_1106,
        providers=[
            (
                Provider.OPEN_AI,
                ModelProviderData(
                    text_price=TextPricePerToken(
                        prompt_cost_per_token=0.000_003,
                        completion_cost_per_token=0.000_015,
                        source="https://aws.amazon.com/bedrock/pricing/",
                    ),
                ),
            ),
        ],
        fallback=None,
    )
    return base.model_copy(deep=True, update=kwargs)


@pytest.mark.parametrize(
    "data, task_typology, expected_result",
    [
        (
            _md(),
            TaskTypology(input=SchemaTypology(has_image=False, has_audio=False)),
            None,
        ),
        (
            _md(),
            TaskTypology(input=SchemaTypology(has_image=True, has_audio=False)),
            "GPT-3.5 Turbo (1106) does not support input images",
        ),
        (
            _md(),
            TaskTypology(input=SchemaTypology(has_image=True, has_audio=False)),
            "GPT-3.5 Turbo (1106) does not support input images",
        ),
        (
            _md(supports_input_image=True),
            TaskTypology(input=SchemaTypology(has_image=True, has_audio=False)),
            None,
        ),
        # Check when the model does not support pdf or images
        (_md(), TaskTypology(input=SchemaTypology(has_pdf=True)), "GPT-3.5 Turbo (1106) does not support input pdf"),
        # Check when the model does not support pdf but supports images
        (
            _md(supports_input_image=True, supports_input_pdf=False),
            TaskTypology(input=SchemaTypology(has_pdf=True)),
            None,
        ),
        (
            _md(),
            TaskTypology(output=SchemaTypology(has_image=True)),
            "GPT-3.5 Turbo (1106) does not support output images",
        ),
    ],
)
def test_is_model_not_supported_and_why(
    data: FinalModelData,
    task_typology: TaskTypology,
    expected_result: str | None,
) -> None:
    assert expected_result == data.is_not_supported_reason(task_typology)


class TestFinalModelData:
    def test_provider_data(self):
        m1 = ModelProviderData(
            text_price=TextPricePerToken(
                prompt_cost_per_token=0.000_003,
                completion_cost_per_token=0.000_015,
                source="https://aws.amazon.com/bedrock/pricing/",
            ),
        )
        m2 = m1.model_copy(deep=True)
        m2.text_price.prompt_cost_per_token = 0.1

        assert m1 != m2, "sanity"

        model_data = FinalModelData(
            model=Model.GPT_3_5_TURBO_1106,
            providers=[(Provider.OPEN_AI, m1), (Provider.AZURE_OPEN_AI, m2)],
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=16_385,
                max_output_tokens=4096,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2024, 11, 6),
            quality_data=QualityData(index=100),
            quality_index=100,
            provider_name=DisplayedProvider.OPEN_AI.value,
            display_name="GPT-3.5 Turbo (1106)",
            supports_tool_calling=True,
            fallback=None,
        )

        assert model_data.provider_data(Provider.OPEN_AI) == m1
        assert model_data.provider_data(Provider.AZURE_OPEN_AI) == m2

        with pytest.raises(ProviderDoesNotSupportModelError):
            model_data.provider_data(Provider.ANTHROPIC)


class TestModelDataRequestMaxOutputTokens:
    def test_request_max_output_tokens_always_set_for_model_data(self, model_data_mapping: ModelDataMapping):
        for m in model_data_mapping.values():
            if not isinstance(m, ModelData):
                continue

            # Checking that the max tokens is greater than 0
            assert m.max_tokens_data.max_tokens > 0
            # TODO[max-tokens]: We should sanitize to always have output tokens
            # assert m.max_tokens_data.max_output_tokens > 0

    def test_all_anthropic_models_have_max_output_tokens(self, model_data_mapping: ModelDataMapping):
        from core.domain.models.model_provider_datas_mapping import ANTHROPIC_PROVIDER_DATA

        for model in ANTHROPIC_PROVIDER_DATA.keys():
            model_data = model_data_mapping[model]
            assert isinstance(model_data, ModelData)
            assert model_data.max_tokens_data.max_output_tokens


class TestModelDataQualityIndex:
    @pytest.mark.parametrize(
        "quality_data, expected_index",
        [
            pytest.param(QualityData(gpqa=80), 800, id="gpqa"),
            pytest.param(QualityData(index=100), 100, id="index"),
            pytest.param(QualityData(mmlu_pro=80), 800, id="mmlu_pro"),
            pytest.param(QualityData(mmlu=80), 480, id="mmlu"),
            pytest.param(QualityData(mmlu=80, mmlu_pro=80), 640, id="mmlu_pro_and_mmlu"),
            pytest.param(
                QualityData(equivalent_to=(Model.O3_2025_04_16_MEDIUM_REASONING_EFFORT, 1)),
                101,
                id="equivalent_to",
            ),
            pytest.param(
                QualityData(
                    gpqa_diamond=100,
                    gpqa=100,
                    mmlu=100,
                    mmlu_pro=100,
                ),
                1000,
                id="max_score",
            ),
        ],
    )
    def test_quality_index(self, quality_data: QualityData, expected_index: int):
        mapping = {
            Model.O3_2025_04_16_MEDIUM_REASONING_EFFORT: _md(quality_data=QualityData(index=100)),
        }
        assert quality_data.quality_index(mapping) == expected_index
