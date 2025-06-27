from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory

from api.services.models import ModelsService
from core.domain.models import Model, Provider
from core.domain.models.model_provider_data import ModelProviderData, TextPricePerToken
from core.storage.task_run_storage import TokenCounts


@pytest.fixture
def models_service(mock_storage: Mock):
    ModelsService._token_counts_cache._cache.cache.clear()  # pyright: ignore[reportPrivateUsage]
    return ModelsService(storage=mock_storage)


class TestComputeCostEstimate:
    @patch(
        "core.domain.models.model_provider_data_mapping.MODEL_PROVIDER_DATAS",
        {
            Provider.OPEN_AI: {
                "gpt-4o-2024-08-06": ModelProviderData(
                    text_price=TextPricePerToken(
                        prompt_cost_per_token=0.0000025,
                        completion_cost_per_token=0.00001,
                        source="openai",
                    ),
                ),
            },
        },
    )
    async def test_get_cost_estimates(self, models_service: ModelsService, mock_storage: Mock):
        mock_storage.task_runs.aggregate_token_counts = AsyncMock(
            return_value=TokenCounts(
                average_prompt_tokens=100,
                average_completion_tokens=200,
                count=1,
            ),
        )

        models_providers = {(Model.GPT_4O_2024_08_06, Provider.OPEN_AI)}  # noqa: F821

        cost_estimates = await models_service.get_cost_estimates(
            task_id=("task_id", 1),
            task_schema_id=1,
            models_providers=models_providers,
        )
        assert mock_storage.task_runs.aggregate_token_counts.call_count == 2
        expected_cost = (100 * 0.0000025) + (200 * 0.00001)
        assert cost_estimates[(Model.GPT_4O_2024_08_06, Provider.OPEN_AI)] == expected_cost

    async def test_get_cost_estimates_empty(self, models_service: ModelsService, mock_storage: Mock):
        mock_storage.task_runs.aggregate_token_counts = AsyncMock(
            return_value=TokenCounts(
                average_prompt_tokens=0,
                average_completion_tokens=0,
                count=0,
            ),
        )

        models_providers = {(Model.GPT_4O_2024_08_06, Provider.OPEN_AI)}  # noqa: F821

        cost_estimates = await models_service.get_cost_estimates(
            task_id=("task_id", 1),
            task_schema_id=1,
            models_providers=models_providers,
        )
        assert mock_storage.task_runs.aggregate_token_counts.call_count == 2
        assert len(cost_estimates) == 1
        assert cost_estimates[(Model.GPT_4O_2024_08_06, Provider.OPEN_AI)] is None

    async def test_get_cost_estimates_with_exception(self, models_service: ModelsService, mock_storage: Mock):
        models_providers = {
            (Model.GPT_4O_2024_11_20, Provider.OPEN_AI),
        }

        # Act
        mock_storage.task_runs.aggregate_token_counts.side_effect = Exception("Test exception")

        cost_estimates = await models_service.get_cost_estimates(("task_id", 1), 1, models_providers)

        # Assert
        assert cost_estimates == {
            (Model.GPT_4O_2024_11_20, Provider.OPEN_AI): None,
        }

    async def test_get_cost_estimates_model_not_supported(
        self,
        models_service: ModelsService,
        mock_storage: Mock,
    ):
        # Have a model provider pair that does not work
        models_providers = {
            (Model.GPT_4O_2024_11_20, Provider.GOOGLE),
        }

        mock_storage.task_runs.aggregate_token_counts.return_value = TokenCounts(
            average_prompt_tokens=100,
            average_completion_tokens=200,
            count=1,
        )

        cost_estimates = await models_service.get_cost_estimates(("task_id", 1), 1, models_providers)
        assert cost_estimates == {}


class TestAggregateTokenCounts:
    async def test_aggregate_token_counts_no_cache_zero_count(
        self,
        models_service: ModelsService,
        mock_storage: Mock,
        frozen_time: FrozenDateTimeFactory,
    ):
        """Test that when count is 0, the cache TTL is 0 (immediate expiry)"""
        token_counts = TokenCounts(
            average_prompt_tokens=0,
            average_completion_tokens=0,
            count=0,
        )
        mock_storage.task_runs.aggregate_token_counts.return_value = token_counts

        result1 = await models_service._aggregate_token_counts(("task_id", 1), 1)  # pyright: ignore[reportPrivateUsage]
        assert result1 == token_counts
        mock_storage.task_runs.aggregate_token_counts.assert_called_once()

        # Even with no time advancement, should make a new call due to count=0
        result2 = await models_service._aggregate_token_counts(("task_id", 1), 1)  # pyright: ignore[reportPrivateUsage]
        assert result2 == token_counts
        assert mock_storage.task_runs.aggregate_token_counts.call_count == 2

    async def test_aggregate_token_counts_low_count_cache(
        self,
        models_service: ModelsService,
        mock_storage: Mock,
        frozen_time: FrozenDateTimeFactory,
    ):
        """Test that when count < 10, the cache TTL is 10 seconds"""
        token_counts = TokenCounts(
            average_prompt_tokens=100,
            average_completion_tokens=200,
            count=5,
        )
        mock_storage.task_runs.aggregate_token_counts.return_value = token_counts

        result1 = await models_service._aggregate_token_counts(("task_id", 1), 1)  # pyright: ignore[reportPrivateUsage]
        assert result1 == token_counts
        mock_storage.task_runs.aggregate_token_counts.assert_called_once()

        # Advance 15 seconds, should still be cached
        frozen_time.tick(delta=timedelta(seconds=15))
        result2 = await models_service._aggregate_token_counts(("task_id", 1), 1)  # pyright: ignore[reportPrivateUsage]
        assert result2 == token_counts
        assert mock_storage.task_runs.aggregate_token_counts.call_count == 1

        # Advance 20 more seconds (total 35s), cache should be expired
        frozen_time.tick(delta=timedelta(seconds=45))
        result3 = await models_service._aggregate_token_counts(("task_id", 1), 1)  # pyright: ignore[reportPrivateUsage]
        assert result3 == token_counts
        assert mock_storage.task_runs.aggregate_token_counts.call_count == 2

    async def test_aggregate_token_counts_high_count_cache(
        self,
        models_service: ModelsService,
        mock_storage: Mock,
        frozen_time: FrozenDateTimeFactory,
    ):
        """Test that when count >= 10, the cache TTL is 1 hour"""
        token_counts = TokenCounts(
            average_prompt_tokens=100,
            average_completion_tokens=200,
            count=10,
        )
        mock_storage.task_runs.aggregate_token_counts.return_value = token_counts

        result1 = await models_service._aggregate_token_counts(("task_id", 1), 1)  # pyright: ignore[reportPrivateUsage]
        assert result1 == token_counts
        mock_storage.task_runs.aggregate_token_counts.assert_called_once()

        # Advance 59 minutes, should still be cached
        frozen_time.tick(delta=timedelta(minutes=59))
        result2 = await models_service._aggregate_token_counts(("task_id", 1), 1)  # pyright: ignore[reportPrivateUsage]
        assert result2 == token_counts
        assert mock_storage.task_runs.aggregate_token_counts.call_count == 1

        # Advance 2 more minutes (total 61m), cache should be expired
        frozen_time.tick(delta=timedelta(minutes=2))
        result3 = await models_service._aggregate_token_counts(("task_id", 1), 1)  # pyright: ignore[reportPrivateUsage]
        assert result3 == token_counts
        assert mock_storage.task_runs.aggregate_token_counts.call_count == 2
