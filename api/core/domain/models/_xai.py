from datetime import date

from core.domain.models._displayed_provider import DisplayedProvider
from core.domain.models.model_data import (
    DeprecatedModel,
    LatestModel,
    MaxTokensData,
    ModelData,
    ModelFallback,
    ModelReasoningBudget,
    QualityData,
    SpeedData,
    SpeedIndex,
)
from core.domain.models.models import Model
from core.domain.reasoning_effort import ReasoningEffort


def xai_models() -> dict[Model, ModelData | LatestModel | DeprecatedModel]:
    return {
        Model.GROK_3_BETA: ModelData(
            display_name="Grok 3 (beta)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=131_072,
                source="https://docs.x.ai/docs/models#models-and-pricing",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/xai.svg",
            release_date=date(2025, 4, 10),
            quality_data=QualityData(
                mmlu_pro=79.9,
                gpqa=73.7,
                source="https://www.vals.ai/models/grok_grok-3-fast-beta",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2300, duration_seconds=42),
            ),
            provider_name=DisplayedProvider.X_AI.value,
            supports_tool_calling=True,
            supports_structured_output=True,
            fallback=ModelFallback.default("medium"),
        ),
        Model.GROK_3_FAST_BETA: ModelData(
            display_name="Grok 3 Fast (beta)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=131_072,
                source="https://docs.x.ai/docs/models#models-and-pricing",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/xai.svg",
            release_date=date(2025, 4, 10),
            quality_data=QualityData(
                mmlu_pro=79.9,
                gpqa=73.7,
                source="https://www.vals.ai/models/grok_grok-3-fast-beta",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2300, duration_seconds=35),
            ),
            provider_name=DisplayedProvider.X_AI.value,
            supports_tool_calling=True,
            supports_structured_output=True,
            fallback=ModelFallback.default("medium"),
        ),
        Model.GROK_3_MINI_BETA: ModelData(
            display_name="Grok 3 Mini (beta)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=131_072,
                source="https://docs.x.ai/docs/models#models-and-pricing",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/xai.svg",
            release_date=date(2025, 4, 10),
            # TODO: Update the quality index
            quality_data=QualityData(
                mmlu_pro=81.4,
                gpqa=79,
                source="https://www.vals.ai/models/grok_grok-3-mini-fast-beta-high-reasoning",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2140, duration_seconds=16),
            ),
            provider_name=DisplayedProvider.X_AI.value,
            supports_tool_calling=True,
            supports_structured_output=True,
            fallback=ModelFallback.default("cheap"),
            reasoning=ModelReasoningBudget(disabled=None, medium=None),
        ),
        Model.GROK_3_MINI_BETA_HIGH_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.GROK_3_MINI_BETA,
            reasoning_effort=ReasoningEffort.HIGH,
        ),
        Model.GROK_3_MINI_BETA_LOW_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.GROK_3_MINI_BETA,
            reasoning_effort=ReasoningEffort.LOW,
        ),
        Model.GROK_3_MINI_FAST_BETA: ModelData(
            display_name="Grok 3 Mini Fast (beta)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=131_072,
                source="https://docs.x.ai/docs/models#models-and-pricing",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/xai.svg",
            release_date=date(2025, 4, 10),
            quality_data=QualityData(
                mmlu_pro=81.4,
                gpqa=79,
                source="https://www.vals.ai/models/grok_grok-3-mini-fast-beta-high-reasoning",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2076, duration_seconds=14.9),
            ),
            provider_name=DisplayedProvider.X_AI.value,
            supports_tool_calling=True,
            supports_structured_output=True,
            fallback=ModelFallback.default("cheap"),
            reasoning=ModelReasoningBudget(disabled=None, medium=None),
        ),
        Model.GROK_3_MINI_FAST_BETA_HIGH_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.GROK_3_MINI_FAST_BETA,
            reasoning_effort=ReasoningEffort.HIGH,
        ),
        Model.GROK_3_MINI_FAST_BETA_LOW_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.GROK_3_MINI_FAST_BETA,
            reasoning_effort=ReasoningEffort.LOW,
        ),
    }
