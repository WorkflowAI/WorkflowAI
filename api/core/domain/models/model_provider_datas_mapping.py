import datetime

from core.domain.models import Model, Provider
from core.providers.google.google_provider_domain import GOOGLE_CHARS_PER_TOKEN

from .model_provider_data import (
    AudioPricePerSecond,
    AudioPricePerToken,
    ImageFixedPrice,
    LifecycleData,
    ModelDataSupportsOverride,
    ModelProviderData,
    TextPricePerToken,
    ThresholdedAudioPricePerSecond,
    ThresholdedImageFixedPrice,
    ThresholdedTextPricePerToken,
)

ProviderDataByModel = dict[Model, ModelProviderData]
ONE_MILLION_TH = 0.000_001


GOOGLE_PROVIDER_DATA: ProviderDataByModel = {
    # Although it seems that Vertex supports the models
    # They return a lot of 429 errors so it is just better to use GEMINI for now
    # Model.GEMINI_2_5_PRO_PREVIEW_0325: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=1.25 / 1_000_000,
    #         completion_cost_per_token=10 / 1_000_000,
    #         source="https://cloud.google.com/vertex-ai/generative-ai/pricing#modality-based-pricing",
    #         thresholded_prices=[
    #             ThresholdedTextPricePerToken(
    #                 threshold=200_000,
    #                 prompt_cost_per_token_over_threshold=2.5 / 1_000_000,
    #                 completion_cost_per_token_over_threshold=15 / 1_000_000,
    #             ),
    #         ],
    #     ),
    # ),
    # Model.GEMINI_2_5_FLASH_PREVIEW_0417: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.15 * ONE_MILLION_TH,
    #         completion_cost_per_token=0.60 * ONE_MILLION_TH,
    #         source="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash",
    #     ),
    #     audio_price=AudioPricePerToken(
    #         audio_input_cost_per_token=1.0 * ONE_MILLION_TH,
    #     ),
    # ),
    # Model.GEMINI_2_5_FLASH_THINKING_PREVIEW_0417: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.15 * ONE_MILLION_TH,
    #         completion_cost_per_token=3.50 * ONE_MILLION_TH,
    #         source="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash",
    #     ),
    #     audio_price=AudioPricePerToken(
    #         audio_input_cost_per_token=1.0 * ONE_MILLION_TH,
    #     ),
    # ),
    Model.GEMINI_2_0_FLASH_001: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.0375 * ONE_MILLION_TH * GOOGLE_CHARS_PER_TOKEN,
            completion_cost_per_token=0.15 * ONE_MILLION_TH * GOOGLE_CHARS_PER_TOKEN,
            source="https://cloud.google.com/vertex-ai/generative-ai/pricing",
        ),
        image_price=ImageFixedPrice(
            cost_per_image=0.000_193_5,
        ),
        audio_price=AudioPricePerSecond(
            cost_per_second=0.000_025,
        ),
    ),
    Model.GEMINI_2_0_FLASH_LITE_001: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.01875 * ONE_MILLION_TH * GOOGLE_CHARS_PER_TOKEN,
            completion_cost_per_token=0.075 * ONE_MILLION_TH * GOOGLE_CHARS_PER_TOKEN,
            source="https://cloud.google.com/vertex-ai/generative-ai/pricing",
        ),
        image_price=ImageFixedPrice(
            cost_per_image=0.000_096_75,
        ),
        audio_price=AudioPricePerSecond(
            cost_per_second=0.000_001_875,
        ),
    ),
    Model.GEMINI_1_5_PRO_001: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_312_5 * GOOGLE_CHARS_PER_TOKEN,
            completion_cost_per_token=0.000_001_25 * GOOGLE_CHARS_PER_TOKEN,
            thresholded_prices=[
                # Price per token > 128k
                ThresholdedTextPricePerToken(
                    threshold=128_000,
                    prompt_cost_per_token_over_threshold=0.000_000_625 * GOOGLE_CHARS_PER_TOKEN,
                    completion_cost_per_token_over_threshold=0.000_002_5 * GOOGLE_CHARS_PER_TOKEN,
                ),
            ],
            source="https://cloud.google.com/vertex-ai/generative-ai/pricing",
        ),
        image_price=ImageFixedPrice(
            cost_per_image=0.000_328_75,
            thresholded_prices=[
                ThresholdedImageFixedPrice(threshold=128000, cost_per_image_over_threshold=0.000_6575),
            ],
        ),
        audio_price=AudioPricePerSecond(
            cost_per_second=0.000_031_25,
            thresholded_prices=[
                ThresholdedAudioPricePerSecond(threshold=128000, cost_per_second_over_threshold=0.000_0625),
            ],
        ),
        lifecycle_data=LifecycleData(
            release_date=datetime.date(year=2024, month=5, day=24),
            sunset_date=datetime.date(year=2025, month=5, day=24),
            source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#model_versions_and_lifecycle",
            post_sunset_replacement_model=Model.GEMINI_1_5_PRO_002,
        ),
    ),
    Model.GEMINI_1_5_PRO_002: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_312_5 * GOOGLE_CHARS_PER_TOKEN,
            completion_cost_per_token=0.000_001_25 * GOOGLE_CHARS_PER_TOKEN,
            thresholded_prices=[
                # Price per token > 128k
                ThresholdedTextPricePerToken(
                    threshold=128_000,
                    prompt_cost_per_token_over_threshold=0.000_000_625 * GOOGLE_CHARS_PER_TOKEN,
                    completion_cost_per_token_over_threshold=0.000_002_5 * GOOGLE_CHARS_PER_TOKEN,
                ),
            ],
            source="https://cloud.google.com/vertex-ai/generative-ai/pricing",
        ),
        image_price=ImageFixedPrice(
            cost_per_image=0.000_328_75,
            thresholded_prices=[
                ThresholdedImageFixedPrice(threshold=128000, cost_per_image_over_threshold=0.000_6575),
            ],
        ),
        audio_price=AudioPricePerSecond(
            cost_per_second=0.000_031_25,
            thresholded_prices=[
                ThresholdedAudioPricePerSecond(threshold=128000, cost_per_second_over_threshold=0.000_0625),
            ],
        ),
        lifecycle_data=LifecycleData(
            release_date=datetime.date(year=2024, month=9, day=24),
            sunset_date=datetime.date(year=2025, month=9, day=24),
            source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#model_versions_and_lifecycle",
        ),
    ),
    Model.GEMINI_1_5_FLASH_001: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_018_75 * GOOGLE_CHARS_PER_TOKEN,
            completion_cost_per_token=0.000_000_075 * GOOGLE_CHARS_PER_TOKEN,
            thresholded_prices=[
                ThresholdedTextPricePerToken(
                    threshold=128000,
                    prompt_cost_per_token_over_threshold=0.000_000_037_5 * GOOGLE_CHARS_PER_TOKEN,
                    completion_cost_per_token_over_threshold=0.000_000_15 * GOOGLE_CHARS_PER_TOKEN,
                ),
            ],
            source="https://cloud.google.com/vertex-ai/generative-ai/pricing",
        ),
        image_price=ImageFixedPrice(
            cost_per_image=0.000_02,
            thresholded_prices=[
                ThresholdedImageFixedPrice(threshold=128000, cost_per_image_over_threshold=0.000_04),
            ],
        ),
        audio_price=AudioPricePerSecond(
            cost_per_second=0.000_002,
            thresholded_prices=[
                ThresholdedAudioPricePerSecond(threshold=128000, cost_per_second_over_threshold=0.000_004),
            ],
        ),
        lifecycle_data=LifecycleData(
            release_date=datetime.date(year=2024, month=5, day=24),
            sunset_date=datetime.date(year=2025, month=5, day=24),
            source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#model_versions_and_lifecycle",
            post_sunset_replacement_model=Model.GEMINI_2_0_FLASH_001,
        ),
    ),
    Model.GEMINI_1_5_FLASH_002: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_018_75 * GOOGLE_CHARS_PER_TOKEN,
            completion_cost_per_token=0.000_000_075 * GOOGLE_CHARS_PER_TOKEN,
            thresholded_prices=[
                ThresholdedTextPricePerToken(
                    threshold=128000,
                    prompt_cost_per_token_over_threshold=0.000_000_037_5 * GOOGLE_CHARS_PER_TOKEN,
                    completion_cost_per_token_over_threshold=0.000_000_15 * GOOGLE_CHARS_PER_TOKEN,
                ),
            ],
            source="https://cloud.google.com/vertex-ai/generative-ai/pricing",
        ),
        image_price=ImageFixedPrice(
            cost_per_image=0.000_02,
            thresholded_prices=[
                ThresholdedImageFixedPrice(threshold=128000, cost_per_image_over_threshold=0.000_04),
            ],
        ),
        audio_price=AudioPricePerSecond(
            cost_per_second=0.000_002,
            thresholded_prices=[
                ThresholdedAudioPricePerSecond(threshold=128000, cost_per_second_over_threshold=0.000_004),
            ],
        ),
        lifecycle_data=LifecycleData(
            release_date=datetime.date(year=2024, month=9, day=24),
            sunset_date=datetime.date(year=2025, month=9, day=24),
            source="https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models#model_versions_and_lifecycle",
            post_sunset_replacement_model=Model.GEMINI_2_0_FLASH_001,
        ),
    ),
    Model.LLAMA_3_1_405B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_005,
            completion_cost_per_token=0.000_016,
            source="https://cloud.google.com/vertex-ai/generative-ai/pricing#meta-models",
        ),
    ),
}


OPENAI_PROVIDER_DATA: ProviderDataByModel = {
    Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=4.40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O3_MINI_2025_01_31_MEDIUM_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=4.40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O3_MINI_2025_01_31_LOW_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=4.40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O3_2025_04_16_HIGH_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.75,
            completion_cost_per_token=40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O3_2025_04_16_MEDIUM_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.75,
            completion_cost_per_token=40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O3_2025_04_16_LOW_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.75,
            completion_cost_per_token=40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O4_MINI_2025_04_16_HIGH_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.1 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.75,
            completion_cost_per_token=4.4 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O4_MINI_2025_04_16_MEDIUM_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.1 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.75,
            completion_cost_per_token=4.4 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O4_MINI_2025_04_16_LOW_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.1 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.75,
            completion_cost_per_token=4.4 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_2024_12_17_LOW_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=15 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=60 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_2024_12_17_MEDIUM_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=15 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=60 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_2024_12_17_HIGH_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=15 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=60 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_4O_2024_11_20: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_002_5,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=0.000_010,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_4O_2024_08_06: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_002_5,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=0.000_010,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_41_2025_04_14: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=2 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.75,
            completion_cost_per_token=8 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_41_MINI_2025_04_14: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.4 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.75,
            completion_cost_per_token=1.6 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_41_NANO_2025_04_14: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.1 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.75,
            completion_cost_per_token=0.4 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_45_PREVIEW_2025_02_27: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=75 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=150 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_4O_MINI_2024_07_18: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_15,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=0.000_000_6,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_PREVIEW_2024_09_12: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_015,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=0.000_060,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_MINI_2024_09_12: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=4.40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_4O_AUDIO_PREVIEW_2024_12_17: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=2.5 * ONE_MILLION_TH,
            completion_cost_per_token=10 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
        audio_price=AudioPricePerToken(
            audio_input_cost_per_token=40 * ONE_MILLION_TH,
        ),
    ),
    # Model.GPT_40_AUDIO_PREVIEW_2024_10_01: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=2.5 * ONE_MILLION_TH,
    #         completion_cost_per_token=10 * ONE_MILLION_TH,
    #         source="https://openai.com/api/pricing/",
    #     ),
    #     audio_price=AudioPricePerToken(
    #         audio_input_cost_per_token=100 * ONE_MILLION_TH,
    #     ),
    # ),
}

OPENAI_IMAGE_PROVIDER_DATA: ProviderDataByModel = {
    Model.GPT_IMAGE_1: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=5 * ONE_MILLION_TH,
            prompt_image_cost_per_token=10 * ONE_MILLION_TH,
            completion_cost_per_token=0,  # GPT Image 1 does not generate text
            completion_image_cost_per_token=40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
}

AMAZON_BEDROCK_PROVIDER_DATA: ProviderDataByModel = {
    Model.CLAUDE_3_7_SONNET_20250219: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_003,
            completion_cost_per_token=0.000_015,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
        supports_override=ModelDataSupportsOverride(
            supports_input_pdf=False,
        ),
    ),
    Model.CLAUDE_3_5_SONNET_20241022: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_003,
            completion_cost_per_token=0.000_015,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
        supports_override=ModelDataSupportsOverride(
            supports_input_pdf=False,
        ),
    ),
    Model.CLAUDE_3_5_SONNET_20240620: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_003,
            completion_cost_per_token=0.000_015,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
    ),
    Model.CLAUDE_3_OPUS_20240229: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_015,
            completion_cost_per_token=0.000_075,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
    ),
    # Model.CLAUDE_3_SONNET_20240229: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_003,
    #         completion_cost_per_token=0.000_015,
    #         source="https://aws.amazon.com/bedrock/pricing/",
    #     ),
    #     lifecycle_data=LifecycleData(
    #         sunset_date=datetime.date(year=2025, month=7, day=20),
    #         source="https://aws.amazon.com/bedrock/pricing/",
    #         post_sunset_replacement_model=Model.CLAUDE_3_5_SONNET_20241022,
    #     ),
    # ),
    Model.CLAUDE_3_HAIKU_20240307: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_25,
            completion_cost_per_token=0.000_00125,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
    ),
    Model.CLAUDE_3_5_HAIKU_20241022: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_8,
            completion_cost_per_token=0.000_004,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
    ),
    Model.LLAMA_3_1_405B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_002_40,
            completion_cost_per_token=0.000_002_40,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
    ),
    Model.LLAMA_3_1_70B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_72,
            completion_cost_per_token=0.000_000_72,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
    ),
    Model.LLAMA_3_1_8B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_22,
            completion_cost_per_token=0.000_000_22,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
    ),
    Model.MISTRAL_LARGE_2_2407: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_002,
            completion_cost_per_token=0.000_006,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
    ),
    # Model.LLAMA_3_2_90B: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_72,
    #         completion_cost_per_token=0.000_000_72,
    #         source="https://aws.amazon.com/bedrock/pricing/",
    #     ),
    # ),
    # Model.LLAMA_3_2_11B: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_16,
    #         completion_cost_per_token=0.000_000_16,
    #         source="https://aws.amazon.com/bedrock/pricing/",
    #     ),
    # ),
    # Model.LLAMA_3_2_3B: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_15,
    #         completion_cost_per_token=0.000_000_15,
    #         source="https://aws.amazon.com/bedrock/pricing/",
    #     ),
    # ),
    Model.LLAMA_3_3_70B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_72,
            completion_cost_per_token=0.000_000_72,
            source="https://aws.amazon.com/bedrock/pricing/",
        ),
    ),
    # Model.LLAMA_3_2_1B: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_1,
    #         completion_cost_per_token=0.000_000_1,
    #         source="https://aws.amazon.com/bedrock/pricing/",
    #     ),
    # ),
}

GROQ_PROVIDER_DATA: ProviderDataByModel = {
    # Model.LLAMA3_70B_8192: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_59,
    #         completion_cost_per_token=0.000_000_79,
    #         source="https://console.groq.com/settings/billing",
    #     ),
    #     # native tools calls are not implemented on Groq for now as we will decommssion the provider for now.
    #     # see [WOR-1968: Disable `Groq` ?](https://linear.app/workflowai/issue/WOR-1968/disable-groq)
    # ),
    # Model.LLAMA3_8B_8192: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_05,
    #         completion_cost_per_token=0.000_000_08,
    #         source="https://console.groq.com/settings/billing",
    #     ),
    #     # native tools calls are not implemented on Groq for now as we will decommssion the provider for now.
    #     # see [WOR-1968: Disable `Groq` ?](https://linear.app/workflowai/issue/WOR-1968/disable-groq)
    # ),
    # Model.MIXTRAL_8X7B_32768: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_24,
    #         completion_cost_per_token=0.000_000_24,
    #         source="https://console.groq.com/settings/billing",
    #     ),
    #     # native tools calls are not implemented on Groq for now as we will decommssion the provider for now.
    #     # see [WOR-1968: Disable `Groq` ?](https://linear.app/workflowai/issue/WOR-1968/disable-groq)
    # ),
    Model.LLAMA_3_1_8B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_05,
            completion_cost_per_token=0.000_000_08,
            source="https://console.groq.com/settings/billing",
        ),
        # native tools calls are not implemented on Groq for now as we will decommssion the provider for now.
        # see [WOR-1968: Disable `Groq` ?](https://linear.app/workflowai/issue/WOR-1968/disable-groq)
    ),
    Model.LLAMA_3_3_70B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_59,
            completion_cost_per_token=0.000_000_79,
            source="https://console.groq.com/settings/billing",
        ),
        # native tools calls are not implemented on Groq for now as we will decommssion the provider for now.
        # see [WOR-1968: Disable `Groq` ?](https://linear.app/workflowai/issue/WOR-1968/disable-groq)
    ),
    #
    # Model.LLAMA_3_1_70B: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_59,
    #         completion_cost_per_token=0.000_000_79,
    #         source="https://console.groq.com/settings/billing",
    #     ),
    #     lifecycle_data=LifecycleData(
    #         sunset_date=datetime.date(year=2024, month=12, day=20),
    #         source="https://console.groq.com/docs/deprecations",
    #         post_sunset_replacement_model=Model.LLAMA_3_3_70B,
    #     ),
    #     # native tools calls are not implemented on Groq for now as we will decommssion the provider for now.
    #     # see [WOR-1968: Disable `Groq` ?](https://linear.app/workflowai/issue/WOR-1968/disable-groq)
    # ),
    # Model.LLAMA_3_2_3B_PREVIEW: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_06,
    #         completion_cost_per_token=0.000_000_06,
    #         source="https://console.groq.com/settings/billing",
    #     ),
    #     # native tools calls are not implemented on Groq for now as we will decommssion the provider for now.
    #     # see [WOR-1968: Disable `Groq` ?](https://linear.app/workflowai/issue/WOR-1968/disable-groq)
    # ),
    # Model.LLAMA_3_2_90B_VISION_PREVIEW: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.000_000_90,
    #         completion_cost_per_token=0.000_000_90,
    #         source="https://groq.com/pricing",
    #     ),
    #     # native tools calls are not implemented on Groq for now as we will decommssion the provider for now.
    #     # see [WOR-1968: Disable `Groq` ?](https://linear.app/workflowai/issue/WOR-1968/disable-groq)
    # ),
    # Model.LLAMA_4_MAVERICK_BASIC: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.20 * ONE_MILLION_TH,
    #         completion_cost_per_token=0.60 * ONE_MILLION_TH,
    #         source="https://groq.com/pricing/",
    #     ),
    # ),
    # Model.LLAMA_4_SCOUT_BASIC: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.11 / 1_000_000,
    #         completion_cost_per_token=0.34 / 1_000_000,
    #         source="https://groq.com/pricing/",
    #     ),
    # ),
    Model.LLAMA_4_MAVERICK_FAST: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.20 * ONE_MILLION_TH,
            completion_cost_per_token=0.60 * ONE_MILLION_TH,
            source="https://groq.com/pricing/",
        ),
    ),
    Model.LLAMA_4_SCOUT_FAST: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.11 / 1_000_000,
            completion_cost_per_token=0.34 / 1_000_000,
            source="https://groq.com/pricing/",
        ),
    ),
    Model.QWEN_QWQ_32B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.29 * ONE_MILLION_TH,
            completion_cost_per_token=0.39 * ONE_MILLION_TH,
            source="https://groq.com/pricing/",
        ),
    ),
}

MISTRAL_PROVIDER_DATA: ProviderDataByModel = {
    Model.PIXTRAL_12B_2409: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.15 / 1_000_000,
            completion_cost_per_token=0.15 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.MINISTRAL_3B_2410: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.04 / 1_000_000,
            completion_cost_per_token=0.04 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.MINISTRAL_8B_2410: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.1 / 1_000_000,
            completion_cost_per_token=0.1 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.MISTRAL_SMALL_2409: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.1 / 1_000_000,
            completion_cost_per_token=0.3 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.MISTRAL_SMALL_2501: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.1 / 1_000_000,
            completion_cost_per_token=0.3 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.MISTRAL_SMALL_2503: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.1 / 1_000_000,
            completion_cost_per_token=0.3 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.MISTRAL_LARGE_2_2407: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=2.0 / 1_000_000,
            completion_cost_per_token=6.0 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.CODESTRAL_MAMBA_2407: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.2 / 1_000_000,
            completion_cost_per_token=0.6 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.PIXTRAL_LARGE_2411: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=2.0 / 1_000_000,
            completion_cost_per_token=6.0 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.MISTRAL_LARGE_2411: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=2.0 / 1_000_000,
            completion_cost_per_token=6.0 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.MISTRAL_SABA_2502: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.2 / 1_000_000,
            completion_cost_per_token=0.6 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
    Model.CODESTRAL_2501: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.3 / 1_000_000,
            completion_cost_per_token=0.9 / 1_000_000,
            source="https://mistral.ai/products/la-plateforme#pricing",
        ),
    ),
}

ANTHROPIC_PROVIDER_DATA: ProviderDataByModel = {
    Model.CLAUDE_3_5_HAIKU_20241022: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.80 * ONE_MILLION_TH,
            completion_cost_per_token=4.00 * ONE_MILLION_TH,
            source="https://docs.anthropic.com/en/docs/about-claude/models/all-models#model-comparison-table",
        ),
    ),
    Model.CLAUDE_3_5_SONNET_20241022: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=3.0 * ONE_MILLION_TH,
            completion_cost_per_token=15 * ONE_MILLION_TH,
            source="https://docs.anthropic.com/en/docs/about-claude/models/all-models#model-comparison-table",
        ),
    ),
    Model.CLAUDE_3_5_SONNET_20240620: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=3.00 * ONE_MILLION_TH,
            completion_cost_per_token=15.00 * ONE_MILLION_TH,
            source="https://docs.anthropic.com/en/docs/about-claude/models/all-models#model-comparison-table",
        ),
    ),
    Model.CLAUDE_3_7_SONNET_20250219: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=3.00 * ONE_MILLION_TH,
            completion_cost_per_token=15.00 * ONE_MILLION_TH,
            source="https://docs.anthropic.com/en/docs/about-claude/models/all-models#model-comparison-table",
        ),
    ),
    Model.CLAUDE_3_OPUS_20240229: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=15 * ONE_MILLION_TH,
            completion_cost_per_token=0.000_015,
            source="https://docs.anthropic.com/en/docs/about-claude/models/all-models#model-comparison-table",
        ),
    ),
    Model.CLAUDE_3_HAIKU_20240307: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.25 * ONE_MILLION_TH,
            completion_cost_per_token=1.25 * ONE_MILLION_TH,
            source="https://docs.anthropic.com/en/docs/about-claude/models/all-models#model-comparison-table",
        ),
    ),
}

AZURE_PROVIDER_DATA: ProviderDataByModel = {
    # TODO: correct/update pricing for Azure OpenAI
    Model.GPT_4O_2024_11_20: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_002_5,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=0.000_010,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_4O_2024_08_06: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_002_5,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=0.000_010,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_PREVIEW_2024_09_12: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_015,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=0.000_060,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_MINI_2024_09_12: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=4.40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=4.40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O3_MINI_2025_01_31_MEDIUM_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=4.40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O3_MINI_2025_01_31_LOW_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.10 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=4.40 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.GPT_4O_MINI_2024_07_18: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.000_000_15,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=0.000_000_6,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_2024_12_17_LOW_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=15 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=60 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_2024_12_17_MEDIUM_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=15 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=60 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
    Model.O1_2024_12_17_HIGH_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=15 * ONE_MILLION_TH,
            prompt_cached_tokens_discount=0.5,
            completion_cost_per_token=60 * ONE_MILLION_TH,
            source="https://openai.com/api/pricing/",
        ),
    ),
}

GOOGLE_GEMINI_API_PROVIDER_DATA: ProviderDataByModel = {
    Model.GEMINI_2_0_FLASH_LITE_001: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.075 * ONE_MILLION_TH,
            completion_cost_per_token=0.30 * ONE_MILLION_TH,
            source="https://ai.google.dev/gemini-api/docs/pricing#2_0flash_lite",
        ),
    ),
    Model.GEMINI_2_0_FLASH_001: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.10 * ONE_MILLION_TH,
            completion_cost_per_token=0.40 * ONE_MILLION_TH,
            source="https://ai.google.dev/pricing#2_0flash-001",
        ),
        audio_price=AudioPricePerToken(
            audio_input_cost_per_token=0.70 * ONE_MILLION_TH,
        ),
    ),
    Model.GEMINI_2_5_FLASH_PREVIEW_0417: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.15 * ONE_MILLION_TH,
            completion_cost_per_token=0.60 * ONE_MILLION_TH,
            source="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash",
        ),
        audio_price=AudioPricePerToken(
            audio_input_cost_per_token=1.0 * ONE_MILLION_TH,
        ),
    ),
    Model.GEMINI_2_5_FLASH_THINKING_PREVIEW_0417: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.15 * ONE_MILLION_TH,
            completion_cost_per_token=3.50 * ONE_MILLION_TH,
            source="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash",
        ),
        audio_price=AudioPricePerToken(
            audio_input_cost_per_token=1.0 * ONE_MILLION_TH,
        ),
    ),
    Model.GEMINI_2_5_PRO_PREVIEW_0325: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.25 / 1_000_000,
            completion_cost_per_token=10 / 1_000_000,
            source="https://ai.google.dev/pricing",
            thresholded_prices=[
                ThresholdedTextPricePerToken(
                    threshold=200_000,
                    prompt_cost_per_token_over_threshold=2.5 / 1_000_000,
                    completion_cost_per_token_over_threshold=15 / 1_000_000,
                ),
            ],
        ),
    ),
    Model.GEMINI_1_5_FLASH_8B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.0375 / 1_000_000,
            completion_cost_per_token=0.15 / 1_000_000,
            thresholded_prices=[
                ThresholdedTextPricePerToken(
                    threshold=128000,
                    prompt_cost_per_token_over_threshold=0.075 / 1_000_000,
                    completion_cost_per_token_over_threshold=0.3 / 1_000_000,
                ),
            ],
            source="https://ai.google.dev/pricing#1_5flash-8B",
        ),
    ),
    Model.GEMINI_1_5_PRO_001: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.25 / 1_000_000,
            completion_cost_per_token=5 / 1_000_000,
            thresholded_prices=[
                # Price per token > 128k
                ThresholdedTextPricePerToken(
                    threshold=128_000,
                    prompt_cost_per_token_over_threshold=2.5 / 1_000_000,
                    completion_cost_per_token_over_threshold=10 / 1_000_000,
                ),
            ],
            source="https://ai.google.dev/pricing#1_5pro",
        ),
    ),
    Model.GEMINI_1_5_PRO_002: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.25 / 1_000_000,
            completion_cost_per_token=5 / 1_000_000,
            thresholded_prices=[
                # Price per token > 128k
                ThresholdedTextPricePerToken(
                    threshold=128_000,
                    prompt_cost_per_token_over_threshold=2.5 / 1_000_000,
                    completion_cost_per_token_over_threshold=10 / 1_000_000,
                ),
            ],
            source="https://ai.google.dev/pricing#1_5pro",
        ),
    ),
    Model.GEMINI_1_5_FLASH_001: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.075 / 1_000_000,
            completion_cost_per_token=0.30 / 1_000_000,
            thresholded_prices=[
                ThresholdedTextPricePerToken(
                    threshold=128000,
                    prompt_cost_per_token_over_threshold=0.15 / 1_000_000,
                    completion_cost_per_token_over_threshold=0.60 / 1_000_000,
                ),
            ],
            source="https://ai.google.dev/pricing#1_5flash",
        ),
    ),
    Model.GEMINI_1_5_FLASH_002: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.075 / 1_000_000,
            completion_cost_per_token=0.30 / 1_000_000,
            thresholded_prices=[
                ThresholdedTextPricePerToken(
                    threshold=128000,
                    prompt_cost_per_token_over_threshold=0.15 / 1_000_000,
                    completion_cost_per_token_over_threshold=0.60 / 1_000_000,
                ),
            ],
            source="https://ai.google.dev/pricing#1_5flash",
        ),
    ),
}

FIREWORKS_PROVIDER_DATA: ProviderDataByModel = {
    # Model.LLAMA3_70B_8192: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.90 / 1_000_000,
    #         completion_cost_per_token=0.90 / 1_000_000,
    #         source="https://fireworks.ai/pricing",
    #     ),
    #     # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    # ),
    # Model.LLAMA3_8B_8192: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.20 / 1_000_000,
    #         completion_cost_per_token=0.20 / 1_000_000,
    #         source="https://fireworks.ai/pricing",
    #     ),
    #     # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    # ),
    Model.LLAMA_3_1_8B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.20 / 1_000_000,
            completion_cost_per_token=0.20 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
        # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    ),
    Model.LLAMA_3_1_70B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.90 / 1_000_000,
            completion_cost_per_token=0.90 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
    ),
    Model.LLAMA_3_1_405B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=3.0 / 1_000_000,
            completion_cost_per_token=3.0 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
    ),
    Model.LLAMA_3_3_70B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.90 / 1_000_000,
            completion_cost_per_token=0.90 / 1_000_000,
            source="https://fireworks.ai/pricing",
            # LLAMA_3_3_70B is not a MoE model, so in 16.1B+ category
        ),
        # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    ),
    # Model.LLAMA_3_2_3B: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.10 / 1_000_000,
    #         completion_cost_per_token=0.10 / 1_000_000,
    #         source="https://fireworks.ai/pricing",
    #     ),
    #     # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    # ),
    # Model.LLAMA_3_2_3B_PREVIEW: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.10 / 1_000_000,
    #         completion_cost_per_token=0.10 / 1_000_000,
    #         source="https://fireworks.ai/pricing",
    #     ),
    #     # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    # ),
    # Model.LLAMA_3_2_11B_VISION: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.20 / 1_000_000,
    #         completion_cost_per_token=0.20 / 1_000_000,
    #         source="https://fireworks.ai/pricing",
    #     ),
    #     # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    # ),
    # Model.LLAMA_3_2_90B_VISION_PREVIEW: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.90 / 1_000_000,
    #         completion_cost_per_token=0.90 / 1_000_000,
    #         source="https://fireworks.ai/pricing",
    #         # LLAMA_3_2_90B_VISION_PREVIEW is not a MoE model, so in 16.1B+ category
    #     ),
    #     # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    # ),
    Model.QWEN_QWQ_32B: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.90 / 1_000_000,
            completion_cost_per_token=0.90 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
        # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    ),
    # Model.MIXTRAL_8X7B_32768: ModelProviderData(
    #     text_price=TextPricePerToken(
    #         prompt_cost_per_token=0.50 / 1_000_000,
    #         completion_cost_per_token=0.50 / 1_000_000,
    #         source="https://fireworks.ai/pricing",
    #     ),
    #     # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    # ),
    Model.DEEPSEEK_V3_2412: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.90 / 1_000_000,
            completion_cost_per_token=0.90 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
        # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    ),
    Model.DEEPSEEK_R1_2501: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=8.0 / 1_000_000,
            completion_cost_per_token=8.0 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
        # see: https://docs.fireworks.ai/guides/function-calling#supported-models
    ),
    Model.DEEPSEEK_R1_2501_BASIC: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.55 / 1_000_000,
            completion_cost_per_token=2.19 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
    ),
    Model.DEEPSEEK_V3_0324: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=1.20 / 1_000_000,
            completion_cost_per_token=1.20 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
    ),
    Model.LLAMA_4_MAVERICK_BASIC: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.22 / 1_000_000,
            completion_cost_per_token=0.88 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
    ),
    Model.LLAMA_4_SCOUT_BASIC: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.15 / 1_000_000,
            completion_cost_per_token=0.60 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
    ),
    # Fall back for the fast groq version
    Model.LLAMA_4_MAVERICK_FAST: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.22 / 1_000_000,
            completion_cost_per_token=0.88 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
    ),
    Model.LLAMA_4_SCOUT_FAST: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.15 / 1_000_000,
            completion_cost_per_token=0.60 / 1_000_000,
            source="https://fireworks.ai/pricing",
        ),
    ),
}

XAI_PROVIDER_DATA: ProviderDataByModel = {
    Model.GROK_3_BETA: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=3 / 1_000_000,
            completion_cost_per_token=15 / 1_000_000,
            source="https://docs.x.ai/docs/models#models-and-pricing",
        ),
    ),
    Model.GROK_3_FAST_BETA: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=5 / 1_000_000,
            completion_cost_per_token=25 / 1_000_000,
            source="https://docs.x.ai/docs/models#models-and-pricing",
        ),
    ),
    Model.GROK_3_MINI_BETA_HIGH_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.3 / 1_000_000,
            completion_cost_per_token=0.5 / 1_000_000,
            source="https://docs.x.ai/docs/models#models-and-pricing",
        ),
    ),
    Model.GROK_3_MINI_BETA_LOW_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.3 / 1_000_000,
            completion_cost_per_token=0.5 / 1_000_000,
            source="https://docs.x.ai/docs/models#models-and-pricing",
        ),
    ),
    Model.GROK_3_MINI_FAST_BETA_HIGH_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.6 / 1_000_000,
            completion_cost_per_token=4 / 1_000_000,
            source="https://docs.x.ai/docs/models#models-and-pricing",
        ),
    ),
    Model.GROK_3_MINI_FAST_BETA_LOW_REASONING_EFFORT: ModelProviderData(
        text_price=TextPricePerToken(
            prompt_cost_per_token=0.6 / 1_000_000,
            completion_cost_per_token=4 / 1_000_000,
            source="https://docs.x.ai/docs/models#models-and-pricing",
        ),
    ),
}

type ProviderModelDataMapping = dict[Provider, ProviderDataByModel]

# Pricing and lifecycle data for each model / provider couple
MODEL_PROVIDER_DATAS: ProviderModelDataMapping = {
    # ------------------------------------------------------------------------------------------------
    # Google Vertex AI
    Provider.GOOGLE: GOOGLE_PROVIDER_DATA,
    # ------------------------------------------------------------------------------------------------
    # OpenAI
    Provider.OPEN_AI: OPENAI_PROVIDER_DATA,
    Provider.OPEN_AI_IMAGE: OPENAI_IMAGE_PROVIDER_DATA,
    # ------------------------------------------------------------------------------------------------
    # Amazon Bedrock
    Provider.AMAZON_BEDROCK: AMAZON_BEDROCK_PROVIDER_DATA,
    # ------------------------------------------------------------------------------------------------
    # Groq
    Provider.GROQ: GROQ_PROVIDER_DATA,
    # ------------------------------------------------------------------------------------------------
    # MistralAI
    Provider.MISTRAL_AI: MISTRAL_PROVIDER_DATA,
    # ------------------------------------------------------------------------------------------------
    # Anthropic
    Provider.ANTHROPIC: ANTHROPIC_PROVIDER_DATA,
    # ------------------------------------------------------------------------------------------------
    # Azure
    Provider.AZURE_OPEN_AI: AZURE_PROVIDER_DATA,
    # ------------------------------------------------------------------------------------------------
    # Google Gemini
    Provider.GOOGLE_GEMINI: GOOGLE_GEMINI_API_PROVIDER_DATA,
    # ------------------------------------------------------------------------------------------------
    # Fireworks
    Provider.FIREWORKS: FIREWORKS_PROVIDER_DATA,
    # ------------------------------------------------------------------------------------------------
    # XAI
    Provider.X_AI: XAI_PROVIDER_DATA,
}
