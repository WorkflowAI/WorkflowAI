"""Tests for model sorting utilities."""

from typing import Literal

import pytest

from api.routers.mcp._mcp_models import ConciseLatestModelResponse, ConciseModelResponse, ConciseModelSupports
from api.routers.mcp._utils.model_sorting import sort_models


def create_test_model(
    model_id: str,
    quality_index: int = 50,
    speed_index: int = 500,
    cost_per_input_token_usd: float = 0.001,
    cost_per_output_token_usd: float = 0.002,
    release_date: str = "2024-01-01",
) -> ConciseModelResponse:
    """Helper function to create test models."""
    return ConciseModelResponse(
        id=model_id,
        display_name=f"Test Model {model_id}",
        supports=ConciseModelSupports(
            input_image=False,
            input_pdf=False,
            input_audio=False,
            audio_only=False,
            tool_calling=True,
            reasoning=False,
        ),
        quality_index=quality_index,
        speed_index=speed_index,
        cost_per_input_token_usd=cost_per_input_token_usd,
        cost_per_output_token_usd=cost_per_output_token_usd,
        release_date=release_date,
        reasoning=None,
    )


def create_test_latest_model(
    model_id: str,
    currently_points_to: str = "some-model",
) -> ConciseLatestModelResponse:
    """Helper function to create test latest models."""
    return ConciseLatestModelResponse(
        id=model_id,
        currently_points_to=currently_points_to,
    )


class TestSortModels:
    """Test suite for model sorting functionality."""

    def test_sort_by_release_date_desc(self):
        """Test sorting by release date (newest first)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", release_date="2024-01-01"),
            create_test_model("model2", release_date="2024-03-01"),
            create_test_model("model3", release_date="2024-02-01"),
        ]

        sorted_models = sort_models(models, "release_date", "desc")

        assert [m.id for m in sorted_models] == ["model2", "model3", "model1"]

    def test_sort_by_release_date_asc(self):
        """Test sorting by release date (oldest first)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", release_date="2024-01-01"),
            create_test_model("model2", release_date="2024-03-01"),
            create_test_model("model3", release_date="2024-02-01"),
        ]

        sorted_models = sort_models(models, "release_date", "asc")

        assert [m.id for m in sorted_models] == ["model1", "model3", "model2"]

    def test_sort_by_release_date_same_date(self):
        """Test stable sorting when models have same release date."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("zebra", release_date="2024-01-01"),
            create_test_model("alpha", release_date="2024-01-01"),
            create_test_model("beta", release_date="2024-01-01"),
        ]

        sorted_models = sort_models(models, "release_date", "desc")

        # Should be sorted by id when dates are the same (reverse order due to desc)
        assert [m.id for m in sorted_models] == ["zebra", "beta", "alpha"]

    def test_sort_by_quality_index_desc(self):
        """Test sorting by quality index (highest first)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", quality_index=50),
            create_test_model("model2", quality_index=100),
            create_test_model("model3", quality_index=75),
        ]

        sorted_models = sort_models(models, "quality_index", "desc")

        assert [m.id for m in sorted_models] == ["model2", "model3", "model1"]

    def test_sort_by_quality_index_asc(self):
        """Test sorting by quality index (lowest first)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", quality_index=50),
            create_test_model("model2", quality_index=100),
            create_test_model("model3", quality_index=75),
        ]

        sorted_models = sort_models(models, "quality_index", "asc")

        assert [m.id for m in sorted_models] == ["model1", "model3", "model2"]

    def test_sort_by_quality_index_same_quality(self):
        """Test stable sorting when models have same quality index."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("zebra", quality_index=100),
            create_test_model("alpha", quality_index=100),
            create_test_model("beta", quality_index=100),
        ]

        sorted_models = sort_models(models, "quality_index", "desc")

        # Should be sorted by id when quality is the same (reverse order due to desc)
        assert [m.id for m in sorted_models] == ["zebra", "beta", "alpha"]

    def test_sort_by_speed_index_desc(self):
        """Test sorting by speed index (highest first)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", speed_index=300),
            create_test_model("model2", speed_index=800),
            create_test_model("model3", speed_index=600),
        ]

        sorted_models = sort_models(models, "speed_index", "desc")

        assert [m.id for m in sorted_models] == ["model2", "model3", "model1"]

    def test_sort_by_speed_index_asc(self):
        """Test sorting by speed index (lowest first)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", speed_index=300),
            create_test_model("model2", speed_index=800),
            create_test_model("model3", speed_index=600),
        ]

        sorted_models = sort_models(models, "speed_index", "asc")

        assert [m.id for m in sorted_models] == ["model1", "model3", "model2"]

    def test_sort_by_speed_index_same_speed(self):
        """Test stable sorting when models have same speed index."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("zebra", speed_index=500),
            create_test_model("alpha", speed_index=500),
            create_test_model("beta", speed_index=500),
        ]

        sorted_models = sort_models(models, "speed_index", "desc")

        # Should be sorted by id when speed is the same (reverse order due to desc)
        assert [m.id for m in sorted_models] == ["zebra", "beta", "alpha"]

    def test_sort_by_cost_asc(self):
        """Test sorting by combined cost (lowest first)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", cost_per_input_token_usd=0.002, cost_per_output_token_usd=0.003),  # 0.005 total
            create_test_model("model2", cost_per_input_token_usd=0.001, cost_per_output_token_usd=0.001),  # 0.002 total
            create_test_model("model3", cost_per_input_token_usd=0.001, cost_per_output_token_usd=0.002),  # 0.003 total
        ]

        sorted_models = sort_models(models, "cost", "asc")

        assert [m.id for m in sorted_models] == ["model2", "model3", "model1"]

    def test_sort_by_cost_desc(self):
        """Test sorting by combined cost (highest first)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", cost_per_input_token_usd=0.002, cost_per_output_token_usd=0.003),  # 0.005 total
            create_test_model("model2", cost_per_input_token_usd=0.001, cost_per_output_token_usd=0.001),  # 0.002 total
            create_test_model("model3", cost_per_input_token_usd=0.001, cost_per_output_token_usd=0.002),  # 0.003 total
        ]

        sorted_models = sort_models(models, "cost", "desc")

        assert [m.id for m in sorted_models] == ["model1", "model3", "model2"]

    def test_sort_by_cost_same_cost(self):
        """Test stable sorting when models have same cost."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("zebra", cost_per_input_token_usd=0.001, cost_per_output_token_usd=0.001),
            create_test_model("alpha", cost_per_input_token_usd=0.001, cost_per_output_token_usd=0.001),
            create_test_model("beta", cost_per_input_token_usd=0.001, cost_per_output_token_usd=0.001),
        ]

        sorted_models = sort_models(models, "cost", "asc")

        # Should be sorted by id when cost is the same (normal order since asc)
        assert [m.id for m in sorted_models] == ["alpha", "beta", "zebra"]

    def test_latest_models_appear_above_target(self):
        """Test that latest models appear just above the models they point to."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", quality_index=50),
            create_test_latest_model("latest-model1", currently_points_to="model2"),
            create_test_model("model2", quality_index=100),
            create_test_latest_model("latest-model2", currently_points_to="model1"),
            create_test_model("model3", quality_index=75),
        ]

        sorted_models = sort_models(models, "quality_index", "desc")

        # Expected order: latest-model1, model2, model3, latest-model2, model1
        # (latest models appear just above their targets in the sorted order)
        assert [m.id for m in sorted_models] == ["latest-model1", "model2", "model3", "latest-model2", "model1"]

    def test_multiple_latest_models_pointing_to_same_target(self):
        """Test multiple latest models pointing to the same concrete model."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", quality_index=100),
            create_test_latest_model("latest-a", currently_points_to="model1"),
            create_test_latest_model("latest-b", currently_points_to="model1"),
            create_test_model("model2", quality_index=50),
        ]

        sorted_models = sort_models(models, "quality_index", "desc")

        # Both latest models should appear before model1, sorted by their id
        assert [m.id for m in sorted_models] == ["latest-a", "latest-b", "model1", "model2"]

    def test_orphaned_latest_models(self):
        """Test latest models that point to models not in the list (orphaned)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", quality_index=100),
            create_test_latest_model("latest-orphan", currently_points_to="nonexistent-model"),
            create_test_model("model2", quality_index=50),
            create_test_latest_model("latest-good", currently_points_to="model2"),
        ]

        sorted_models = sort_models(models, "quality_index", "desc")

        # Orphaned latest models should appear at the end
        assert [m.id for m in sorted_models] == ["model1", "latest-good", "model2", "latest-orphan"]

    def test_empty_list(self):
        """Test sorting an empty list."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = []

        sorted_models = sort_models(models, "quality_index", "desc")
        assert sorted_models == []

    def test_single_model(self):
        """Test sorting a single model."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [create_test_model("model1")]

        sorted_models = sort_models(models, "quality_index", "desc")
        assert [m.id for m in sorted_models] == ["model1"]

    def test_only_latest_models(self):
        """Test sorting when there are only latest models (all orphaned)."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_latest_model("latest-c", currently_points_to="missing-c"),
            create_test_latest_model("latest-a", currently_points_to="missing-a"),
            create_test_latest_model("latest-b", currently_points_to="missing-b"),
        ]

        sorted_models = sort_models(models, "quality_index", "desc")

        # Should be sorted by id since they're all orphaned
        assert [m.id for m in sorted_models] == ["latest-a", "latest-b", "latest-c"]

    def test_only_concrete_models(self):
        """Test sorting when there are only concrete models."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", quality_index=50),
            create_test_model("model2", quality_index=100),
            create_test_model("model3", quality_index=75),
        ]

        sorted_models = sort_models(models, "quality_index", "desc")

        # Should be sorted by quality index
        assert [m.id for m in sorted_models] == ["model2", "model3", "model1"]

    def test_sort_modifies_in_place(self):
        """Test that sort_models modifies the list in place."""
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [
            create_test_model("model1", quality_index=50),
            create_test_model("model2", quality_index=100),
        ]

        original_list = models
        sorted_models = sort_models(models, "quality_index", "desc")

        # Should return the same list object
        assert sorted_models is original_list
        assert [m.id for m in models] == ["model2", "model1"]

    @pytest.mark.parametrize("sort_by", ["release_date", "quality_index", "speed_index", "cost"])
    @pytest.mark.parametrize("order", ["asc", "desc"])
    def test_sort_preserves_model_data(
        self,
        sort_by: Literal["release_date", "quality_index", "speed_index", "cost"],
        order: Literal["asc", "desc"],
    ):
        """Test that sorting doesn't modify model data."""
        model = create_test_model(
            "test_model",
            quality_index=75,
            speed_index=600,
            cost_per_input_token_usd=0.001,
            cost_per_output_token_usd=0.002,
            release_date="2024-06-15",
        )
        models: list[ConciseModelResponse | ConciseLatestModelResponse] = [model]

        sort_models(models, sort_by, order)

        # Verify model data is unchanged
        sorted_model = models[0]
        assert isinstance(sorted_model, ConciseModelResponse)
        assert sorted_model.id == "test_model"
        assert sorted_model.quality_index == 75
        assert sorted_model.speed_index == 600
        assert sorted_model.cost_per_input_token_usd == 0.001
        assert sorted_model.cost_per_output_token_usd == 0.002
        assert sorted_model.release_date == "2024-06-15"
