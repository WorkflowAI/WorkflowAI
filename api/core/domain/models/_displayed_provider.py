from enum import StrEnum


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
    X_AI = "xAI"
    CEREBRAS = "Cerebras"
