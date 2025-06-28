import asyncio
import os
from typing import Any, List, Optional, TypedDict

import httpx
from dotenv import load_dotenv

from core.domain.models.model_data import ModelData
from core.domain.models.model_data_mapping import MODEL_DATAS
from core.domain.models.model_provider_data_mapping import MISTRAL_PROVIDER_DATA
from core.domain.models.models import Model
from core.providers.mistral.mistral_provider import MODEL_MAP


class ModelCapabilities(TypedDict):
    completion_chat: bool
    completion_fim: bool
    function_calling: bool
    fine_tuning: bool
    vision: bool
    classification: bool


class MistralModel(TypedDict):
    id: str
    object: str
    created: int
    owned_by: str
    capabilities: ModelCapabilities
    name: str
    description: str
    max_context_length: int
    aliases: List[str]
    deprecation: Optional[Any]
    default_model_temperature: float
    type: str


def _reversed_map_model(value: str):
    for k, v in MODEL_MAP.items():
        if v == value:
            return k
    return value


async def _list_models() -> dict[str, MistralModel]:
    async with httpx.AsyncClient() as client:
        url = "https://api.mistral.ai/v1/models"
        response = await client.get(url, headers={"Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}"})
        response.raise_for_status()
        return {
            Model(_reversed_map_model(model["id"])): model
            for model in response.json()["data"]
            if _reversed_map_model(model["id"]) in Model
        }


async def _main():
    mistral_values = await _list_models()

    for model, data in MODEL_DATAS.items():
        if not isinstance(data, ModelData):
            continue

        if model not in mistral_values and model not in MISTRAL_PROVIDER_DATA:
            # Model is not supported by Mistral
            continue

        if model not in mistral_values:
            # Model is not supported by Mistral but we think it is
            raise ValueError(f"Model {model} is not supported by Mistral but we think it is")

        if model not in MISTRAL_PROVIDER_DATA:
            # Model is supported by Mistral but we don't have data for it
            raise ValueError(f"Model {model} is supported by Mistral but we don't have data for it")

        values_from_mistral = mistral_values[model]

        if values_from_mistral["capabilities"]["function_calling"] != data.supports_tool_calling:
            raise ValueError(f"Model {model} has a different function calling support")

        if values_from_mistral["capabilities"]["vision"] != data.supports_input_image:
            raise ValueError(f"Model {model} has a different vision support")

        if values_from_mistral["max_context_length"] != data.max_tokens_data.max_tokens:
            raise ValueError(
                f"Model {model} has a different max context length: {values_from_mistral['max_context_length']} != {data.max_tokens_data.max_tokens}",
            )


if __name__ == "__main__":
    load_dotenv(override=True)
    asyncio.run(_main())
