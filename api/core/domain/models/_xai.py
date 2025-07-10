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
)
from core.domain.models.models import Model
from core.domain.reasoning_effort import ReasoningEffort


def xai_models() -> dict[Model, ModelData | LatestModel | DeprecatedModel]:
    return {
        Model.GROK_4_0709: ModelData(
            display_name="Grok 4 (0709)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=256_000,
                source="https://docs.x.ai/docs/models/grok-4-0709",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/xai.svg",
            release_date=date(2025, 7, 9),
            quality_data=QualityData(
                mmlu_pro=87.0,
                gpqa_diamond=88.0,
                source="https://x.com/ArtificialAnlys/status/1943166841150644622",
            ),
            provider_name=DisplayedProvider.X_AI.value,
            supports_tool_calling=True,
            supports_structured_output=True,
            fallback=ModelFallback.default("medium"),
        ),
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
