import json
import logging
from typing import Literal, cast

from pydantic import BaseModel

from core.domain.errors import (
    MissingEnvVariablesError,
    MissingModelError,
)
from core.domain.models import Model, Provider
from core.providers.base.utils import get_provider_config_env

logger = logging.getLogger(__name__)


# A map Model -> bedrock resource id
# By default we use the cross inference resources
def _default_resource_ids():
    return {
        Model.CLAUDE_3_7_SONNET_20250219: "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        Model.CLAUDE_3_5_SONNET_20241022: "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        Model.CLAUDE_3_5_SONNET_20240620: "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
        Model.CLAUDE_3_OPUS_20240229: "us.anthropic.claude-3-opus-20240229-v1:0",
        Model.CLAUDE_3_SONNET_20240229: "us.anthropic.claude-3-sonnet-20240229-v1:0",
        Model.CLAUDE_3_5_HAIKU_20241022: "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        Model.CLAUDE_3_HAIKU_20240307: "us.anthropic.claude-3-haiku-20240307-v1:0",
        Model.LLAMA_3_3_70B: "us.meta.llama3-3-70b-instruct-v1:0",
        Model.LLAMA_3_2_90B: "us.meta.llama3-2-90b-instruct-v1:0",
        Model.LLAMA_3_2_11B: "us.meta.llama3-2-11b-instruct-v1:0",
        Model.LLAMA_3_2_3B: "us.meta.llama3-2-3b-instruct-v1:0",
        Model.LLAMA_3_2_1B: "us.meta.llama3-2-1b-instruct-v1:0",
        Model.LLAMA_3_1_405B: "meta.llama3-1-405b-instruct-v1:0",
        Model.LLAMA_3_1_70B: "us.meta.llama3-1-70b-instruct-v1:0",
        Model.LLAMA_3_1_8B: "us.meta.llama3-1-8b-instruct-v1:0",
        Model.MISTRAL_LARGE_2_2407: "mistral.mistral-large-2407-v1:0",
    }


logger = logging.getLogger(__name__)


class AmazonBedrockConfig(BaseModel):
    provider: Literal[Provider.AMAZON_BEDROCK] = Provider.AMAZON_BEDROCK

    aws_bedrock_access_key: str
    aws_bedrock_secret_key: str
    resource_id_x_model_map: dict[Model, str]
    available_model_x_region_map: dict[Model, str]
    default_region: str = "us-west-2"

    def __str__(self):
        models = [model.value for model in self.available_model_x_region_map.keys()]
        regions = {region for region in self.available_model_x_region_map.values()}
        return (
            f"AmazonBedrockConfig(access_key={self.aws_bedrock_access_key[:4]}****, "
            f"secret_key={self.aws_bedrock_secret_key[:4]}****, "
            f"available_models={models}, available_regions={regions})"
        )

    @classmethod
    def from_env(cls, index: int):
        def _map_model_map(key: str, default: dict[Model, str]) -> dict[Model, str]:
            try:
                value = get_provider_config_env(key, index)
            except MissingEnvVariablesError:
                return default
            try:
                d = json.loads(value)
            except json.JSONDecodeError:
                logger.exception("Invalid model mapping. Must be a json object of model names to deployment names")
                return default
            if not isinstance(d, dict):
                logger.error(
                    "Invalid model mapping. Must be a json object of model names to deployment names",
                    extra={"raw_models": value},
                )
                return default
            out: dict[Model, str] = {}
            for k, v in cast(dict[str, str], d).items():
                try:
                    out[Model(k)] = v
                except ValueError:
                    logger.warning(
                        "Invalid model name in model mapping, Skipping",
                        extra={"model": k},
                    )
            return out

        return cls(
            aws_bedrock_access_key=get_provider_config_env("AWS_BEDROCK_ACCESS_KEY", index),
            aws_bedrock_secret_key=get_provider_config_env("AWS_BEDROCK_SECRET_KEY", index),
            available_model_x_region_map=_map_model_map("AWS_BEDROCK_MODEL_REGION_MAP", {}),
            resource_id_x_model_map=_map_model_map("AWS_BEDROCK_RESOURCE_ID_MODEL_MAP", _default_resource_ids()),
            default_region=get_provider_config_env("AWS_BEDROCK_DEFAULT_REGION", index, "us-west-2"),
        )

    def region_for_model(self, model: Model):
        return self.available_model_x_region_map.get(model, self.default_region)

    def id_for_model(self, model: Model):
        try:
            return self.resource_id_x_model_map[model]
        except KeyError:
            raise MissingModelError(
                f"Model {model} is not supported by Amazon Bedrock",
                extras={"model": model},
            )
