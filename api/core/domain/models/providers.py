from enum import StrEnum


# Providers are ordered by priority, meaning
# that the higher the provider is in the enum the more
# changes it will get to be selected
class Provider(StrEnum):
    GROQ = "groq"
    FIREWORKS = "fireworks"
    # Anthropic is the default provider for Anthropic models
    # Bedrock is ok but it throttles instead of returning 429s
    # Which is very inconvenient
    ANTHROPIC = "anthropic"
    AMAZON_BEDROCK = "amazon_bedrock"
    # OpenAI is the default provider for OpenAI models
    # We tried Azure for a while but it is no way reliable
    OPEN_AI = "openai"
    AZURE_OPEN_AI = "azure_openai"
    GOOGLE = "google"
    MISTRAL_AI = "mistral_ai"
    GOOGLE_GEMINI = "google_gemini"
    GOOGLE_IMAGEN = "google_vertex_imagen"
    X_AI = "xai"
    CEREBRAS = "cerebras"
    OPEN_AI_IMAGE = "openai_image"
