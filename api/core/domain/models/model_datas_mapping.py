from datetime import date
from enum import StrEnum

from core.domain.models import Model, Provider

from .model_data import DeprecatedModel, FinalModelData, LatestModel, MaxTokensData, ModelData


class DisplayedProvider(StrEnum):
    # Provider name displayed in the UI.
    # The link between a model and a displayed provider is arbitrary and configured manually in the model data.
    OPEN_AI = "OpenAI"
    ANTHROPIC = "Anthropic"
    FIREWORKS = "Fireworks"
    GOOGLE = "Google"
    MISTRAL_AI = "Mistral"
    GROQ = "Groq"
    AMAZON_BEDROCK = "Amazon Bedrock"


def _build_model_datas():
    models = {
        Model.GPT_4O_LATEST: LatestModel(
            model=Model.GPT_4O_2024_11_20,
            display_name="GPT-4o (latest)",
            is_default=True,
        ),
        Model.GPT_4O_2024_11_20: ModelData(
            display_name="GPT-4o (2024-11-20)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16_384,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            latest_model=Model.GPT_4O_LATEST,
            release_date=date(2024, 11, 20),
            quality_index=641,  # MMLU=85.70, GPQA=46.00
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
        ),
        Model.GPT_4O_2024_08_06: ModelData(
            display_name="GPT-4o (2024-08-06)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16_384,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2024, 8, 6),
            quality_index=674,  # MMLU=88.70, GPQA=53.10
            latest_model=Model.GPT_4O_LATEST,
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
        ),
        Model.GPT_45_PREVIEW_2025_02_27: ModelData(
            display_name="GPT-4.5-preview (2025-02-27)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16_384,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2025, 2, 27),
            quality_index=782,  # MMLU=85.10, GPQA=71.40
            latest_model=Model.GPT_4O_LATEST,
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
        ),
        Model.GPT_4O_2024_05_13: DeprecatedModel(replacement_model=Model.GPT_4O_2024_11_20),
        Model.GPT_4_TURBO_2024_04_09: DeprecatedModel(replacement_model=Model.GPT_4O_2024_11_20),
        Model.GPT_4_0125_PREVIEW: DeprecatedModel(replacement_model=Model.GPT_4O_2024_11_20),
        Model.GPT_4_1106_PREVIEW: DeprecatedModel(replacement_model=Model.GPT_4O_2024_11_20),
        Model.GPT_4O_MINI_LATEST: LatestModel(
            model=Model.GPT_4O_MINI_2024_07_18,
            display_name="GPT-4o mini (latest)",
        ),
        Model.GPT_4O_MINI_2024_07_18: ModelData(
            display_name="GPT-4o mini (2024-07-18)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16000,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            latest_model=Model.GPT_4O_MINI_LATEST,
            release_date=date(2024, 7, 18),
            quality_index=611,  # MMLU=82.00, GPQA=40.20
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
        ),
        Model.GPT_3_5_TURBO_0125: DeprecatedModel(replacement_model=Model.GPT_4O_MINI_2024_07_18),
        Model.GPT_3_5_TURBO_1106: DeprecatedModel(replacement_model=Model.GPT_4O_MINI_2024_07_18),
        Model.GPT_4_1106_VISION_PREVIEW: DeprecatedModel(replacement_model=Model.GPT_4O_2024_11_20),
        Model.GPT_4O_AUDIO_PREVIEW_2024_12_17: ModelData(
            display_name="GPT-4o (Audio Preview 2024-12-17)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            support_input_schema=False,
            supports_input_audio=True,
            supports_audio_only=True,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=16384,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            is_default=True,
            release_date=date(2024, 12, 17),
            provider_name=DisplayedProvider.OPEN_AI.value,
            quality_index=675,  # MMLU=88.70, GPQA=53.60
            supports_tool_calling=False,
        ),
        Model.GPT_40_AUDIO_PREVIEW_2024_10_01: DeprecatedModel(replacement_model=Model.GPT_4O_AUDIO_PREVIEW_2024_12_17),
        Model.O1_PREVIEW_2024_09_12: ModelData(
            display_name="o1-preview (2024-09-12)",
            supports_json_mode=False,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=32768,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2024, 9, 12),
            quality_index=833,  # MMLU=90.80, GPQA=78.30
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=False,  # OpenAI returns 400 "model_does_not_support_mode"
        ),
        Model.O1_MINI_LATEST: LatestModel(model=Model.O1_MINI_2024_09_12, display_name="o1-mini (latest)"),
        Model.O1_MINI_2024_09_12: ModelData(
            display_name="o1-mini (2024-09-12)",
            supports_json_mode=False,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128_000,
                max_output_tokens=65536,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            latest_model=Model.O1_MINI_LATEST,
            release_date=date(2024, 9, 12),
            quality_index=751,  # MMLU=85.20, GPQA=70.00
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=False,  # OpenAI returns 400 "model_does_not_support_mode"
        ),
        Model.O3_MINI_LATEST_HIGH_REASONING_EFFORT: LatestModel(
            model=Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT,
            display_name="o3-mini (latest) - High reasoning effort",
        ),
        Model.O3_MINI_LATEST_MEDIUM_REASONING_EFFORT: LatestModel(
            model=Model.O3_MINI_2025_01_31_MEDIUM_REASONING_EFFORT,
            display_name="o3-mini (latest) - Medium reasoning effort",
        ),
        Model.O3_MINI_LATEST_LOW_REASONING_EFFORT: LatestModel(
            model=Model.O3_MINI_2025_01_31_LOW_REASONING_EFFORT,
            display_name="o3-mini (latest) - Low reasoning effort",
        ),
        Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT: ModelData(
            display_name="o3-mini (2025-01-31) - High reasoning effort",
            supports_json_mode=False,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            release_date=date(2025, 1, 31),
            quality_index=833,  # MMLU=86.90, GPQA=79.70
            provider_name=DisplayedProvider.OPEN_AI.value,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            latest_model=Model.O3_MINI_LATEST_HIGH_REASONING_EFFORT,
            supports_tool_calling=True,
        ),
        Model.O3_MINI_2025_01_31_MEDIUM_REASONING_EFFORT: ModelData(
            display_name="o3-mini (2025-01-31) - Medium reasoning effort",
            supports_json_mode=False,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            release_date=date(2025, 1, 31),
            quality_index=828,  # MMLU=88.70, GPQA=77.00
            provider_name=DisplayedProvider.OPEN_AI.value,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            latest_model=Model.O3_MINI_LATEST_MEDIUM_REASONING_EFFORT,
            supports_tool_calling=True,
        ),
        Model.O3_MINI_2025_01_31_LOW_REASONING_EFFORT: ModelData(
            display_name="o3-mini (2025-01-31) - Low reasoning effort",
            supports_json_mode=False,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            release_date=date(2025, 1, 31),
            quality_index=780,  # MMLU=79.10, GPQA=77.00
            provider_name=DisplayedProvider.OPEN_AI.value,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            latest_model=Model.O3_MINI_LATEST_LOW_REASONING_EFFORT,
            supports_tool_calling=True,
        ),
        Model.GEMINI_1_5_PRO_PREVIEW_0514: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_2_0_FLASH_LITE_PREVIEW_2502: DeprecatedModel(replacement_model=Model.GEMINI_2_0_FLASH_LITE_001),
        Model.GEMINI_2_0_FLASH_LITE_001: ModelData(
            display_name="Gemini 2.0 Flash-Lite (001)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,
            max_tokens_data=MaxTokensData(
                max_tokens=1048576,
                max_output_tokens=8_192,
                source="https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.0-flash-lite",
            ),
            provider_for_pricing=Provider.GOOGLE,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 2, 5),
            quality_index=675,  # MMLU=83.50, GPQA=51.50
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_2_0_FLASH_001: ModelData(
            display_name="Gemini 2.0 Flash (001)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured outputs, but we did not activate this feature for Google  yet
            max_tokens_data=MaxTokensData(
                max_tokens=1048576,
                max_output_tokens=8_192,
                source="https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.0-flash",
            ),
            provider_for_pricing=Provider.GOOGLE,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 2, 5),
            latest_model=Model.GEMINI_2_0_FLASH_LATEST,
            quality_index=718,  # MMLU=76.40, GPQA=74.20
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_2_5_PRO_EXP_0325: ModelData(
            display_name="Gemini 2.5 Pro Exp (03-25)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,
            max_tokens_data=MaxTokensData(
                max_tokens=1_048_576 + 65_536,
                max_output_tokens=65_536,
                source="https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.0-pro",
            ),
            provider_for_pricing=Provider.GOOGLE_GEMINI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 3, 25),
            quality_index=842,  # 1 + GEMINI_2_0_PRO_EXP(MMLU=80.50, GPQA=64.70)
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_2_0_PRO_EXP: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO_EXP_0325),
        Model.GEMINI_2_0_FLASH_EXP: DeprecatedModel(replacement_model=Model.GEMINI_2_0_FLASH_001),
        Model.GEMINI_2_0_FLASH_LATEST: LatestModel(
            model=Model.GEMINI_2_0_FLASH_001,
            display_name="Gemini 2.0 Flash (latest)",
            is_default=True,
        ),
        Model.GEMINI_1_5_PRO_LATEST: LatestModel(
            model=Model.GEMINI_1_5_PRO_002,
            display_name="Gemini 1.5 Pro (latest)",
            is_default=True,
        ),
        Model.GEMINI_2_0_FLASH_THINKING_EXP_0121: ModelData(
            display_name="Gemini 2.0 Flash Thinking Exp (0121)",
            supports_json_mode=False,  # Json mode not supported for this model
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured outputs, but we did not activate this feature for Google  yet
            max_tokens_data=MaxTokensData(
                max_tokens=1048576,
                max_output_tokens=8_192,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#gemini-2.0-flash-thinking-mode",
            ),
            provider_for_pricing=Provider.GOOGLE_GEMINI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2025, 1, 21),
            quality_index=759,  # MMLU=77.60, GPQA=74.20
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=False,
        ),
        Model.GEMINI_2_0_FLASH_THINKING_EXP_1219: DeprecatedModel(
            replacement_model=Model.GEMINI_2_0_FLASH_THINKING_EXP_0121,
        ),
        Model.GEMINI_1_5_PRO_002: ModelData(
            display_name="Gemini 1.5 Pro (002)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured outputs, but we did not activate this feature for Google  yet
            max_tokens_data=MaxTokensData(
                max_tokens=2_097_152,
                max_output_tokens=8_192,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#gemini-1.5-pro",
            ),
            provider_for_pricing=Provider.GOOGLE,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            latest_model=Model.GEMINI_1_5_PRO_LATEST,
            release_date=date(2024, 9, 24),
            quality_index=721,  # MMLU=85.14, GPQA=59.10
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_1_5_PRO_001: ModelData(
            display_name="Gemini 1.5 Pro (001)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured outputs, but we did not activate this feature for Google  yet
            max_tokens_data=MaxTokensData(
                max_tokens=2_097_152,
                max_output_tokens=8_192,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#gemini-1.5-pro",
            ),
            provider_for_pricing=Provider.GOOGLE,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            latest_model=Model.GEMINI_1_5_PRO_LATEST,
            release_date=date(2024, 5, 24),
            quality_index=705,  # MMLU=81.90, GPQA=59.10
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_1_5_PRO_PREVIEW_0409: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_1_5_FLASH_PREVIEW_0514: DeprecatedModel(replacement_model=Model.GEMINI_1_5_FLASH_002),
        Model.GEMINI_1_5_FLASH_LATEST: LatestModel(
            model=Model.GEMINI_1_5_FLASH_002,
            display_name="Gemini 1.5 Flash (latest)",
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
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                # TODO: 64_000 in extended thinking mode
                # See https://docs.anthropic.com/en/docs/about-claude/models/all-models
                max_output_tokens=8192,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2025, 2, 19),
            # TODO: quality index, for now quality index of CLAUDE_3_5_SONNET_20241022 + 1
            quality_index=878,  # MMLU=90.80, GPQA=84.80
            latest_model=Model.CLAUDE_3_7_SONNET_LATEST,
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
        ),
        Model.CLAUDE_3_5_SONNET_20241022: ModelData(
            display_name="Claude 3.5 Sonnet (2024-10-22)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=8192,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2024, 10, 22),
            quality_index=768,  # MMLU=86.00, GPQA=68.00
            latest_model=Model.CLAUDE_3_5_SONNET_LATEST,
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_1_5_FLASH_002: ModelData(
            display_name="Gemini 1.5 Flash (002)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured outputs, but we did not activate this feature for Google  yet
            max_tokens_data=MaxTokensData(
                max_tokens=1048576,
                max_output_tokens=8192,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#gemini-1.5-flash",
            ),
            provider_for_pricing=Provider.GOOGLE,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            latest_model=Model.GEMINI_1_5_FLASH_LATEST,
            release_date=date(2024, 9, 24),
            quality_index=650,  # MMLU=78.90, GPQA=51.00
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_1_5_FLASH_001: ModelData(
            display_name="Gemini 1.5 Flash (001)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured outputs, but we did not activate this feature for Google  yet
            max_tokens_data=MaxTokensData(
                max_tokens=1048576,
                max_output_tokens=8192,
                source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#gemini-1.5-flash",
            ),
            provider_for_pricing=Provider.GOOGLE,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            latest_model=Model.GEMINI_1_5_FLASH_LATEST,
            release_date=date(2024, 5, 24),
            quality_index=650,  # MMLU=78.90, GPQA=51.00
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_1_0_PRO_VISION_001: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_1_0_PRO_001: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.GEMINI_1_0_PRO_002: DeprecatedModel(replacement_model=Model.GEMINI_1_5_PRO_002),
        Model.CLAUDE_3_5_SONNET_LATEST: LatestModel(
            model=Model.CLAUDE_3_5_SONNET_20241022,
            display_name="Claude 3.5 Sonnet (latest)",
        ),
        Model.O1_2024_12_17_MEDIUM_REASONING_EFFORT: ModelData(
            display_name="o1 (2024-12-17) - Medium reasoning effort",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models/gp#o1",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2024, 12, 17),
            quality_index=839,  # MMLU=90.80, GPQA=78.30
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
        ),
        Model.O1_2024_12_17_HIGH_REASONING_EFFORT: ModelData(
            display_name="o1 (2024-12-17) - High reasoning effort",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models/gp#o1",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2024, 12, 17),
            quality_index=853,  # MMLU=87.00, GPQA=91.60
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
        ),
        Model.O1_2024_12_17_LOW_REASONING_EFFORT: ModelData(
            display_name="o1 (2024-12-17) - Low reasoning effort",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=200_000,
                max_output_tokens=100_000,
                source="https://platform.openai.com/docs/models/gp#o1",
            ),
            provider_for_pricing=Provider.OPEN_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
            release_date=date(2024, 12, 17),
            quality_index=798,  # MMLU=84.10, GPQA=78.00
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
        ),
        Model.CLAUDE_3_5_SONNET_20240620: ModelData(
            display_name="Claude 3.5 Sonnet (2024-06-20)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=4096,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            latest_model=Model.CLAUDE_3_5_SONNET_LATEST,
            release_date=date(2024, 6, 20),
            quality_index=738,  # MMLU=88.30, GPQA=59.40
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
        ),
        Model.CLAUDE_3_OPUS_20240229: ModelData(
            display_name="Claude 3 Opus (2024-02-29)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=4096,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2024, 2, 29),
            quality_index=693,  # MMLU=88.20, GPQA=50.40
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
        ),
        Model.CLAUDE_3_SONNET_20240229: ModelData(
            display_name="Claude 3 Sonnet (2024-02-29)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=4096,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2024, 2, 29),
            quality_index=704,  # MMLU=81.50, GPQA=59.40
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
        ),
        Model.CLAUDE_3_HAIKU_20240307: ModelData(
            display_name="Claude 3 Haiku (2024-03-07)",
            supports_json_mode=False,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=4096,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            release_date=date(2024, 3, 7),
            quality_index=550,  #  MMLU=76.7, GPQA=33.3
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
        ),
        Model.CLAUDE_3_5_HAIKU_LATEST: LatestModel(
            model=Model.CLAUDE_3_5_HAIKU_20241022,
            display_name="Claude 3.5 Haiku (latest)",
        ),
        Model.CLAUDE_3_5_HAIKU_20241022: ModelData(
            display_name="Claude 3.5 Haiku (2024-10-22)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=200000,
                max_output_tokens=8192,
                source="https://docs.anthropic.com/en/docs/about-claude/models",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/anthropic.svg",
            latest_model=Model.CLAUDE_3_5_HAIKU_LATEST,
            release_date=date(2024, 10, 22),
            quality_index=595,  # MMLU=76.7, QPAQ=41.6
            provider_name=DisplayedProvider.ANTHROPIC.value,
            supports_tool_calling=True,
        ),
        # https://fireworks.ai/models/fireworks/llama-v3-70b-instruct
        Model.LLAMA3_70B_8192: ModelData(
            display_name="Llama 3 (70B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=8192,
                source="https://learn.microsoft.com/en-us/azure/ai-studio/how-to/deploy-models-llama?tabs=llama-three, could not find specific Groq info",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 4, 18),
            quality_index=635,  # MMLU=82.00, GPQA=50.50
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
        ),
        Model.LLAMA3_8B_8192: ModelData(
            display_name="Llama 3 (8B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=8192,
                source="https://learn.microsoft.com/en-us/azure/ai-studio/how-to/deploy-models-llama?tabs=llama-three, could not find specific Groq info",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 4, 18),
            quality_index=470,  # MMLU=68.40, GPQA=44.00
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
        ),
        Model.MIXTRAL_8X7B_32768: ModelData(
            display_name="Mixtral (8x7B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=32768,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/mixtral-8x7b-instruct",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/mistral.svg",
            release_date=date(2023, 12, 11),
            quality_index=468,  # MMLU=70.60, GPQA=39.00
            provider_name=DisplayedProvider.MISTRAL_AI.value,
            supports_tool_calling=False,
        ),
        Model.LLAMA_3_1_405B: ModelData(
            display_name="Llama 3.1 (405B)",
            supports_json_mode=False,  # 405b does not support JSON mode for now https://www.together.ai/blog/meta-llama-3-1
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 7, 23),
            quality_index=754,  # MMLU=88.60, GPQA=73.90
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
        ),
        # https://fireworks.ai/models/fireworks/llama-v3p3-70b-instruct
        Model.LLAMA_3_3_70B: ModelData(
            display_name="Llama 3.3 (70B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=131072,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/llama-v3p3-70b-instruct",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 12, 6),
            quality_index=682,  # MMLU=86.00, GPQA=50.50
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
        ),
        # https://fireworks.ai/models/fireworks/llama-v3p1-70b-instruct
        Model.LLAMA_3_1_70B: ModelData(
            display_name="Llama 3.1 (70B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 7, 23),
            quality_index=654,  # MMLU=86.00, GPQA=48.00
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
        ),
        # https://fireworks.ai/models/fireworks/llama-v3p1-8b-instruct
        Model.LLAMA_3_1_8B: ModelData(
            display_name="Llama 3.1 (8B)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=131072,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/llama-v3p1-8b-instruct",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 7, 23),
            quality_index=494,  # MMLU=66.70, GPQA=33.80
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
        ),
        Model.LLAMA_3_2_90B: ModelData(
            display_name="Llama 3.2 (90B) Instruct",
            supports_json_mode=False,
            supports_input_image=True,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://console.cloud.google.com/vertex-ai/publishers/meta/model-garden/llama3-2",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,  # TODO: fixeworks
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 9, 25),
            quality_index=664,  # MMLU=86.00, GPQA=46.70
            provider_name=DisplayedProvider.AMAZON_BEDROCK.value,
            supports_tool_calling=True,
        ),
        Model.LLAMA_3_2_11B: ModelData(
            display_name="Llama 3.2 (11B) Instruct",
            supports_json_mode=False,
            supports_input_image=True,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://us-west-2.console.aws.amazon.com/bedrock/home?region=us-west-2#/providers?model=meta.llama3-2-11b-instruct-v1:0",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,  # TODO: fixeworks
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 9, 25),
            quality_index=529,  # MMLU=73.00, GPQA=32.80
            provider_name=DisplayedProvider.AMAZON_BEDROCK.value,
            supports_tool_calling=False,
        ),
        Model.LLAMA_3_2_3B: ModelData(
            display_name="Llama 3.2 (3B) Instruct",
            supports_json_mode=False,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=131072,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/llama-v3p2-3b-instruct",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 9, 25),
            quality_index=483,  # MMLU=63.40, GPQA=33.80
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
        ),
        Model.LLAMA_3_2_1B: ModelData(
            display_name="Llama 3.2 (1B) Instruct",
            supports_json_mode=False,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=131000,
                source="https://us-west-2.console.aws.amazon.com/bedrock/home?region=us-west-2#/providers?model=meta.llama3-2-1b-instruct-v1:0",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,  # TODO: fixeworks
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 9, 25),
            quality_index=368,  # MMLU=49.30, GPQA=27.20
            provider_name=DisplayedProvider.AMAZON_BEDROCK.value,
            supports_tool_calling=False,
        ),
        Model.LLAMA_3_2_90B_TEXT_PREVIEW: DeprecatedModel(replacement_model=Model.LLAMA_3_2_90B_VISION_PREVIEW),
        Model.LLAMA_3_2_11B_TEXT_PREVIEW: DeprecatedModel(replacement_model=Model.LLAMA_3_2_90B_VISION_PREVIEW),
        # https://fireworks.ai/models/fireworks/llama-v3p2-3b
        Model.LLAMA_3_2_3B_PREVIEW: ModelData(
            display_name="Llama 3.2 (3B) Preview",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=131072,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/llama-v3p2-3b-instruct",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 9, 25),
            quality_index=481,  # MMLU=63.40, GPQA=32.80
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
        ),
        Model.LLAMA_3_2_1B_PREVIEW: DeprecatedModel(replacement_model=Model.LLAMA_3_2_1B),
        Model.LLAMA_3_2_90B_VISION_PREVIEW: ModelData(
            # TODO: Add support for images via Groq Provider
            display_name="Llama 3.2 (90B) Vision Preview",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=131072,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/llama-v3p2-90b-vision-instruct",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 9, 25),
            quality_index=694,  # MMLU=86.00, GPQA=59.10
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
        ),
        Model.MISTRAL_LARGE_2_LATEST: LatestModel(
            model=Model.MISTRAL_LARGE_2_2407,
            display_name="Mistral Large 2 (latest)",
        ),
        Model.MISTRAL_LARGE_2_2407: ModelData(
            display_name="Mistral Large 2 (24-07)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://mistral.ai/news/mistral-large-2407/",
            ),
            provider_for_pricing=Provider.AMAZON_BEDROCK,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/mistral.svg",
            latest_model=Model.MISTRAL_LARGE_2_LATEST,
            release_date=date(2024, 7, 24),
            quality_index=549,  # MMLU=84.00, GPQA=46.09
            provider_name=DisplayedProvider.MISTRAL_AI.value,
            supports_tool_calling=True,
        ),
        Model.PIXTRAL_12B_2409: ModelData(
            display_name="PixTral (12B-2409)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://docs.mistral.ai/getting-started/models/",
            ),
            provider_for_pricing=Provider.MISTRAL_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/mistral.svg",
            release_date=date(2024, 9, 17),
            quality_index=526,  # MMLU=69.20, GPQA=39.00
            provider_name=DisplayedProvider.MISTRAL_AI.value,
            supports_tool_calling=True,
        ),
        Model.MINISTRAL_3B_2410: ModelData(
            display_name="MiniStral (3B-2410)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://docs.mistral.ai/getting-started/models/",
            ),
            provider_for_pricing=Provider.MISTRAL_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/mistral.svg",
            release_date=date(2024, 10, 24),
            quality_index=317,  # MMLU=33.90, GPQA=33.59
            provider_name=DisplayedProvider.MISTRAL_AI.value,
            supports_tool_calling=True,
        ),
        Model.MINISTRAL_8B_2410: ModelData(
            display_name="MiniStral (8B-2410)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://docs.mistral.ai/getting-started/models/",
            ),
            provider_for_pricing=Provider.MISTRAL_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/mistral.svg",
            release_date=date(2024, 10, 24),
            quality_index=426,  # MMLU=63.40, GPQA=33.80
            provider_name=DisplayedProvider.MISTRAL_AI.value,
            supports_tool_calling=True,
        ),
        Model.MISTRAL_SMALL_2409: ModelData(
            display_name="Mistral Small (24-09)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=32768,
                source="https://docs.mistral.ai/getting-started/models/",
            ),
            provider_for_pricing=Provider.MISTRAL_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/mistral.svg",
            release_date=date(2024, 9, 24),
            quality_index=377,  # MMLU=52.90, GPQA=33.80
            provider_name=DisplayedProvider.MISTRAL_AI.value,
            supports_tool_calling=True,
        ),
        Model.CODESTRAL_MAMBA_2407: ModelData(
            display_name="CodeStral Mamba (24-07)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=32768,
                # source="https://docs.mistral.ai/getting-started/models/",
                # NOTE: The site states 256k context window but the Mistral models API + testing seems to point towards a context of 32768 as of now
                source="https://api.mistral.ai/v1/models",
            ),
            provider_for_pricing=Provider.MISTRAL_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/mistral.svg",
            release_date=date(2024, 7, 24),
            quality_index=481,  # MMLU=63.47, GPQA=38.35
            provider_name=DisplayedProvider.MISTRAL_AI.value,
            supports_tool_calling=True,
        ),
        Model.MISTRAL_LARGE_LATEST: LatestModel(
            model=Model.MISTRAL_LARGE_2411,
            display_name="Mistral Large (latest)",
        ),
        Model.PIXTRAL_LARGE_LATEST: LatestModel(
            model=Model.PIXTRAL_LARGE_2411,
            display_name="PixTral Large (latest)",
        ),
        Model.PIXTRAL_LARGE_2411: ModelData(
            display_name="PixTral Large (24-11)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://docs.mistral.ai/getting-started/models/",
            ),
            provider_for_pricing=Provider.MISTRAL_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/mistral.svg",
            latest_model=Model.PIXTRAL_LARGE_LATEST,
            release_date=date(2024, 11, 24),
            quality_index=531,  # MMLU=70.10, GPQA=39.30
            provider_name=DisplayedProvider.MISTRAL_AI.value,
            supports_tool_calling=True,
        ),
        Model.MISTRAL_LARGE_2411: ModelData(
            display_name="Mistral Large 2 (24-11)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://docs.mistral.ai/getting-started/models/",
            ),
            provider_for_pricing=Provider.MISTRAL_AI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/mistral.svg",
            latest_model=Model.MISTRAL_LARGE_LATEST,
            release_date=date(2024, 11, 24),
            quality_index=702,  # MMLU=84.00, GPQA=59.10
            provider_name=DisplayedProvider.MISTRAL_AI.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_1_5_FLASH_8B: ModelData(
            display_name="Gemini 1.5 Flash (8B)",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            supports_structured_output=False,  # Model supports structured output but we did not activate for Gemini yet
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://ai.google.dev/gemini-api/docs/models/gemini",
            ),
            provider_for_pricing=Provider.GOOGLE_GEMINI,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/google.svg",
            release_date=date(2024, 10, 3),
            quality_index=485,  # MMLU=58.7, GPQA=38.4
            provider_name=DisplayedProvider.GOOGLE.value,
            supports_tool_calling=True,
        ),
        Model.GEMINI_EXP_1206: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO_EXP_0325),
        Model.GEMINI_EXP_1121: DeprecatedModel(replacement_model=Model.GEMINI_2_5_PRO_EXP_0325),
        Model.QWEN_QWQ_32B_PREVIEW: ModelData(
            display_name="Qwen QWQ (32B) Preview",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=32768,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/qwen-qwq-32b-preview",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/qwen.svg",
            release_date=date(2024, 11, 28),
            quality_index=693,  # MMLU=83.30, GPQA=59.10
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
        ),
        Model.LLAMA_3_2_11B_VISION: ModelData(
            display_name="Llama 3.2 (11B) Vision",
            supports_json_mode=True,
            supports_input_image=True,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=True,
            max_tokens_data=MaxTokensData(
                max_tokens=131072,
                source="https://api.fireworks.ai/v1/accounts/fireworks/models/llama-v3p2-11b-vision-instruct",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/meta.svg",
            release_date=date(2024, 9, 25),
            quality_index=598,  # MMLU=73.00, GPQA=46.70
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=False,
        ),
        # https://fireworks.ai/models/fireworks/deepseek-v3
        Model.DEEPSEEK_V3_2412: ModelData(
            display_name="DeepSeek V3 (24-12) (US hosted)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/deepseek-ai/DeepSeek-V3",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/deepseek.svg",
            release_date=date(2024, 12, 30),
            quality_index=738,  # MMLU=88.50, GPQA=59.10
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            supports_structured_output=True,
            latest_model=Model.DEEPSEEK_V3_LATEST,
        ),
        # https://fireworks.ai/models/fireworks/deepseek-r1
        Model.DEEPSEEK_R1_2501: ModelData(
            display_name="DeepSeek R1 (25-01) (US hosted)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=False,  # To access the thinking, we have to disable the structured output
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/deepseek-ai/DeepSeek-R1",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/deepseek.svg",
            release_date=date(2025, 1, 20),
            quality_index=812,  # MMLU=90.80, GPQA=71.50
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
        ),
        # https://fireworks.ai/models/fireworks/deepseek-r1-basic
        Model.DEEPSEEK_R1_2501_BASIC: ModelData(
            display_name="DeepSeek R1 Basic (25-01) (US hosted)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            supports_structured_output=False,  # To access the thinking, we have to disable the structured output
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/deepseek-ai/DeepSeek-R1",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/deepseek.svg",
            release_date=date(2025, 3, 18),
            quality_index=812,  # MMLU=90.80, GPQA=71.50
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
        ),
        # https://fireworks.ai/models/fireworks/deepseek-v3-0324
        Model.DEEPSEEK_V3_0324: ModelData(
            display_name="DeepSeek V3 (03-24) (US hosted)",
            supports_json_mode=True,
            supports_input_image=False,
            supports_multiple_images_in_input=False,
            supports_input_pdf=False,
            supports_input_audio=False,
            max_tokens_data=MaxTokensData(
                max_tokens=128000,
                source="https://github.com/deepseek-ai/DeepSeek-V3",
            ),
            provider_for_pricing=Provider.FIREWORKS,
            icon_url="https://workflowai.blob.core.windows.net/workflowai-public/deepseek.svg",
            release_date=date(2025, 3, 24),
            # TODO: Update the quality index once the values are out
            quality_index=739,  # MMLU=88.50, GPQA=59.10
            provider_name=DisplayedProvider.FIREWORKS.value,
            supports_tool_calling=True,
            latest_model=Model.DEEPSEEK_V3_LATEST,
            supports_structured_output=True,
        ),
        Model.DEEPSEEK_V3_LATEST: LatestModel(
            model=Model.DEEPSEEK_V3_0324,
            display_name="DeepSeek V3 (latest)",
        ),
    }

    from .model_provider_datas_mapping import MODEL_PROVIDER_DATAS

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
        final_model_data = FinalModelData.model_validate({**model_data.model_dump(), "model": model, "providers": []})
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
