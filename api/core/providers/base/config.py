from typing import Annotated, Union

from pydantic import Field

from core.providers.amazon_bedrock.amazon_bedrock_provider import AmazonBedrockConfig
from core.providers.anthropic.anthropic_provider import AnthropicConfig
from core.providers.cerebras.cerebras_provider import CerebrasConfig
from core.providers.google.gemini.gemini_api_provider import GoogleGeminiAPIProviderConfig
from core.providers.google.google_provider import GoogleProviderConfig
from core.providers.groq.groq_provider import GroqConfig
from core.providers.mistral.mistral_provider import MistralAIConfig
from core.providers.openai.azure_open_ai_provider.azure_openai_provider import AzureOpenAIConfig
from core.providers.openai.openai_provider import OpenAIConfig

ProviderConfig = Annotated[
    Union[
        GroqConfig,
        AmazonBedrockConfig,
        OpenAIConfig,
        GoogleProviderConfig,
        AnthropicConfig,
        MistralAIConfig,
        GoogleGeminiAPIProviderConfig,
        AzureOpenAIConfig,
        CerebrasConfig,
    ],
    Field(discriminator="provider"),
]
