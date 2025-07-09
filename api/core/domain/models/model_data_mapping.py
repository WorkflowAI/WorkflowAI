from datetime import date
from typing import Literal

from core.domain.models import Model, Provider
from core.domain.models._displayed_provider import DisplayedProvider
from core.domain.models._mistral import mistral_models
from core.domain.models._xai import xai_models
from core.domain.reasoning_effort import ReasoningEffort

from .model_data import (
    DeprecatedModel,
    FinalModelData,
    LatestModel,
    MaxTokensData,
    ModelData,
    ModelDataMapping,
    ModelFallback,
    ModelReasoningBudget,
    PricingTier,
    QualityData,
    SpeedData,
    SpeedIndex,
)


def _char_to_token(char_count: int) -> int:
    # Approx 4 characters per token
    return int(round(char_count / 4))


def _openai_fallback(pricing: PricingTier, context_exceeded: Model | Literal["no"] | None = None):
    """Alternative fallback for OpenAI models. Can't use the default since it uses mostly OpenAI models"""
    model: Model
    match pricing:
        case "cheap" | "cheapest":
            # Depending on the model, might have to set to "no" individually
            model = Model.GEMINI_2_0_FLASH_LATEST
        case "medium":
            # Medium models usually have a 1M context window
            model = Model.CLAUDE_4_SONNET_LATEST
            if not context_exceeded:
                context_exceeded = Model.GEMINI_1_5_PRO_LATEST
        case "expensive":
            # OpenAI expensive models usually have a 200k context window
            model = Model.CLAUDE_4_OPUS_LATEST
            if not context_exceeded:
                context_exceeded = Model.GEMINI_2_5_PRO

    return ModelFallback.only_model(model, pricing_tier=pricing, context_exceeded=context_exceeded)


def _raw_model_data() -> dict[Model, ModelData | LatestModel | DeprecatedModel]:
    return {
        Model.GPT_4O_LATEST: LatestModel(
            model=Model.GPT_4O_2024_11_20,
            display_name="GPT-4o (latest)",
            is_default=False,
            aliases=["gpt-4o"],
        ),
        Model.GPT_4O_2024_11_20: ModelData(
            display_name="GPT-4o (2024-11-20)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16_384,
                source="https://platform.openai.com/docs/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            latest_model=Model.GPT_4O_LATEST,
            release_date=date(2024, 11, 20),
            quality_data=QualityData(mmlu=85.70, gpqa=46.00),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1787, duration_seconds=27.6),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            fallback=_openai_fallback("medium"),
        ),
        Model.GPT_4O_2024_08_06: ModelData(
            display_name="GPT-4o (2024-08-06)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16_384,
                source="https://platform.openai.com/docs/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2024, 8, 6),
            quality_data=QualityData(mmlu=88.70, gpqa=53.10),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1913, duration_seconds=24),
            ),
            latest_model=Model.GPT_4O_LATEST,
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            fallback=_openai_fallback("medium"),
        ),
        Model.GPT_41_LATEST: LatestModel(
            model=Model.GPT_41_2025_04_14,
            display_name="GPT-4.1 (latest)",
            is_default=True,
        ),
        Model.GPT_41_2025_04_14: ModelData(
            display_name="GPT-4.1 (2025-04-14)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=1_047_576,
                max_output_tokens=32_768,
                source="https://platform.openai.com/docs/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            latest_model=Model.GPT_41_LATEST,
            release_date=date(2025, 4, 14),
            quality_data=QualityData(mmlu=90.2, gpqa=66.3),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1884, duration_seconds=38),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            fallback=_openai_fallback("medium"),
        ),
        Model.GPT_41_MINI_LATEST: LatestModel(
            model=Model.GPT_41_MINI_2025_04_14,
            display_name="GPT-4.1 Mini (latest)",
            is_default=False,
        ),
        Model.GPT_41_MINI_2025_04_14: ModelData(
            display_name="GPT-4.1 Mini (2025-04-14)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=1_047_576,
                max_output_tokens=32_768,
                source="https://platform.openai.com/docs/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            latest_model=Model.GPT_41_MINI_LATEST,
            release_date=date(2025, 4, 14),
            quality_data=QualityData(mmlu=87.5, gpqa=65),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1986, duration_seconds=38),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            fallback=_openai_fallback("cheapest", context_exceeded="no"),
        ),
        Model.GPT_41_NANO_LATEST: LatestModel(
            model=Model.GPT_41_NANO_2025_04_14,
            display_name="GPT-4.1 Nano (latest)",
            is_default=False,
        ),
        Model.GPT_41_NANO_2025_04_14: ModelData(
            display_name="GPT-4.1 Nano (2025-04-14)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=1_047_576,
                max_output_tokens=32_768,
                source="https://platform.openai.com/docs/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2025, 4, 14),
            quality_data=QualityData(mmlu=80, gpqa=50),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2002, duration_seconds=19),
            ),
            latest_model=Model.GPT_41_NANO_LATEST,
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            fallback=_openai_fallback("cheapest", context_exceeded="no"),
        ),
        Model.GPT_45_PREVIEW_2025_02_27: DeprecatedModel(replacement_model=Model.GPT_41_2025_04_14),
        Model.GPT_4O_2024_05_13: DeprecatedModel(replacement_model=Model.GPT_4O_2024_11_20),
        Model.GPT_4_TURBO_2024_04_09: DeprecatedModel(
            replacement_model=Model.GPT_4O_2024_11_20,
            aliases=["gpt-4-turbo", "gpt-4", "gpt-4-0613", "gpt-4-turbo-preview"],
        ),
        Model.GPT_4O_MINI_LATEST: LatestModel(
            model=Model.GPT_4O_MINI_2024_07_18,
            display_name="GPT-4o mini (latest)",
        ),
        Model.GPT_4O_MINI_2024_07_18: ModelData(
            display_name="GPT-4o mini (2024-07-18)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16000,
                source="https://platform.openai.com/docs/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            latest_model=Model.GPT_4O_MINI_LATEST,
            release_date=date(2024, 7, 18),
            quality_data=QualityData(mmlu=82.00, gpqa=40.20),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1914, duration_seconds=28),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            fallback=_openai_fallback("cheapest"),
        ),
        Model.GPT_IMAGE_1: ModelData(
            display_name="GPT Image 1",
            supports_json_mode=False,
            supports_input_image=True,
            supports_output_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_output_text=False,
            supports_structured_output=False,
            max_tokens_data=MaxTokensData(
                # gpt-image-1 does not really have a context window it seems
                # But the input max is 32_000 characters
                max_tokens=_char_to_token(32_000),
                source="https://platform.openai.com/docs/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2025, 4, 23),
            quality_data=QualityData(index=611),  # TODO: a bit difficult to estimate here
            speed_data=SpeedData(
                index=SpeedIndex(value=10),  # difficult to estimate, assigne low value
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=False,
            is_default=True,
            # No fallback for image generation
            fallback=None,
        ),
        Model.GPT_3_5_TURBO_0125: DeprecatedModel(
            replacement_model=Model.GPT_4O_MINI_2024_07_18,
            aliases=["gpt-3.5-turbo-16k", "gpt-3.5-turbo", "gpt-3.5-turbo-instruct-0914", "gpt-3.5-turbo-instruct"],
        ),
        Model.GPT_3_5_TURBO_1106: DeprecatedModel(
            replacement_model=Model.GPT_4O_MINI_2024_07_18,
        ),
        Model.GPT_4_0125_PREVIEW: DeprecatedModel(replacement_model=Model.GPT_41_2025_04_14),
        Model.GPT_4_1106_PREVIEW: DeprecatedModel(replacement_model=Model.GPT_41_2025_04_14),
        Model.GPT_4_1106_VISION_PREVIEW: DeprecatedModel(replacement_model=Model.GPT_4O_2024_11_20),
        Model.GPT_4O_AUDIO_PREVIEW_2025_06_03: ModelData(
            display_name="GPT-4o (Audio Preview 2025-06-03)",
            supports_json_mode=False,
            supports_structured_output=False,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_schema=False,
            supports_input_audio=True,
            supports_audio_only=True,
            supports_system_messages=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16384,
                source="https://platform.openai.com/docs/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            is_default=True,
            release_date=date(2025, 6, 3),
            provider_name=DisplayedProvider.OPEN_AI.value,
            quality_data=QualityData(equivalent_to=(Model.GPT_4O_AUDIO_PREVIEW_2024_12_17, 1)),
            speed_data=SpeedData(
                index=SpeedIndex(value=10),  # difficult to estimate, assigne low value
            ),
            supports_tool_calling=False,
            aliases=[],
            fallback=ModelFallback(
                # Falling back to Gemini 1.5 Pro to support audio
                content_moderation=Model.GEMINI_1_5_PRO_002,
                structured_output=Model.GEMINI_1_5_PRO_002,
                rate_limit=Model.GEMINI_1_5_PRO_002,
                context_exceeded=None,
            ),
            supports_temperature=False,
            supports_top_p=False,
            supports_presence_penalty=False,
            supports_frequency_penalty=False,
        ),
        Model.GPT_4O_AUDIO_PREVIEW_2024_12_17: ModelData(
            display_name="GPT-4o (Audio Preview 2024-12-17)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_schema=False,
            supports_input_audio=True,
            supports_audio_only=True,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16384,
                source="https://platform.openai.com/docs/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            is_default=True,
            release_date=date(2024, 12, 17),
            provider_name=DisplayedProvider.OPEN_AI.value,
            quality_data=QualityData(mmlu=88.70, gpqa=53.60),
            speed_data=SpeedData(
                index=SpeedIndex(value=10),  # difficult to estimate, assigne low value
            ),
            supports_tool_calling=False,
            aliases=["gpt-4o-audio-preview"],
            fallback=ModelFallback(
                # Falling back to Gemini 1.5 Pro to support audio
                content_moderation=Model.GEMINI_1_5_PRO_002,
                structured_output=Model.GEMINI_1_5_PRO_002,
                rate_limit=Model.GEMINI_1_5_PRO_002,
                context_exceeded=None,
            ),
            supports_temperature=False,
            supports_top_p=False,
            supports_presence_penalty=False,
            supports_frequency_penalty=False,
        ),
        Model.GPT_4O_AUDIO_PREVIEW_2024_10_01: DeprecatedModel(replacement_model=Model.GPT_4O_AUDIO_PREVIEW_2024_12_17),
        Model.O1_PREVIEW_2024_09_12: DeprecatedModel(replacement_model=Model.O3_2025_04_16, aliases=["o1-preview"]),
        Model.O1_MINI_LATEST: DeprecatedModel(replacement_model=Model.O3_MINI_2025_01_31, aliases=["o1-mini"]),
        Model.O1_MINI_2024_09_12: DeprecatedModel(replacement_model=Model.O3_MINI_2025_01_31),
        Model.O3_MINI_LATEST_HIGH_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_MINI_2025_01_31,
            reasoning_effort=ReasoningEffort.HIGH,
        ),
        Model.O3_MINI_LATEST_MEDIUM_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_MINI_2025_01_31,
            reasoning_effort=ReasoningEffort.MEDIUM,
        ),
        Model.O3_MINI_LATEST_LOW_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_MINI_2025_01_31,
            reasoning_effort=ReasoningEffort.LOW,
        ),
        Model.O3_MINI_LATEST: LatestModel(
            model=Model.O3_MINI_2025_01_31,
            display_name="o3-mini (latest)",
        ),
        Model.O3_MINI_2025_01_31: ModelData(
            display_name="o3-mini (2025-01-31)",
            supports_json_mode=False,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            release_date=date(2025, 1, 31),
            quality_data=QualityData(mmlu=88.70, gpqa=77.00),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2252, duration_seconds=18),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models",
            ),
            latest_model=Model.O3_MINI_LATEST,
            supports_tool_calling=True,
            supports_parallel_tool_calls=False,
            fallback=_openai_fallback("cheap"),
            reasoning=ModelReasoningBudget(disabled=None),
            supports_temperature=False,
            supports_top_p=False,
            supports_presence_penalty=False,
            supports_frequency_penalty=False,
        ),
        Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_MINI_2025_01_31,
            reasoning_effort=ReasoningEffort.HIGH,
        ),
        Model.O3_MINI_2025_01_31_MEDIUM_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_MINI_2025_01_31,
            reasoning_effort=ReasoningEffort.MEDIUM,
        ),
        Model.O3_MINI_2025_01_31_LOW_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_MINI_2025_01_31,
            reasoning_effort=ReasoningEffort.LOW,
        ),
        Model.O4_MINI_LATEST_HIGH_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O4_MINI_2025_04_16,
            reasoning_effort=ReasoningEffort.HIGH,
        ),
        Model.O4_MINI_LATEST_MEDIUM_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O4_MINI_2025_04_16,
            reasoning_effort=ReasoningEffort.MEDIUM,
        ),
        Model.O4_MINI_LATEST_LOW_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O4_MINI_2025_04_16,
            reasoning_effort=ReasoningEffort.LOW,
        ),
        Model.O4_MINI_LATEST: LatestModel(
            model=Model.O4_MINI_2025_04_16,
            display_name="o4-mini (latest)",
        ),
        Model.O4_MINI_2025_04_16: ModelData(
            display_name="o4-mini (2025-04-16)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            release_date=date(2025, 4, 16),
            quality_data=QualityData(
                mmlu_pro=80.6,
                gpqa=74.5,
                source="https://www.vals.ai/models/openai_o4-mini-2025-04-16",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2650, duration_seconds=33),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models",
            ),
            latest_model=Model.O4_MINI_LATEST,
            supports_tool_calling=True,
            supports_parallel_tool_calls=False,
            fallback=_openai_fallback("cheap"),
            reasoning=ModelReasoningBudget(disabled=None),
            supports_temperature=False,
            supports_top_p=False,
            supports_presence_penalty=False,
            supports_frequency_penalty=False,
        ),
        Model.O4_MINI_2025_04_16_HIGH_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O4_MINI_2025_04_16,
            reasoning_effort=ReasoningEffort.HIGH,
        ),
        Model.O4_MINI_2025_04_16_MEDIUM_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O4_MINI_2025_04_16,
            reasoning_effort=ReasoningEffort.MEDIUM,
        ),
        Model.O4_MINI_2025_04_16_LOW_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O4_MINI_2025_04_16,
            reasoning_effort=ReasoningEffort.LOW,
        ),
        Model.O3_LATEST: LatestModel(model=Model.O3_2025_04_16, display_name="o3 (latest)"),
        Model.O3_2025_04_16: ModelData(
            display_name="o3 (2025-04-16)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            supports_structured_output=True,
            release_date=date(2025, 4, 16),
            quality_data=QualityData(
                gpqa_diamond=83.6,
                mmlu_pro=85.6,
                source="https://www.vals.ai/models/openai_o3-2025-04-16",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2200, duration_seconds=80),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models",
            ),
            latest_model=Model.O3_LATEST,
            supports_tool_calling=True,
            supports_parallel_tool_calls=False,
            aliases=["o3-2025-04-16"],
            fallback=_openai_fallback("medium"),
            reasoning=ModelReasoningBudget(disabled=None),
            supports_temperature=False,
            supports_top_p=False,
            supports_presence_penalty=False,
            supports_frequency_penalty=False,
        ),
        Model.O3_LATEST_HIGH_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_2025_04_16,
            reasoning_effort=ReasoningEffort.HIGH,
        ),
        Model.O3_LATEST_MEDIUM_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_2025_04_16,
            reasoning_effort=ReasoningEffort.MEDIUM,
        ),
        Model.O3_LATEST_LOW_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_2025_04_16,
            reasoning_effort=ReasoningEffort.LOW,
        ),
        Model.O3_2025_04_16_HIGH_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_2025_04_16,
            reasoning_effort=ReasoningEffort.HIGH,
        ),
        Model.O3_2025_04_16_MEDIUM_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_2025_04_16,
            reasoning_effort=ReasoningEffort.MEDIUM,
        ),
        Model.O3_2025_04_16_LOW_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O3_2025_04_16,
            reasoning_effort=ReasoningEffort.LOW,
        ),
        # Model.O3_PRO_LATEST_HIGH_REASONING_EFFORT: LatestModel(
        #     model=Model.O3_PRO_2025_06_10_HIGH_REASONING_EFFORT,
        #     display_name="o3-pro (latest) - High reasoning effort",
        # ),
        # Model.O3_PRO_LATEST_MEDIUM_REASONING_EFFORT: LatestModel(
        #     model=Model.O3_PRO_2025_06_10_MEDIUM_REASONING_EFFORT,
        #     display_name="o3-pro (latest) - Medium reasoning effort",
        #     aliases=["o3-pro"],
        # ),
        # Model.O3_PRO_LATEST_LOW_REASONING_EFFORT: LatestModel(
        #     model=Model.O3_PRO_2025_06_10_LOW_REASONING_EFFORT,
        #     display_name="o3-pro (latest) - Low reasoning effort",
        # ),
        # Model.O3_PRO_2025_06_10_HIGH_REASONING_EFFORT: ModelData(
        #     display_name="o3-pro (2025-06-10) - High reasoning effort",
        #     supports_json_mode=True,
        #     supports_input_image=True,
        #     supports_input_pdf=True,
        #     supports_input_audio=False,
        #     supports_structured_output=True,
        #     release_date=date(2025, 6, 10),
        #     quality_data=QualityData(
        #         equivalent_to=(Model.O3_PRO_2025_06_10_MEDIUM_REASONING_EFFORT, 5),  # Same quality as o3
        #     ),
        #     provider_name=DisplayedProvider.OPEN_AI.value,
        #     icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
        #     max_tokens_data=MaxTokensData(
        #         max_tokens=200_000,
        #         max_output_tokens=100_000,
        #         source="https://platform.openai.com/docs/models/o3-pro",
        #     ),
        #     latest_model=Model.O3_PRO_LATEST_HIGH_REASONING_EFFORT,
        #     supports_tool_calling=True,
        #     supports_parallel_tool_calls=False,
        #     fallback=_openai_fallback("expensive"),
        # ),
        # Model.O3_PRO_2025_06_10_MEDIUM_REASONING_EFFORT: ModelData(
        #     display_name="o3-pro (2025-06-10) - Medium reasoning effort",
        #     supports_json_mode=True,
        #     supports_input_image=True,
        #     supports_input_pdf=True,
        #     supports_input_audio=False,
        #     supports_structured_output=True,
        #     release_date=date(2025, 6, 10),
        #     quality_data=QualityData(
        #         # TODO: for now using same quality data as o3
        #         gpqa_diamond=83.6,
        #         mmlu_pro=85.6,
        #         source="https://www.vals.ai/models/openai_o3-2025-04-16",
        #     ),
        # speed_data=SpeedData(index=500),  # Default speed index, can be updated with real data later
        #     provider_name=DisplayedProvider.OPEN_AI.value,
        #     icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
        #     max_tokens_data=MaxTokensData(
        #         max_tokens=200_000,
        #         max_output_tokens=100_000,
        #         source="https://platform.openai.com/docs/models/o3-pro",
        #     ),
        #     latest_model=Model.O3_PRO_LATEST_MEDIUM_REASONING_EFFORT,
        #     supports_tool_calling=True,
        #     supports_parallel_tool_calls=False,
        #     aliases=["o3-pro-2025-06-10"],
        #     fallback=_openai_fallback("expensive"),
        # ),
        # Model.O3_PRO_2025_06_10_LOW_REASONING_EFFORT: ModelData(
        #     display_name="o3-pro (2025-06-10) - Low reasoning effort",
        #     supports_json_mode=True,
        #     supports_input_image=True,
        #     supports_input_pdf=True,
        #     supports_input_audio=False,
        #     supports_structured_output=True,
        #     release_date=date(2025, 6, 10),
        #     quality_data=QualityData(
        #         equivalent_to=(Model.O3_PRO_2025_06_10_MEDIUM_REASONING_EFFORT, -5),  # Same quality as o3
        #     ),
        #     provider_name=DisplayedProvider.OPEN_AI.value,
        #     icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
        #     max_tokens_data=MaxTokensData(
        #         max_tokens=200_000,
        #         max_output_tokens=100_000,
        #         source="https://platform.openai.com/docs/models/o3-pro",
        #     ),
        #     latest_model=Model.O3_PRO_LATEST_LOW_REASONING_EFFORT,
        #     supports_tool_calling=True,
        #     supports_parallel_tool_calls=False,
        #     fallback=_openai_fallback("expensive"),
        # ),
        Model.GEMINI_1_5_PRO_PREVIEW_0514: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_2_0_FLASH_LITE_PREVIEW_2502: DeprecatedModel(replacement_model=Model.GEMINI_2_0_FLASH_LITE_001),
        Model.GEMINI_2_0_FLASH_LITE_001: ModelData(
            display_name="Gemini 2.0 Flash-Lite (001)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,
            max_tokens_data=MaxTokensData(
                max_tokens=1048576,
                max_output_tokens=8_192,
                source="https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.0-flash-lite",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 2, 5),
            quality_data=QualityData(mmlu=83.5, gpqa=51.5),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1821, duration_seconds=13),
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default(
                "cheapest",
                content_moderation=Model.GPT_41_NANO_LATEST,
                context_exceeded="no",
            ),
        ),
        Model.GEMINI_2_0_FLASH_001: ModelData(
            display_name="Gemini 2.0 Flash (001)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured outputs, but we did not activate this feature for Google  yet
            max_tokens_data=MaxTokensData(
                max_tokens=1048576,
                max_output_tokens=8_192,
                source="https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.0-flash",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 2, 5),
            latest_model=Model.GEMINI_2_0_FLASH_LATEST,
            quality_data=QualityData(mmlu=76.4, gpqa=74.2),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1805, duration_seconds=14),
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default(
                "cheapest",
                content_moderation=Model.GPT_41_NANO_LATEST,
                context_exceeded="no",
            ),
        ),
        Model.GEMINI_2_5_FLASH_PREVIEW_0417: DeprecatedModel(replacement_model=Model.GEMINI_2_5_FLASH),
        Model.GEMINI_2_5_FLASH_PREVIEW_0520: DeprecatedModel(
            replacement_model=Model.GEMINI_2_5_FLASH,
            reasoning_effort=ReasoningEffort.DISABLED,
        ),
        Model.GEMINI_2_5_FLASH: ModelData(
            display_name="Gemini 2.5 Flash",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=1_048_576 + 65_536,
                max_output_tokens=65_536,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 6, 18),
            quality_data=QualityData(
                gpqa=82.8,
                mmlu=88.4,
                source="https://deepmind.google/models/gemini/flash/",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2821, duration_seconds=13.4),
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default(
                "cheapest",
                content_moderation=Model.GPT_41_NANO_LATEST,
                rate_limit=Model.GEMINI_2_0_FLASH_001,
                context_exceeded="no",
            ),
            is_default=True,
            reasoning=ModelReasoningBudget(disabled=0, min=1, max=24576),
        ),
        Model.GEMINI_2_5_FLASH_THINKING_PREVIEW_0417: DeprecatedModel(replacement_model=Model.GEMINI_2_5_FLASH),
        Model.GEMINI_2_5_FLASH_THINKING_PREVIEW_0520: DeprecatedModel(replacement_model=Model.GEMINI_2_5_FLASH),
        Model.GEMINI_2_5_PRO: ModelData(
            display_name="Gemini 2.5 Pro",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=1_048_576 + 65_536,
                max_output_tokens=65_536,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-pro",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 6, 18),
            quality_data=QualityData(
                gpqa_diamond=86.4,
                mmlu=89.2,
                source="https://deepmind.google/models/gemini/pro/",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1890, duration_seconds=73),
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default(
                "medium",
                content_moderation=Model.GPT_41_LATEST,
                context_exceeded="no",
            ),
            # https://cloud.google.com/vertex-ai/generative-ai/docs/thinking
            reasoning=ModelReasoningBudget(min=128, max=32_768),
        ),
        Model.GEMINI_2_5_FLASH_LITE_PREVIEW_0617: ModelData(
            display_name="Gemini 2.5 Flash Lite Preview (06-17)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=1_048_576 + 65_536,
                max_output_tokens=65_536,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-lite",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 6, 18),
            quality_data=QualityData(
                gpqa_diamond=66.7,
                mmlu=84.5,
                source="https://deepmind.google/models/gemini/flash-lite/",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2900, duration_seconds=9),
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default(
                "cheapest",
                content_moderation=Model.GPT_41_NANO_LATEST,
                context_exceeded="no",
            ),
            # https://cloud.google.com/vertex-ai/generative-ai/docs/thinking
            reasoning=ModelReasoningBudget(disabled=0, min=512, max=24_576),
        ),
        Model.GEMINI_2_5_PRO_PREVIEW_0605: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO),
        Model.GEMINI_2_5_PRO_PREVIEW_0506: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO),
        Model.GEMINI_2_5_PRO_PREVIEW_0325: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO),
        Model.GEMINI_2_5_PRO_EXP_0325: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO),
        Model.GEMINI_2_0_PRO_EXP: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO),
        Model.GEMINI_2_0_FLASH_EXP: ModelData(
            display_name="Gemini 2.0 Flash Exp (Image Generation)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_output_image=True,
            supports_structured_output=False,
            supports_system_messages=False,
            max_tokens_data=MaxTokensData(
                max_tokens=1_048_576 + 8_192,
                max_output_tokens=8_192,
                source="https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.0-flash",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 2, 5),
            quality_data=QualityData(equivalent_to=(Model.GEMINI_2_0_FLASH_001, 0)),
            speed_data=SpeedData(index=SpeedIndex.from_experiment(output_tokens=2200, duration_seconds=15)),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
            is_default=True,
            fallback=None,  # No fallback for exp models
        ),
        Model.GEMINI_2_0_FLASH_LATEST: LatestModel(
            model=Model.GEMINI_2_0_FLASH_001,
            display_name="Gemini 2.0 Flash (latest)",
        ),
        Model.GEMINI_1_5_PRO_LATEST: LatestModel(
            model=Model.GEMINI_1_5_PRO_002,
            display_name="Gemini 1.5 Pro (latest)",
            is_default=True,
        ),
        Model.GEMINI_2_0_FLASH_THINKING_EXP_0121: DeprecatedModel(
            replacement_model=Model.GEMINI_2_5_PRO,
        ),
        Model.GEMINI_2_0_FLASH_THINKING_EXP_1219: DeprecatedModel(
            replacement_model=Model.GEMINI_2_5_PRO,
        ),
        Model.GEMINI_1_5_PRO_002: ModelData(
            display_name="Gemini 1.5 Pro (002)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured outputs, but we did not activate this feature for Google  yet
            max_tokens_data=MaxTokensData(
                max_tokens=2_097_152,
                max_output_tokens=8_192,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#gemini-1.5-pro",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            latest_model=Model.GEMINI_1_5_PRO_LATEST,
            release_date=date(2024, 9, 24),
            quality_data=QualityData(mmlu=85.14, gpqa=59.10),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1905, duration_seconds=35),
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("medium", content_moderation=Model.GPT_41_LATEST, context_exceeded="no"),
        ),
        Model.GEMINI_1_5_PRO_001: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_1_5_PRO_PREVIEW_0409: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_1_5_FLASH_PREVIEW_0514: DeprecatedModel(replacement_model=Model.GEMINI_1_5_FLASH_002),
        Model.GEMINI_1_5_FLASH_LATEST: LatestModel(
            model=Model.GEMINI_1_5_FLASH_002,
            display_name="Gemini 1.5 Flash (latest)",
        ),
        Model.CLAUDE_4_SONNET_LATEST: LatestModel(
            model=Model.CLAUDE_4_SONNET_20250514,
            display_name="Claude 4 Sonnet (latest)",
            is_default=True,
        ),
        Model.CLAUDE_4_SONNET_20250514: ModelData(
            display_name="Claude 4 Sonnet (2025-05-14)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                # See https://docs.anthropic.com/en/docs/about-claude/models/all-models
                max_output_tokens=64_000,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2025, 5, 22),
            # https://www.anthropic.com/news/claude-4
            # We only have the mmmlu for now...
            quality_data=QualityData(gpqa_diamond=70),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2648, duration_seconds=32),
            ),
            latest_model=Model.CLAUDE_4_SONNET_LATEST,
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("medium"),
        ),
        Model.CLAUDE_4_OPUS_LATEST: LatestModel(
            model=Model.CLAUDE_4_OPUS_20250514,
            display_name="Claude 4 Opus (latest)",
            is_default=True,
        ),
        Model.CLAUDE_4_OPUS_20250514: ModelData(
            display_name="Claude 4 Opus (2025-05-14)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                # See https://docs.anthropic.com/en/docs/about-claude/models/all-models
                max_output_tokens=32_000,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2025, 5, 22),
            # https://www.anthropic.com/news/claude-4
            # We only have the mmmlu for now...
            quality_data=QualityData(gpqa_diamond=74.9),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2648, duration_seconds=56.6),
            ),
            latest_model=Model.CLAUDE_4_OPUS_LATEST,
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("expensive"),
        ),
        Model.CLAUDE_3_7_SONNET_LATEST: LatestModel(
            model=Model.CLAUDE_3_7_SONNET_20250219,
            display_name="Claude 3.7 Sonnet (latest)",
            is_default=True,
        ),
        Model.CLAUDE_3_7_SONNET_20250219: ModelData(
            display_name="Claude 3.7 Sonnet (2025-02-19)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                # See https://docs.anthropic.com/en/docs/about-claude/models/all-models
                max_output_tokens=64_000,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2025, 2, 19),
            # TODO: quality index, for now quality index of CLAUDE_3_5_SONNET_20241022 + 1
            quality_data=QualityData(mmlu=90.8, gpqa=84.8, gpqa_diamond=69.7),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2640, duration_seconds=40),
            ),
            latest_model=Model.CLAUDE_3_7_SONNET_LATEST,
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("medium"),
        ),
        Model.CLAUDE_3_5_SONNET_20241022: ModelData(
            display_name="Claude 3.5 Sonnet (2024-10-22)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=8192,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2024, 10, 22),
            quality_data=QualityData(mmlu=86, gpqa=68),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=543, duration_seconds=11),
            ),
            latest_model=Model.CLAUDE_3_5_SONNET_LATEST,
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("medium"),
        ),
        Model.GEMINI_1_5_FLASH_002: ModelData(
            display_name="Gemini 1.5 Flash (002)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured outputs, but we did not activate this feature for Google  yet
            max_tokens_data=MaxTokensData(
                max_tokens=1048576,
                max_output_tokens=8192,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#gemini-1.5-flash",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            latest_model=Model.GEMINI_1_5_FLASH_LATEST,
            release_date=date(2024, 9, 24),
            quality_data=QualityData(mmlu=78.9, gpqa=51),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1857, duration_seconds=16.7),
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default(
                "cheapest",
                content_moderation=Model.GPT_41_NANO_LATEST,
                context_exceeded="no",
            ),
        ),
        Model.GEMINI_1_5_FLASH_001: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_1_0_PRO_VISION_001: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_1_0_PRO_001: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_1_0_PRO_002: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.CLAUDE_3_5_SONNET_LATEST: LatestModel(
            model=Model.CLAUDE_3_5_SONNET_20241022,
            display_name="Claude 3.5 Sonnet (latest)",
        ),
        Model.O1_2024_12_17: ModelData(
            display_name="o1 (2024-12-17)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models/gp#o1",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2024, 12, 17),
            quality_data=QualityData(mmlu=90.8, gpqa=78.3),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2248, duration_seconds=62),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            supports_parallel_tool_calls=False,
            fallback=_openai_fallback("expensive"),
            reasoning=ModelReasoningBudget(disabled=None),
            aliases=["o1"],
            supports_temperature=False,
            supports_top_p=False,
            supports_presence_penalty=False,
            supports_frequency_penalty=False,
        ),
        Model.O1_2024_12_17_HIGH_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O1_2024_12_17,
            reasoning_effort=ReasoningEffort.HIGH,
        ),
        Model.O1_2024_12_17_LOW_REASONING_EFFORT: DeprecatedModel(
            replacement_model=Model.O1_2024_12_17,
            reasoning_effort=ReasoningEffort.LOW,
        ),
        Model.CLAUDE_3_5_SONNET_20240620: ModelData(
            display_name="Claude 3.5 Sonnet (2024-06-20)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=4096,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            latest_model=Model.CLAUDE_3_5_SONNET_LATEST,
            release_date=date(2024, 6, 20),
            quality_data=QualityData(mmlu=88.3, gpqa=59.4),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2655, duration_seconds=40),
            ),
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("medium"),
        ),
        Model.CLAUDE_3_OPUS_20240229: ModelData(
            display_name="Claude 3 Opus (2024-02-29)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=4096,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2024, 2, 29),
            quality_data=QualityData(mmlu=88.2, gpqa=50.4),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2692, duration_seconds=96),
            ),
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("medium"),
        ),
        Model.CLAUDE_3_SONNET_20240229: DeprecatedModel(replacement_model=Model.CLAUDE_3_5_SONNET_20241022),
        Model.CLAUDE_3_HAIKU_20240307: ModelData(
            display_name="Claude 3 Haiku (2024-03-07)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=4096,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2024, 3, 7),
            quality_data=QualityData(mmlu=76.7, gpqa=33.3),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=640, duration_seconds=6),
            ),
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("cheap"),
        ),
        Model.CLAUDE_3_5_HAIKU_LATEST: LatestModel(
            model=Model.CLAUDE_3_5_HAIKU_20241022,
            display_name="Claude 3.5 Haiku (latest)",
        ),
        Model.CLAUDE_3_5_HAIKU_20241022: ModelData(
            display_name="Claude 3.5 Haiku (2024-10-22)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=8192,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            latest_model=Model.CLAUDE_3_5_HAIKU_LATEST,
            release_date=date(2024, 10, 22),
            quality_data=QualityData(mmlu=76.7, gpqa=41.6),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=706, duration_seconds=15),
            ),
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("cheap"),
        ),
        Model.LLAMA3_70B_8192: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        Model.LLAMA3_8B_8192: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        Model.LLAMA_3_1_405B: ModelData(
            display_name="Llama 3.1 (405B)",
            supports_json_mode=False,  # 405b does not support JSON mode for now https://www.together.ai/blog/meta-llama-3-1
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 7, 23),
            quality_data=QualityData(mmlu=88.6, gpqa=73.9),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2431, duration_seconds=32),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("medium"),
        ),
        # https://fireworks.ai/models/fireworks/llama-v3p3-70b-instruct
        Model.LLAMA_3_3_70B: ModelData(
            display_name="Llama 3.3 (70B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=131072,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/llama-v3p3-70b-instruct",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 12, 6),
            quality_data=QualityData(mmlu=86, gpqa=50.5),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2568, duration_seconds=10),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
            fallback=ModelFallback.default("cheap"),
        ),
        # https://fireworks.ai/models/fireworks/llama-v3p1-70b-instruct
        Model.LLAMA_3_1_70B: ModelData(
            display_name="Llama 3.1 (70B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 7, 23),
            quality_data=QualityData(mmlu=86, gpqa=48),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2396, duration_seconds=18),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("cheap"),
        ),
        # https://fireworks.ai/models/fireworks/llama-v3p1-8b-instruct
        Model.LLAMA_3_1_8B: ModelData(
            display_name="Llama 3.1 (8B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=131072,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/llama-v3p1-8b-instruct",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 7, 23),
            quality_data=QualityData(mmlu=66.7, gpqa=33.8),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1680, duration_seconds=4.2),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
            fallback=ModelFallback.only_model(Model.GEMINI_2_0_FLASH_LITE_001, "cheapest"),
        ),
        Model.LLAMA_3_2_90B: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        Model.LLAMA_3_2_11B: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        Model.LLAMA_3_2_3B: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        Model.LLAMA_3_2_1B: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        Model.LLAMA_3_2_90B_TEXT_PREVIEW: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        Model.LLAMA_3_2_11B_TEXT_PREVIEW: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        # https://fireworks.ai/models/fireworks/llama-v3p2-3b
        Model.LLAMA_3_2_3B_PREVIEW: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        Model.LLAMA_3_2_1B_PREVIEW: DeprecatedModel(replacement_model=Model.LLAMA_4_SCOUT_BASIC),
        Model.LLAMA_3_2_90B_VISION_PREVIEW: DeprecatedModel(replacement_model=Model.LLAMA_4_MAVERICK_BASIC),
        Model.GEMINI_1_5_FLASH_8B: ModelData(
            display_name="Gemini 1.5 Flash (8B)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured output but we did not activate for Gemini yet
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://ai.google.dev/gemini-api/docs/models/gemini",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2024, 10, 3),
            quality_data=QualityData(mmlu=58.7, gpqa=38.4),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2236, duration_seconds=12),
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default(
                "cheapest",
                rate_limit=Model.GEMINI_2_0_FLASH_EXP,
                content_moderation=Model.GPT_41_NANO_LATEST,
            ),
        ),
        Model.GEMINI_EXP_1206: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO),
        Model.GEMINI_EXP_1121: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO),
        Model.QWEN_QWQ_32B: ModelData(
            display_name="Qwen QWQ (32B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=131_072,
                source="https://fireworks.ai/models/fireworks/qwq-32b",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/qwen.svg",
            release_date=date(2025, 3, 6),
            quality_data=QualityData(mmlu=83.3, gpqa=59.1),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2316, duration_seconds=11.4),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
            fallback=ModelFallback.default("cheap"),
        ),
        Model.QWEN3_235B_A22B: ModelData(
            display_name="Qwen3 235B (22B active)",
            supports_json_mode=True,
            supports_input_image=False,  # Double check
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=125_000,
                source="https://app.fireworks.ai/models/fireworks/qwen3-235b-a22b",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/qwen.svg",
            release_date=date(2025, 4, 29),
            quality_data=QualityData(mmlu=87.8, gpqa=70, source="https://qwenlm.github.io/blog/qwen3/"),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2120, duration_seconds=49),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("cheap"),
        ),
        Model.QWEN3_30B_A3B: ModelData(
            display_name="Qwen3 30B (3B active)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=39_000,
                source="https://app.fireworks.ai/models/fireworks/qwen3-30b-a3b",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/qwen.svg",
            release_date=date(2025, 4, 29),
            quality_data=QualityData(mmlu=80, gpqa=62, source="https://qwenlm.github.io/blog/qwen3/"),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2300, duration_seconds=45),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("cheapest"),
        ),
        Model.QWEN_QWQ_32B_PREVIEW: DeprecatedModel(replacement_model=Model.QWEN_QWQ_32B),
        Model.LLAMA_3_2_11B_VISION: DeprecatedModel(
            replacement_model=Model.LLAMA_4_MAVERICK_BASIC,
        ),
        Model.LLAMA_4_MAVERICK_BASIC: ModelData(
            display_name="Llama 4 Maverick",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=1_000_000,  # not sure about the exact number
                source="https://fireworks.ai/models/fireworks/llama4-maverick-instruct-basic",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2025, 4, 5),
            quality_data=QualityData(equivalent_to=(Model.LLAMA_4_MAVERICK_FAST, 0)),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2000, duration_seconds=16.3),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
            supports_structured_output=True,
            fallback=ModelFallback.default("cheap", context_exceeded="no"),
        ),
        # https://fireworks.ai/models/fireworks/llama4-scout-instruct-basic
        Model.LLAMA_4_SCOUT_BASIC: ModelData(
            display_name="Llama 4 Scout",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                # LLama says 10M but fireworks only supports 128k for now
                max_tokens=128_000,
                source="https://fireworks.ai/models/fireworks/llama4-scout-instruct-basic",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2025, 4, 5),
            quality_data=QualityData(equivalent_to=(Model.LLAMA_4_SCOUT_FAST, 0)),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1878, duration_seconds=15),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
            supports_structured_output=True,
            fallback=ModelFallback.default("cheapest"),
        ),
        Model.LLAMA_4_MAVERICK_FAST: ModelData(
            display_name="Llama 4 Maverick ⚡",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                source="https://console.groq.com/docs/model/llama-4-maverick-17b-128e-instruct",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2025, 4, 5),
            quality_data=QualityData(
                mmlu_pro=79.4,
                gpqa=67.7,
                gpqa_diamond=61.1,
                source="https://www.vals.ai/models/together_meta-llama_Llama-4-Maverick-17B-128E-Instruct-FP8",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2491, duration_seconds=5.8),
            ),
            provider_name=DisplayedProvider.GROQ.value,
            supports_tool_calling=True,
            supports_structured_output=True,
            fallback=ModelFallback.default("cheap"),
        ),
        # https://fireworks.ai/models/fireworks/llama4-scout-instruct-basic
        Model.LLAMA_4_SCOUT_FAST: ModelData(
            display_name="Llama 4 Scout ⚡",
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                source="https://console.groq.com/docs/model/llama-4-scout-17b-16e-instruct",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2025, 4, 5),
            # https://ai.meta.com/blog/llama-4-multimodal-intelligence/
            quality_data=QualityData(
                mmlu_pro=69.6,
                gpqa=44.4,
                source="https://www.vals.ai/models/together_meta-llama_Llama-4-Scout-17B-16E-Instruct",
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2532, duration_seconds=4.8),
            ),
            provider_name=DisplayedProvider.GROQ.value,
            supports_tool_calling=True,
            supports_structured_output=True,
            fallback=ModelFallback.default("cheapest"),
        ),
        # https://fireworks.ai/models/fireworks/deepseek-v3
        Model.DEEPSEEK_V3_2412: ModelData(
            display_name="DeepSeek V3 (24-12) (US hosted)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/deepseek-ai/DeepSeek-V3",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/deepseek.svg",
            release_date=date(2024, 12, 30),
            quality_data=QualityData(mmlu=88.5, gpqa=59.1),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2290, duration_seconds=24),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            supports_structured_output=True,
            latest_model=Model.DEEPSEEK_V3_LATEST,
            fallback=ModelFallback.default("cheap"),
        ),
        # https://fireworks.ai/models/fireworks/deepseek-r1
        Model.DEEPSEEK_R1_2501: ModelData(
            display_name="DeepSeek R1 (25-01) (US hosted)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=False,  # To access the thinking, we have to disable the structured output
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/deepseek-ai/DeepSeek-R1",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/deepseek.svg",
            release_date=date(2025, 1, 20),
            quality_data=QualityData(mmlu=90.8, gpqa=71.5),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2435, duration_seconds=32.9),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("expensive"),
        ),
        # https://fireworks.ai/models/fireworks/deepseek-r1-basic
        Model.DEEPSEEK_R1_2501_BASIC: ModelData(
            display_name="DeepSeek R1 Basic (25-01) (US hosted)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=False,  # To access the thinking, we have to disable the structured output
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/deepseek-ai/DeepSeek-R1",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/deepseek.svg",
            release_date=date(2025, 3, 18),
            quality_data=QualityData(mmlu=90.8, gpqa=71.5),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2300, duration_seconds=67),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            fallback=ModelFallback.default("cheap"),
        ),
        # https://fireworks.ai/models/fireworks/deepseek-r1-0528
        Model.DEEPSEEK_R1_0528: ModelData(
            display_name="DeepSeek R1 (05-28) (US hosted)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=False,  # To access the thinking, we have to disable the structured output
            max_tokens_data=MaxTokensData(
                max_tokens=160_000,
                source="https://app.fireworks.ai/models/fireworks/deepseek-r1-0528",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/deepseek.svg",
            release_date=date(2025, 5, 28),
            quality_data=QualityData(
                equivalent_to=(  # TODO: adjust later, could not find score for MMLU nor GPQA
                    Model.DEEPSEEK_R1_2501,
                    5,
                ),
            ),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=2400, duration_seconds=31),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,  # Function calling not supported according to the spec
            fallback=ModelFallback.default("medium"),
        ),
        # https://fireworks.ai/models/fireworks/deepseek-v3-0324
        Model.DEEPSEEK_V3_0324: ModelData(
            display_name="DeepSeek V3 (03-24) (US hosted)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/deepseek-ai/DeepSeek-V3",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/deepseek.svg",
            release_date=date(2025, 3, 24),
            quality_data=QualityData(mmlu=88.5, gpqa=59.1),
            speed_data=SpeedData(
                index=SpeedIndex.from_experiment(output_tokens=1519, duration_seconds=8),
            ),
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            latest_model=Model.DEEPSEEK_V3_LATEST,
            supports_structured_output=True,
            fallback=ModelFallback.default("medium"),
        ),
        Model.DEEPSEEK_V3_LATEST: LatestModel(
            model=Model.DEEPSEEK_V3_0324,
            display_name="DeepSeek V3 (latest)",
        ),
        Model.IMAGEN_3_0_LATEST: LatestModel(
            model=Model.IMAGEN_3_0_002,
            display_name="Imagen 3.0 (latest)",
            is_default=True,
        ),
        Model.IMAGEN_3_0_002: ModelData(
            display_name="Imagen 3.0 (002)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_output_text=False,
            supports_output_image=True,
            max_tokens_data=MaxTokensData(
                max_tokens=480,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 1, 23),
            quality_data=QualityData(index=50),  # TODO: Update the quality index
            speed_data=SpeedData(
                index=SpeedIndex(value=10),  # Hard to estimate, assign low value
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=False,
            latest_model=Model.IMAGEN_3_0_LATEST,
            # No fallback for image generation
            fallback=None,
        ),
        Model.IMAGEN_3_0_001: ModelData(
            display_name="Imagen 3.0 (001)",
            supports_json_mode=False,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_output_text=False,
            supports_output_image=True,
            max_tokens_data=MaxTokensData(
                max_tokens=480,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2024, 7, 31),
            quality_data=QualityData(index=500),  # TODO: Update the quality index
            speed_data=SpeedData(
                index=SpeedIndex(value=10),  # Hard to estimate, assign low value
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=False,
            latest_model=Model.IMAGEN_3_0_LATEST,
            # No fallback for image generation
            fallback=None,
        ),
        Model.IMAGEN_3_0_FAST_001: ModelData(
            display_name="Imagen 3.0 ⚡ (001)",
            supports_json_mode=False,
            supports_input_image=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_output_text=False,
            supports_output_image=True,
            max_tokens_data=MaxTokensData(
                max_tokens=480,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/imagen-api",
            ),
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2024, 7, 31),
            quality_data=QualityData(index=500),  # TODO: Update the quality index
            speed_data=SpeedData(
                index=SpeedIndex(value=10),  # Hard to estimate, assign low value
            ),
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=False,
            fallback=None,  # No fallback for image generation
        ),
        **mistral_models(),
        **xai_models(),
    }


def _finalize_reasoning(model_data: ModelData):
    reasoning = model_data.reasoning
    if not reasoning:
        return None

    max_tokens = model_data.max_tokens_data.max_output_tokens or model_data.max_tokens_data.max_tokens

    max_budget = reasoning.max if "max" in reasoning.model_fields_set else max_tokens

    low_budget = reasoning.low if "low" in reasoning.model_fields_set else int(round(0.2 * max_budget))
    medium_budget = reasoning.medium if "medium" in reasoning.model_fields_set else int(round(0.5 * max_budget))
    high_budget = reasoning.high if "high" in reasoning.model_fields_set else int(round(0.8 * max_budget))

    min_budget = reasoning.min if "min" in reasoning.model_fields_set else low_budget

    return ModelReasoningBudget(
        disabled=reasoning.disabled,
        low=low_budget,
        medium=medium_budget,
        high=high_budget,
        min=min_budget or 1,
        max=max_budget,
    )


def _build_model_datas() -> ModelDataMapping:
    models = _raw_model_data()

    from .model_provider_data_mapping import MODEL_PROVIDER_DATAS

    def _map_model_data(model: Model, model_data: ModelData | LatestModel | DeprecatedModel):
        if isinstance(model_data, LatestModel):
            if not model_data.icon_url:
                mapped_data = models[model_data.model]
                if isinstance(mapped_data, ModelData):
                    model_data.icon_url = mapped_data.icon_url
            return model_data
        if not isinstance(model_data, ModelData):
            return model_data
        # Enumerating the provider enum to get the same order
        final_model_data = FinalModelData.model_validate(
            {
                **model_data.model_dump(),
                "model": model,
                "providers": [],
                "quality_index": model_data.quality_data.quality_index(models),
                "speed_index": model_data.speed_data.speed_index(models),
                "reasoning": _finalize_reasoning(model_data),
            },
        )
        for provider in Provider:
            data = MODEL_PROVIDER_DATAS[provider]
            try:
                final_model_data.providers.append((provider, data[model]))
            except KeyError:
                # Model is not supported by this provider
                continue
        return final_model_data

    return {model: _map_model_data(model, model_data) for model, model_data in models.items()}


MODEL_DATAS = _build_model_datas()


def _build_aliases() -> dict[str, Model]:
    out: dict[str, Model] = {}
    for k, m in MODEL_DATAS.items():
        if isinstance(m, LatestModel):
            out[k.value.removesuffix("-latest")] = k
        if m.aliases:
            for alias in m.aliases:
                out[alias] = k
    return out


MODEL_ALIASES = _build_aliases()


MODEL_COUNT = len([model for model in MODEL_DATAS.values() if isinstance(model, FinalModelData)])


def get_model_id(model: str) -> Model:
    if m := MODEL_ALIASES.get(model):
        return m

    try:
        return Model(model)
    except ValueError:
        raise ValueError(f"Invalid model: {model}")
