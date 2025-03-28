import base64
import json
import random
from typing import Any, Literal

from pydantic import BaseModel, model_validator
from typing_extensions import override

from core.domain.errors import (
    InvalidProviderConfig,
    UnknownProviderError,
)
from core.domain.llm_usage import LLMUsage
from core.domain.models import Model, Provider
from core.providers.base.utils import get_provider_config_env
from core.providers.google import google_provider_auth
from core.providers.google.google_provider_base import GoogleProviderBase
from core.providers.google.google_provider_domain import (
    BLOCK_THRESHOLD,
    GOOGLE_CHARS_PER_TOKEN,
    PER_TOKEN_MODELS,
    message_or_system_message,
)

# https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations#available-regions
_MIXED_REGION_MODELS = {
    # Model.GEMINI_2_0_FLASH_EXP,
    Model.GEMINI_1_5_FLASH_002,
    Model.GEMINI_1_5_FLASH_001,
    Model.GEMINI_1_5_PRO_001,
    Model.GEMINI_1_5_PRO_002,
    Model.GEMINI_2_0_FLASH_001,
    Model.GEMINI_2_0_FLASH_LITE_001,
}

_VERTEX_API_REGION_METADATA_KEY = "workflowai.vertex_api_region"
_VERTEX_API_EXCLUDED_REGIONS_METADATA_KEY = "workflowai.vertex_api_excluded_regions"


class GoogleProviderConfig(BaseModel):
    provider: Literal[Provider.GOOGLE] = Provider.GOOGLE

    vertex_project: str
    vertex_credentials: str
    vertex_location: list[str]

    default_block_threshold: BLOCK_THRESHOLD | None = None

    def __str__(self):
        return (
            f"GoogleProviderConfig(project={self.vertex_project}, location={self.vertex_location[0]}, credentials=****)"
        )

    @model_validator(mode="before")
    @classmethod
    def sanitize_vertex_location(cls, data: Any) -> Any:
        if isinstance(data, dict) and "vertex_location" in data and isinstance(data["vertex_location"], str):
            data["vertex_location"] = [data["vertex_location"]]
        return data  # pyright: ignore [reportUnknownVariableType]


class GoogleProvider(GoogleProviderBase[GoogleProviderConfig]):
    def _get_random_region(self, choices: list[str]) -> str:
        return random.choice(choices)

    def all_available_regions(self):
        return set(self.config.vertex_location)

    def get_vertex_location(self) -> str:
        used_regions = self._get_metadata(_VERTEX_API_EXCLUDED_REGIONS_METADATA_KEY)
        excluded_regions: set[str] = set(used_regions.split(",")) if used_regions else set()
        region = self._get_metadata(_VERTEX_API_REGION_METADATA_KEY)
        if region and region not in excluded_regions:
            excluded_regions.add(region)
            self._add_metadata(_VERTEX_API_EXCLUDED_REGIONS_METADATA_KEY, ",".join(excluded_regions))
        choices = list(self.all_available_regions() - set(excluded_regions))

        if len(choices) == 0:
            raise UnknownProviderError("No available regions left to retry.", extra={"choices": choices})
        return self._get_random_region(choices)

    @override
    async def _request_headers(self, request: dict[str, Any], url: str, model: Model) -> dict[str, str]:
        token = await google_provider_auth.get_token(self.config.vertex_credentials)
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    @override
    def _request_url(self, model: Model, stream: bool) -> str:
        location = self.config.vertex_location[0] if model not in _MIXED_REGION_MODELS else self.get_vertex_location()
        self._add_metadata(_VERTEX_API_REGION_METADATA_KEY, location)

        MODEL_STR_OVERRIDES = {
            Model.LLAMA_3_2_90B: "llama-3.2-90b-vision-instruct-maas",
            Model.LLAMA_3_1_405B: "llama3-405b-instruct-maas",
        }

        PUBLISHER_OVERRIDES = {
            Model.LLAMA_3_2_90B: "meta",
            Model.LLAMA_3_1_405B: "meta",
        }

        if stream:
            suffix = "streamGenerateContent?alt=sse"
        else:
            suffix = "generateContent"

        model_str = MODEL_STR_OVERRIDES.get(model, model.value)

        publisher_str = PUBLISHER_OVERRIDES.get(model, "google")

        return f"https://{location}-aiplatform.googleapis.com/v1/projects/{self.config.vertex_project}/locations/{location}/publishers/{publisher_str}/models/{model_str}:{suffix}"

    @override
    @classmethod
    def required_env_vars(cls) -> list[str]:
        return ["GOOGLE_VERTEX_AI_PROJECT_ID", "GOOGLE_VERTEX_AI_LOCATION", "GOOGLE_VERTEX_AI_CREDENTIALS"]

    @override
    @classmethod
    def name(cls) -> Provider:
        return Provider.GOOGLE

    @override
    @classmethod
    def _default_config(cls, index: int) -> GoogleProviderConfig:
        return GoogleProviderConfig(
            vertex_project=get_provider_config_env("GOOGLE_VERTEX_AI_PROJECT_ID", index),
            vertex_credentials=get_provider_config_env("GOOGLE_VERTEX_AI_CREDENTIALS", index),
            vertex_location=get_provider_config_env("GOOGLE_VERTEX_AI_LOCATION", index).split(","),
            default_block_threshold="BLOCK_NONE",
        )

    @override
    def default_model(self) -> Model:
        return Model.GEMINI_1_5_FLASH_002

    @classmethod
    def sanitize_config(cls, config: GoogleProviderConfig) -> GoogleProviderConfig:
        credentials = config.vertex_credentials
        if not credentials.startswith("{"):
            # Credentials are not a JSON string. We assume they are base64 encoded
            # the frontend sends b64 encoded credentials
            if credentials.startswith("data:application/json;base64,"):
                credentials = credentials[29:]
            try:
                credentials = base64.b64decode(credentials).decode("utf-8")
            except ValueError:
                raise InvalidProviderConfig("Invalid base64 encoded credentials")

        try:
            raw_json = json.loads(credentials)
        except json.JSONDecodeError:
            raise InvalidProviderConfig("Vertex credentials are not a json payload")

        if not isinstance(raw_json, dict):
            raise InvalidProviderConfig("Vertex credentials are not a json object")

        # Check if the project matches the project in the config
        if raw_json.get("project_id") != config.vertex_project:  # pyright: ignore [reportUnknownMemberType]
            raise InvalidProviderConfig("Vertex credentials project_id does not match the project in the config")

        if "private_key" not in raw_json:
            raise InvalidProviderConfig("Vertex credentials are missing a private_key")

        return GoogleProviderConfig(
            vertex_project=config.vertex_project,
            vertex_credentials=credentials,
            vertex_location=config.vertex_location,
        )

    def _compute_prompt_token_count_per_token(self, messages: list[dict[str, Any]], model: Model) -> float:
        token_count = 0

        for message in messages:
            domain_message = message_or_system_message(message)

            message_token_count = domain_message.text_token_count(model)
            token_count += message_token_count

        return token_count

    @override
    def _compute_prompt_token_count(
        self,
        messages: list[dict[str, Any]],
        model: Model,
    ) -> float:
        if model in PER_TOKEN_MODELS:
            return self._compute_prompt_token_count_per_token(messages, model)

        char_count = 0

        for message in messages:
            domain_message = message_or_system_message(message)
            message_char_count = domain_message.text_char_count()
            char_count += message_char_count

        return char_count / GOOGLE_CHARS_PER_TOKEN

    @override
    def _compute_prompt_image_count(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        image_count = 0

        for message in messages:
            domain_message = message_or_system_message(message)

            message_char_count = domain_message.image_count()
            image_count += message_char_count

        return image_count

    @override
    async def feed_prompt_token_count(self, llm_usage: LLMUsage, messages: list[dict[str, Any]], model: Model) -> None:
        if model in PER_TOKEN_MODELS:
            # For per token models, we just return the number of tokens
            await super().feed_prompt_token_count(llm_usage, messages, model)
            return
        # For other models, we have to compute the number of characters

        llm_usage.prompt_token_count = self._compute_prompt_token_count(messages, model)
        # the prompt token count should include the total number of tokens
        if llm_usage.prompt_audio_token_count is not None:
            llm_usage.prompt_token_count += llm_usage.prompt_audio_token_count

    @override
    def feed_completion_token_count(self, llm_usage: LLMUsage, response: str | None, model: Model) -> None:
        if model in PER_TOKEN_MODELS:
            # For per token models, we just return the number of tokens
            super().feed_completion_token_count(llm_usage, response, model)
            return

        llm_usage.completion_token_count = len(response.replace(" ", "")) / GOOGLE_CHARS_PER_TOKEN if response else 0
