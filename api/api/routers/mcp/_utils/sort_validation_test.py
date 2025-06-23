# pyright: reportPrivateUsage=false
"""Tests for sort field validation utilities."""

import pytest

from api.routers.mcp._utils.sort_validation import (
    SortValidationError,
    get_valid_agent_sort_fields,
    get_valid_model_sort_fields,
    get_valid_sort_orders,
    validate_agent_sort_params,
    validate_model_sort_params,
)


class TestValidateAgentSortParams:
    """Test suite for agent sort parameter validation."""

    def test_valid_agent_sort_params(self):
        """Test validation with all valid agent sort parameters."""
        # Test all valid combinations
        valid_fields = ["last_active_at", "total_cost_usd", "run_count"]
        valid_orders = ["asc", "desc"]

        for field in valid_fields:
            for order in valid_orders:
                sort_by, validated_order = validate_agent_sort_params(field, order)
                assert sort_by == field
                assert validated_order == order

    def test_invalid_agent_sort_field(self):
        """Test validation with invalid agent sort field."""
        with pytest.raises(SortValidationError) as exc_info:
            validate_agent_sort_params("invalid_field", "desc")

        error_message = str(exc_info.value)
        assert "Invalid sort field 'invalid_field' for agents" in error_message
        assert "last_active_at" in error_message
        assert "total_cost_usd" in error_message
        assert "run_count" in error_message

    def test_invalid_agent_sort_order(self):
        """Test validation with invalid sort order for agents."""
        with pytest.raises(SortValidationError) as exc_info:
            validate_agent_sort_params("last_active_at", "invalid_order")

        error_message = str(exc_info.value)
        assert "Invalid sort order 'invalid_order'" in error_message
        assert "asc" in error_message
        assert "desc" in error_message

    def test_both_invalid_agent_params(self):
        """Test validation when both parameters are invalid - should catch field first."""
        with pytest.raises(SortValidationError) as exc_info:
            validate_agent_sort_params("invalid_field", "invalid_order")

        # Should catch the sort field error first
        error_message = str(exc_info.value)
        assert "Invalid sort field 'invalid_field' for agents" in error_message

    @pytest.mark.parametrize("field", ["last_active_at", "total_cost_usd", "run_count"])
    @pytest.mark.parametrize("order", ["asc", "desc"])
    def test_agent_params_parametrized(self, field: str, order: str):
        """Parametrized test for all valid agent sort combinations."""
        sort_by, validated_order = validate_agent_sort_params(field, order)
        assert sort_by == field
        assert validated_order == order

    def test_case_sensitive_agent_validation(self):
        """Test that validation is case sensitive."""
        with pytest.raises(SortValidationError):
            validate_agent_sort_params("LAST_ACTIVE_AT", "desc")

        with pytest.raises(SortValidationError):
            validate_agent_sort_params("last_active_at", "DESC")


class TestValidateModelSortParams:
    """Test suite for model sort parameter validation."""

    def test_valid_model_sort_params(self):
        """Test validation with all valid model sort parameters."""
        # Test all valid combinations
        valid_fields = ["release_date", "quality_index", "cost"]
        valid_orders = ["asc", "desc"]

        for field in valid_fields:
            for order in valid_orders:
                sort_by, validated_order = validate_model_sort_params(field, order)
                assert sort_by == field
                assert validated_order == order

    def test_invalid_model_sort_field(self):
        """Test validation with invalid model sort field."""
        with pytest.raises(SortValidationError) as exc_info:
            validate_model_sort_params("invalid_field", "desc")

        error_message = str(exc_info.value)
        assert "Invalid sort field 'invalid_field' for models" in error_message
        assert "release_date" in error_message
        assert "quality_index" in error_message
        assert "cost" in error_message

    def test_invalid_model_sort_order(self):
        """Test validation with invalid sort order for models."""
        with pytest.raises(SortValidationError) as exc_info:
            validate_model_sort_params("quality_index", "invalid_order")

        error_message = str(exc_info.value)
        assert "Invalid sort order 'invalid_order'" in error_message
        assert "asc" in error_message
        assert "desc" in error_message

    def test_both_invalid_model_params(self):
        """Test validation when both parameters are invalid - should catch field first."""
        with pytest.raises(SortValidationError) as exc_info:
            validate_model_sort_params("invalid_field", "invalid_order")

        # Should catch the sort field error first
        error_message = str(exc_info.value)
        assert "Invalid sort field 'invalid_field' for models" in error_message

    @pytest.mark.parametrize("field", ["release_date", "quality_index", "cost"])
    @pytest.mark.parametrize("order", ["asc", "desc"])
    def test_model_params_parametrized(self, field: str, order: str):
        """Parametrized test for all valid model sort combinations."""
        sort_by, validated_order = validate_model_sort_params(field, order)
        assert sort_by == field
        assert validated_order == order

    def test_case_sensitive_model_validation(self):
        """Test that validation is case sensitive."""
        with pytest.raises(SortValidationError):
            validate_model_sort_params("QUALITY_INDEX", "desc")

        with pytest.raises(SortValidationError):
            validate_model_sort_params("quality_index", "DESC")


class TestHelperFunctions:
    """Test suite for helper functions."""

    def test_get_valid_agent_sort_fields(self):
        """Test that we get the correct list of valid agent sort fields."""
        fields = get_valid_agent_sort_fields()
        assert set(fields) == {"last_active_at", "total_cost_usd", "run_count"}
        assert len(fields) == 3

    def test_get_valid_model_sort_fields(self):
        """Test that we get the correct list of valid model sort fields."""
        fields = get_valid_model_sort_fields()
        assert set(fields) == {"release_date", "quality_index", "cost"}
        assert len(fields) == 3

    def test_get_valid_sort_orders(self):
        """Test that we get the correct list of valid sort orders."""
        orders = get_valid_sort_orders()
        assert set(orders) == {"asc", "desc"}
        assert len(orders) == 2


class TestSortValidationError:
    """Test suite for SortValidationError exception."""

    def test_exception_message(self):
        """Test that exception stores and displays the message correctly."""
        message = "Test error message"
        error = SortValidationError(message)

        assert error.message == message
        assert str(error) == message

    def test_exception_inheritance(self):
        """Test that SortValidationError inherits from Exception."""
        error = SortValidationError("test")
        assert isinstance(error, Exception)


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_empty_strings(self):
        """Test validation with empty strings."""
        with pytest.raises(SortValidationError):
            validate_agent_sort_params("", "desc")

        with pytest.raises(SortValidationError):
            validate_agent_sort_params("last_active_at", "")

        with pytest.raises(SortValidationError):
            validate_model_sort_params("", "desc")

        with pytest.raises(SortValidationError):
            validate_model_sort_params("quality_index", "")

    def test_whitespace_strings(self):
        """Test validation with whitespace strings."""
        with pytest.raises(SortValidationError):
            validate_agent_sort_params(" ", "desc")

        with pytest.raises(SortValidationError):
            validate_agent_sort_params("last_active_at", " ")

        # Test with fields that have whitespace (should fail)
        with pytest.raises(SortValidationError):
            validate_agent_sort_params(" last_active_at ", "desc")

    def test_similar_but_wrong_field_names(self):
        """Test validation with field names that are similar but incorrect."""
        # Test common mistakes for agent fields
        with pytest.raises(SortValidationError):
            validate_agent_sort_params("last_active", "desc")  # Missing _at

        with pytest.raises(SortValidationError):
            validate_agent_sort_params("total_cost", "desc")  # Missing _usd

        with pytest.raises(SortValidationError):
            validate_agent_sort_params("runs_count", "desc")  # Wrong order

        # Test common mistakes for model fields
        with pytest.raises(SortValidationError):
            validate_model_sort_params("release", "desc")  # Missing _date

        with pytest.raises(SortValidationError):
            validate_model_sort_params("quality", "desc")  # Missing _index

    def test_mixed_case_variations(self):
        """Test various case variations that should all fail."""
        case_variations = [
            "Last_Active_At",
            "lastActiveAt",
            "LAST_ACTIVE_AT",
            "last_Active_at",
        ]

        for variation in case_variations:
            with pytest.raises(SortValidationError):
                validate_agent_sort_params(variation, "desc")

        order_variations = ["ASC", "DESC", "Asc", "Desc", "aSc", "dEsC"]
        for variation in order_variations:
            with pytest.raises(SortValidationError):
                validate_agent_sort_params("last_active_at", variation)
