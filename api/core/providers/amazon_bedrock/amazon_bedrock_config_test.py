import logging
import os
from unittest.mock import patch

from core.domain.models import Model, Provider
from core.domain.models.model_provider_datas_mapping import AMAZON_BEDROCK_PROVIDER_DATA
from core.providers.amazon_bedrock.amazon_bedrock_config import (
    AmazonBedrockConfig,
    _default_resource_ids,  # pyright: ignore [reportPrivateUsage]
)


def test_default_resource_ids_are_exhaustive():
    assert set(_default_resource_ids()) == set(AMAZON_BEDROCK_PROVIDER_DATA.keys())


class TestFromEnv:
    @patch.dict(
        os.environ,
        {"AWS_BEDROCK_ACCESS_KEY": "aws_bedrock_access_key", "AWS_BEDROCK_SECRET_KEY": "aws_bedrock_secret_key"},
        clear=True,
    )
    def test_no_maps(self):
        config = AmazonBedrockConfig.from_env(0)
        assert config.provider == Provider.AMAZON_BEDROCK
        assert config.aws_bedrock_access_key == "aws_bedrock_access_key"
        assert config.aws_bedrock_secret_key == "aws_bedrock_secret_key"
        assert config.resource_id_x_model_map == _default_resource_ids(), "resource_id_x_model_map should be set"
        assert config.available_model_x_region_map == {}, "available_model_x_region_map should be empty"

    @patch.dict(
        os.environ,
        {
            "AWS_BEDROCK_ACCESS_KEY": "aws_bedrock_access_key",
            "AWS_BEDROCK_SECRET_KEY": "aws_bedrock_secret_key",
            "AWS_BEDROCK_RESOURCE_ID_MODEL_MAP": '{"claude-3-5-haiku-20241022": "resource1"}',
        },
        clear=True,
    )
    def test_resource_id_x_model_map(self):
        config = AmazonBedrockConfig.from_env(0)
        assert config.resource_id_x_model_map == {Model.CLAUDE_3_5_HAIKU_20241022: "resource1"}

    @patch.dict(
        os.environ,
        {
            "AWS_BEDROCK_ACCESS_KEY": "aws_bedrock_access_key",
            "AWS_BEDROCK_SECRET_KEY": "aws_bedrock_secret_key",
            "AWS_BEDROCK_RESOURCE_ID_MODEL_MAP": '["bla"]',
        },
    )
    def test_resource_id_x_model_map_invalid(self):
        config = AmazonBedrockConfig.from_env(0)
        assert config.resource_id_x_model_map == _default_resource_ids()


def test_amazon_provider_works_with_unknown_model_in_region_map():
    # Check that logger was called with warning
    with patch.object(logging.Logger, "warning") as mock_warning:
        with patch.dict(
            "os.environ",
            {
                "AWS_BEDROCK_ACCESS_KEY": "test_access_key",
                "AWS_BEDROCK_SECRET_KEY": "test_secret_key",
                "AWS_BEDROCK_MODEL_REGION_MAP": '{"bogus-model": "us-west-2", "claude-3-5-sonnet-20240620": "us-west-2", "claude-3-opus-20240229": "us-west-2"}',
            },
            clear=True,
        ):
            config = AmazonBedrockConfig.from_env(0)
            assert config.available_model_x_region_map == {
                Model.CLAUDE_3_5_SONNET_20240620: "us-west-2",
                Model.CLAUDE_3_OPUS_20240229: "us-west-2",
            }
            mock_warning.assert_called_once_with(
                "Invalid model name in model mapping, Skipping",
                extra={"model": "bogus-model"},
            )
