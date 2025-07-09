from datetime import date
from typing import get_args

from core.domain.models.model_data import (
    MaxTokensData,
    ModelData,
    ModelDataSupports,
    QualityData,
    SpeedData,
    SpeedIndex,
)
from core.domain.models.model_data_mapping import MODEL_DATAS, DisplayedProvider
from core.domain.models.model_provider_data import ModelDataSupportsOverride


class TestModelDataSupportsOverride:
    def test_fields_are_exhaustive(self):
        opt_fields = ModelDataSupportsOverride.model_fields
        non_opt_fields = ModelDataSupports.model_fields

        assert len(opt_fields) == len(non_opt_fields)

        for opt_f_name, opt_f in opt_fields.items():
            non_opt_f = non_opt_fields[opt_f_name]

            non_opt_type = get_args(opt_f.annotation)[0]
            assert non_opt_type == non_opt_f.annotation

    def test_override(self):
        override = ModelDataSupportsOverride(
            supports_json_mode=False,
            supports_input_image=False,
        )

        data = ModelData(
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_audio_only=True,
            supports_system_messages=True,
            supports_structured_output=True,
            supports_input_schema=True,
            display_name="test",
            icon_url="test",
            max_tokens_data=MaxTokensData(
                max_tokens=1000,
                max_output_tokens=100,
                source="",
            ),
            release_date=date(2024, 12, 13),
            quality_data=QualityData(index=400),
            speed_data=SpeedData(
                index=SpeedIndex(value=500),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            fallback=None,
        )

        assert override.override(data) == ModelData(
            supports_json_mode=False,
            supports_input_image=False,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_audio_only=True,
            supports_system_messages=True,
            supports_structured_output=True,
            supports_input_schema=True,
            display_name="test",
            icon_url="test",
            max_tokens_data=MaxTokensData(
                max_tokens=1000,
                max_output_tokens=100,
                source="",
            ),
            release_date=date(2024, 12, 13),
            quality_data=QualityData(index=400),
            speed_data=SpeedData(
                index=SpeedIndex(value=500),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            fallback=None,
        )


class TestOverrides:
    def test_at_least_one_provider_with_no_override(self):
        # At least one provider must not have override per models
        # This is a bit reductive since we could imagine different dimensions of overrides
        # but for now we need the sanity check
        for provider_data in MODEL_DATAS.values():
            if not isinstance(provider_data, ModelData):
                continue
            assert any(model_data.supports_override is None for _, model_data in provider_data.providers)
