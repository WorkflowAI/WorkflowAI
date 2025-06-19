# pyright: reportPrivateUsage=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUntypedFunctionDecorator=false
"""Unit tests for sort validation utilities."""

import pytest

from api.routers.mcp._utils.sort_validation import (
    InvalidSortFieldError,
    InvalidSortOrderError,
    SortValidationError,
    get_valid_agent_sort_fields,
    get_valid_model_sort_fields,
    get_valid_sort_orders,
    validate_agent_sort_field,
    validate_agent_sort_params,
    validate_model_sort_field,
    validate_model_sort_params,
    validate_sort_order,
)


class TestSortValidationExceptions:
    """Test suite for sort validation exception classes."""

    def test_sort_validation_error_inheritance(self):
        """Test that SortValidationError inherits from ValueError."""
        error = SortValidationError("test message")
        assert isinstance(error, ValueError)
        assert str(error) == "test message"

    def test_invalid_sort_field_error(self):
        """Test InvalidSortFieldError construction and properties."""
        error = InvalidSortFieldError("agent", "invalid_field", ["field1", "field2"])

        assert error.entity_type == "agent"
        assert error.field == "invalid_field"
        assert error.valid_fields == ["field1", "field2"]
        assert str(error) == "Invalid sort field 'invalid_field' for agent. Valid fields are: field1, field2"

    def test_invalid_sort_order_error(self):
        """Test InvalidSortOrderError construction and properties."""
        error = InvalidSortOrderError("invalid_order", ["asc", "desc"])

        assert error.order == "invalid_order"
        assert error.valid_orders == ["asc", "desc"]
        assert str(error) == "Invalid sort order 'invalid_order'. Valid orders are: asc, desc"


class TestValidFieldRetrieval:
    """Test suite for functions that retrieve valid fields from type annotations."""

    def test_get_valid_agent_sort_fields(self):
        """Test retrieval of valid agent sort fields."""
        fields = get_valid_agent_sort_fields()
        expected_fields = ["last_active_at", "total_cost_usd", "run_count"]

        assert isinstance(fields, list)
        assert set(fields) == set(expected_fields)

    def test_get_valid_model_sort_fields(self):
        """Test retrieval of valid model sort fields."""
        fields = get_valid_model_sort_fields()
        expected_fields = ["release_date", "quality_index", "cost"]

        assert isinstance(fields, list)
        assert set(fields) == set(expected_fields)

    def test_get_valid_sort_orders(self):
        """Test retrieval of valid sort orders."""
        orders = get_valid_sort_orders()
        expected_orders = ["asc", "desc"]

        assert isinstance(orders, list)
        assert set(orders) == set(expected_orders)


class TestAgentSortFieldValidation:
    """Test suite for agent sort field validation."""

    @pytest.mark.parametrize("sort_by", ["last_active_at", "total_cost_usd", "run_count"])
    def test_validate_agent_sort_field_valid(self, sort_by: str):
        """Test validation passes for valid agent sort fields."""
        # Should not raise any exception
        validate_agent_sort_field(sort_by)

    @pytest.mark.parametrize("sort_by", ["invalid_field", "release_date", "quality_index", "cost", ""])
    def test_validate_agent_sort_field_invalid(self, sort_by: str):
        """Test validation fails for invalid agent sort fields."""
        with pytest.raises(InvalidSortFieldError) as exc_info:
            validate_agent_sort_field(sort_by)

        error = exc_info.value
        assert error.entity_type == "agent"
        assert error.field == sort_by
        assert "last_active_at" in error.valid_fields
        assert "total_cost_usd" in error.valid_fields
        assert "run_count" in error.valid_fields


class TestModelSortFieldValidation:
    """Test suite for model sort field validation."""

    @pytest.mark.parametrize("sort_by", ["release_date", "quality_index", "cost"])
    def test_validate_model_sort_field_valid(self, sort_by: str):
        """Test validation passes for valid model sort fields."""
        # Should not raise any exception
        validate_model_sort_field(sort_by)

    @pytest.mark.parametrize("sort_by", ["invalid_field", "last_active_at", "total_cost_usd", "run_count", ""])
    def test_validate_model_sort_field_invalid(self, sort_by: str):
        """Test validation fails for invalid model sort fields."""
        with pytest.raises(InvalidSortFieldError) as exc_info:
            validate_model_sort_field(sort_by)

        error = exc_info.value
        assert error.entity_type == "model"
        assert error.field == sort_by
        assert "release_date" in error.valid_fields
        assert "quality_index" in error.valid_fields
        assert "cost" in error.valid_fields


class TestSortOrderValidation:
    """Test suite for sort order validation."""

    @pytest.mark.parametrize("order", ["asc", "desc"])
    def test_validate_sort_order_valid(self, order: str):
        """Test validation passes for valid sort orders."""
        # Should not raise any exception
        validate_sort_order(order)

    @pytest.mark.parametrize("order", ["invalid_order", "ascending", "descending", "ASC", "DESC", ""])
    def test_validate_sort_order_invalid(self, order: str):
        """Test validation fails for invalid sort orders."""
        with pytest.raises(InvalidSortOrderError) as exc_info:
            validate_sort_order(order)

        error = exc_info.value
        assert error.order == order
        assert "asc" in error.valid_orders
        assert "desc" in error.valid_orders


class TestCombinedValidation:
    """Test suite for combined sort parameter validation."""

    @pytest.mark.parametrize("sort_by", ["last_active_at", "total_cost_usd", "run_count"])
    @pytest.mark.parametrize("order", ["asc", "desc"])
    def test_validate_agent_sort_params_valid(self, sort_by: str, order: str):
        """Test combined validation passes for valid agent sort parameters."""
        # Should not raise any exception
        validate_agent_sort_params(sort_by, order)

    @pytest.mark.parametrize("sort_by", ["release_date", "quality_index", "cost"])
    @pytest.mark.parametrize("order", ["asc", "desc"])
    def test_validate_model_sort_params_valid(self, sort_by: str, order: str):
        """Test combined validation passes for valid model sort parameters."""
        # Should not raise any exception
        validate_model_sort_params(sort_by, order)

    def test_validate_agent_sort_params_invalid_field(self):
        """Test combined validation fails for invalid agent sort field."""
        with pytest.raises(InvalidSortFieldError) as exc_info:
            validate_agent_sort_params("invalid_field", "desc")

        error = exc_info.value
        assert error.entity_type == "agent"
        assert error.field == "invalid_field"

    def test_validate_agent_sort_params_invalid_order(self):
        """Test combined validation fails for invalid sort order."""
        with pytest.raises(InvalidSortOrderError) as exc_info:
            validate_agent_sort_params("last_active_at", "invalid_order")

        error = exc_info.value
        assert error.order == "invalid_order"

    def test_validate_model_sort_params_invalid_field(self):
        """Test combined validation fails for invalid model sort field."""
        with pytest.raises(InvalidSortFieldError) as exc_info:
            validate_model_sort_params("invalid_field", "desc")

        error = exc_info.value
        assert error.entity_type == "model"
        assert error.field == "invalid_field"

    def test_validate_model_sort_params_invalid_order(self):
        """Test combined validation fails for invalid sort order."""
        with pytest.raises(InvalidSortOrderError) as exc_info:
            validate_model_sort_params("quality_index", "invalid_order")

        error = exc_info.value
        assert error.order == "invalid_order"

    def test_validate_agent_sort_params_both_invalid(self):
        """Test that invalid field error is raised first when both parameters are invalid."""
        with pytest.raises(InvalidSortFieldError) as exc_info:
            validate_agent_sort_params("invalid_field", "invalid_order")

        # Should raise InvalidSortFieldError first since that's validated first
        error = exc_info.value
        assert error.entity_type == "agent"
        assert error.field == "invalid_field"

    def test_validate_model_sort_params_both_invalid(self):
        """Test that invalid field error is raised first when both parameters are invalid."""
        with pytest.raises(InvalidSortFieldError) as exc_info:
            validate_model_sort_params("invalid_field", "invalid_order")

        # Should raise InvalidSortFieldError first since that's validated first
        error = exc_info.value
        assert error.entity_type == "model"
        assert error.field == "invalid_field"


class TestEdgeCases:
    """Test suite for edge cases and error conditions."""

    def test_empty_string_validation(self):
        """Test validation with empty strings."""
        with pytest.raises(InvalidSortFieldError):
            validate_agent_sort_field("")

        with pytest.raises(InvalidSortFieldError):
            validate_model_sort_field("")

        with pytest.raises(InvalidSortOrderError):
            validate_sort_order("")

    def test_none_validation(self):
        """Test validation with None values (should raise TypeError due to string operations)."""
        with pytest.raises(TypeError):
            validate_agent_sort_field(None)  # type: ignore

        with pytest.raises(TypeError):
            validate_model_sort_field(None)  # type: ignore

        with pytest.raises(TypeError):
            validate_sort_order(None)  # type: ignore

    def test_case_sensitivity(self):
        """Test that validation is case-sensitive."""
        with pytest.raises(InvalidSortFieldError):
            validate_agent_sort_field("LAST_ACTIVE_AT")

        with pytest.raises(InvalidSortFieldError):
            validate_model_sort_field("QUALITY_INDEX")

        with pytest.raises(InvalidSortOrderError):
            validate_sort_order("ASC")

        with pytest.raises(InvalidSortOrderError):
            validate_sort_order("DESC")
