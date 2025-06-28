# pyright: reportPrivateUsage=false
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from api.routers.mcp._mcp_models import PaginatedMCPToolReturn


class MockData(BaseModel):
    """Mock data model for testing"""

    info: str


class MockItem(BaseModel):
    """Mock item model for testing"""

    id: int
    name: str
    description: str


class TestPaginatedGenericMCPToolReturnPaginate:
    """Test suite for PaginatedGenericMCPToolReturn.paginate method"""

    @pytest.fixture
    def mock_data(self) -> MockData:
        """Create mock data for testing"""
        return MockData(info="test data")

    @pytest.fixture
    def mock_items(self) -> list[MockItem]:
        """Create mock items for testing"""
        return [
            MockItem(id=i, name=f"Item {i}", description=f"Description for item {i}")
            for i in range(1, 11)  # 10 items
        ]

    @pytest.fixture
    def basic_response(
        self,
        mock_data: MockData,
        mock_items: list[MockItem],
    ) -> PaginatedMCPToolReturn[MockData, MockItem]:
        """Create a basic response for testing"""
        return PaginatedMCPToolReturn[MockData, MockItem](
            success=True,
            data=mock_data,
            items=mock_items,
            error=None,
            messages=["Test message"],
        )

    def test_paginate_with_no_items(self, mock_data: MockData):
        """Test pagination when there are no items"""
        response = PaginatedMCPToolReturn[MockData, MockItem](
            success=True,
            data=mock_data,
            items=None,
            error=None,
            messages=None,
        )

        result = response.paginate(max_tokens=1000, page=1)

        assert result.success is True
        assert result.items == []
        assert result.pagination is not None
        assert result.pagination.has_next_page is False
        assert result.pagination.next_page is None
        assert result.pagination.max_tokens_limit == 1000

    def test_paginate_with_empty_items_list(self, mock_data: MockData):
        """Test pagination when items list is empty"""
        response = PaginatedMCPToolReturn[MockData, MockItem](
            success=True,
            data=mock_data,
            items=[],
            error=None,
            messages=None,
        )

        result = response.paginate(max_tokens=1000, page=1)

        assert result.success is True
        assert result.items == []
        assert result.pagination is not None
        assert result.pagination.has_next_page is False

    def test_paginate_with_zero_max_tokens(self, basic_response: PaginatedMCPToolReturn[MockData, MockItem]):
        """Test pagination with max_tokens = 0"""
        result = basic_response.paginate(max_tokens=0, page=1)

        assert result.success is True
        assert result.items == []
        assert result.pagination is not None
        assert result.pagination.has_next_page is False
        assert result.pagination.max_tokens_limit == 0

    def test_paginate_with_negative_max_tokens(self, basic_response: PaginatedMCPToolReturn[MockData, MockItem]):
        """Test pagination with negative max_tokens"""
        result = basic_response.paginate(max_tokens=-100, page=1)

        assert result.success is True
        assert result.items == []
        assert result.pagination is not None
        assert result.pagination.has_next_page is False

    def test_paginate_with_invalid_page_number(self, basic_response: PaginatedMCPToolReturn[MockData, MockItem]):
        """Test pagination with invalid page numbers"""
        # Page 0
        result = basic_response.paginate(max_tokens=1000, page=0)
        assert result.items == []
        assert result.pagination is not None
        assert result.pagination.has_next_page is False

        # Negative page
        result = basic_response.paginate(max_tokens=1000, page=-1)
        assert result.items == []
        assert result.pagination is not None
        assert result.pagination.has_next_page is False

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_base_response_exceeds_token_limit(
        self,
        mock_tokens_from_string: Mock,
        mock_data: MockData,
        mock_items: list[MockItem],
    ):
        """Test when base response (without items) exceeds token limit"""
        # Mock token counting - base response returns 500 tokens
        mock_tokens_from_string.return_value = 500

        response = PaginatedMCPToolReturn[MockData, MockItem](
            success=True,
            data=mock_data,
            items=mock_items,
            error=None,
            messages=["Test message"],
        )

        # Set max_tokens to 400 (less than base response + buffer)
        result = response.paginate(max_tokens=400, page=1)

        assert result.success is False
        assert result.items == []
        assert result.error is not None
        assert "Base response exceeds token limit" in result.error
        assert result.pagination is not None
        assert result.pagination.has_next_page is False

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_single_item_exceeds_available_tokens(self, mock_tokens_from_string: Mock, mock_data: MockData):
        """Test when a single item exceeds available tokens"""
        # First call for base response
        # Subsequent calls for items
        mock_tokens_from_string.side_effect = [
            100,  # Base response tokens
            2000,  # First item tokens (exceeds available)
        ]

        large_item = MockItem(id=1, name="Large Item", description="x" * 10000)
        response = PaginatedMCPToolReturn[MockData, MockItem](
            success=True,
            data=mock_data,
            items=[large_item],
            error=None,
            messages=None,
        )

        # Set max_tokens to 1000 (base=100 + buffer=100 leaves 800 available, but item needs 2000)
        result = response.paginate(max_tokens=1000, page=1)

        assert result.success is False
        assert result.items == []
        assert result.error is not None
        assert "Single item exceeds token limit" in result.error
        assert result.pagination is not None
        assert result.pagination.has_next_page is False

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_successful_single_page_pagination(
        self,
        mock_tokens_from_string: Mock,
        basic_response: PaginatedMCPToolReturn[MockData, MockItem],
    ):
        """Test successful pagination when all items fit in one page"""
        # Mock token counting
        mock_tokens_from_string.side_effect = [
            100,  # Base response tokens
            50,
            50,
            50,
            50,
            50,  # First 5 items (each 50 tokens)
            50,
            50,
            50,
            50,
            50,  # Next 5 items (each 50 tokens)
        ]

        # Max tokens = 1000, base = 100, buffer = 100, available = 800
        # All 10 items = 500 tokens, fits in one page
        result = basic_response.paginate(max_tokens=1000, page=1)

        assert result.success is True
        assert result.items is not None
        assert len(result.items) == 10
        assert result.items[0].id == 1
        assert result.items[9].id == 10
        assert result.pagination is not None
        assert result.pagination.has_next_page is False
        assert result.pagination.next_page is None

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_multi_page_pagination_first_page(
        self,
        mock_tokens_from_string: Mock,
        basic_response: PaginatedMCPToolReturn[MockData, MockItem],
    ):
        """Test pagination with multiple pages - requesting first page"""
        # Mock token counting
        mock_tokens_from_string.side_effect = [
            100,  # Base response tokens
            150,
            150,
            150,
            150,  # First 4 items (each 150 tokens = 600 total)
            150,  # 5th item would exceed limit
        ]

        # Max tokens = 800, base = 100, buffer = 100, available = 600
        # Only 4 items fit (4 * 150 = 600)
        result = basic_response.paginate(max_tokens=800, page=1)

        assert result.success is True
        assert result.items is not None
        assert len(result.items) == 4
        assert result.items[0].id == 1
        assert result.items[3].id == 4
        assert result.pagination is not None
        assert result.pagination.has_next_page is True
        assert result.pagination.next_page == 2

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_multi_page_pagination_second_page(
        self,
        mock_tokens_from_string: Mock,
        basic_response: PaginatedMCPToolReturn[MockData, MockItem],
    ):
        """Test pagination with multiple pages - requesting second page"""
        # Mock token counting
        token_counts = [100] + [150] * 20  # Base response + items
        mock_tokens_from_string.side_effect = token_counts

        # Max tokens = 800, base = 100, buffer = 100, available = 600
        # 4 items per page (4 * 150 = 600)
        result = basic_response.paginate(max_tokens=800, page=2)

        assert result.success is True
        assert result.items is not None
        assert len(result.items) == 4
        assert result.items[0].id == 5
        assert result.items[3].id == 8
        assert result.pagination is not None
        assert result.pagination.has_next_page is True
        assert result.pagination.next_page == 3

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_multi_page_pagination_last_page(
        self,
        mock_tokens_from_string: Mock,
        basic_response: PaginatedMCPToolReturn[MockData, MockItem],
    ):
        """Test pagination with multiple pages - requesting last page with partial items"""
        # Mock token counting
        token_counts = [100] + [150] * 20  # Base response + items
        mock_tokens_from_string.side_effect = token_counts

        # Max tokens = 800, base = 100, buffer = 100, available = 600
        # 4 items per page, so page 3 should have items 9-10 (only 2 items)
        result = basic_response.paginate(max_tokens=800, page=3)

        assert result.success is True
        assert result.items is not None
        assert len(result.items) == 2
        assert result.items[0].id == 9
        assert result.items[1].id == 10
        assert result.pagination is not None
        assert result.pagination.has_next_page is False
        assert result.pagination.next_page is None

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_requesting_non_existent_page(
        self,
        mock_tokens_from_string: Mock,
        basic_response: PaginatedMCPToolReturn[MockData, MockItem],
    ):
        """Test requesting a page that doesn't exist"""
        # Mock token counting
        token_counts = [100] + [150] * 20  # Base response + items
        mock_tokens_from_string.side_effect = token_counts

        # Request page 10 when only 3 pages exist
        result = basic_response.paginate(max_tokens=800, page=10)

        assert result.success is True
        assert result.items == []
        assert result.pagination is not None
        assert result.pagination.has_next_page is False
        assert result.pagination.next_page is None

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_variable_item_sizes(self, mock_tokens_from_string: Mock, mock_data: MockData):
        """Test pagination with items of varying token sizes"""
        items = [
            MockItem(id=1, name="Small", description="x"),
            MockItem(id=2, name="Medium", description="x" * 100),
            MockItem(id=3, name="Large", description="x" * 1000),
            MockItem(id=4, name="Small again", description="x"),
            MockItem(id=5, name="Medium again", description="x" * 100),
        ]

        response = PaginatedMCPToolReturn[MockData, MockItem](
            success=True,
            data=mock_data,
            items=items,
            error=None,
            messages=None,
        )

        # Mock token counting with variable sizes
        mock_tokens_from_string.side_effect = [
            100,  # Base response
            50,  # Item 1 (small)
            200,  # Item 2 (medium)
            400,  # Item 3 (large)
            50,  # Item 4 (small)
            200,  # Item 5 (medium)
        ]

        # Max tokens = 800, base = 100, buffer = 100, available = 600
        # Page 1: items 1 (50) + 2 (200) = 250 tokens
        # Item 3 (400) would make it 650, exceeding 600
        result = response.paginate(max_tokens=800, page=1)

        assert result.success is True
        assert result.items is not None
        assert len(result.items) == 2
        assert result.items[0].id == 1
        assert result.items[1].id == 2
        assert result.pagination is not None
        assert result.pagination.has_next_page is True

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_exactly_fitting_page(self, mock_tokens_from_string: Mock, mock_data: MockData):
        """Test when items exactly fit the available token limit"""
        items = [MockItem(id=i, name=f"Item {i}", description=f"Desc {i}") for i in range(1, 5)]

        response = PaginatedMCPToolReturn[MockData, MockItem](
            success=True,
            data=mock_data,
            items=items,
            error=None,
            messages=None,
        )

        # Mock token counting
        mock_tokens_from_string.side_effect = [
            100,  # Base response
            150,
            150,
            150,
            150,  # 4 items, each 150 tokens = 600 total (exactly available)
        ]

        # Max tokens = 800, base = 100, buffer = 100, available = 600
        result = response.paginate(max_tokens=800, page=1)

        assert result.success is True
        assert result.items is not None
        assert len(result.items) == 4
        assert result.pagination and result.pagination.has_next_page is False

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_pagination_preserves_original_fields(
        self,
        mock_tokens_from_string: Mock,
        basic_response: PaginatedMCPToolReturn[MockData, MockItem],
    ):
        """Test that pagination preserves all original response fields"""
        mock_tokens_from_string.side_effect = [100] + [50] * 10  # Base + items

        original_data = basic_response.data
        original_messages = basic_response.messages
        original_error = basic_response.error

        result = basic_response.paginate(max_tokens=1000, page=1)

        assert result.data == original_data
        assert result.messages == original_messages
        assert result.error == original_error
        assert result.success == basic_response.success

    def test_get_actual_token_count(self, basic_response: PaginatedMCPToolReturn[MockData, MockItem]):
        """Test the get_actual_token_count method"""
        with patch("api.routers.mcp._mcp_models.tokens_from_string") as mock_tokens:
            mock_tokens.return_value = 12345

            token_count = basic_response.get_actual_token_count()

            assert token_count == 12345
            mock_tokens.assert_called_once()
            # Verify it was called with JSON string and model
            call_args = mock_tokens.call_args
            assert isinstance(call_args[0][0], str)  # First arg should be JSON string
            assert call_args[0][1] == "gpt-4o"  # Default model

    @patch("api.routers.mcp._mcp_models.tokens_from_string")
    def test_pagination_info_included_in_token_count(
        self,
        mock_tokens_from_string: Mock,
        basic_response: PaginatedMCPToolReturn[MockData, MockItem],
    ):
        """Test that pagination info is included in token calculations"""
        # Setup mock to track all calls
        # Need enough values for base response + all items being processed
        mock_tokens_from_string.side_effect = [
            200,  # Base response with pagination info
            50,
            50,
            50,
            50,
            50,  # First 5 items (each 50 tokens)
            50,
            50,
            50,
            50,
            50,  # Remaining items if needed
        ]

        result = basic_response.paginate(max_tokens=500, page=1)

        # Verify first call includes pagination info in the base response
        first_call = mock_tokens_from_string.call_args_list[0]
        json_str = first_call[0][0]
        assert "pagination" in json_str
        assert "has_next_page" in json_str
        assert "max_tokens_limit" in json_str

        # Also verify the result
        assert result.items is not None
        assert result.success is True
        # With 200 base + 100 buffer = 200 available for items
        # Each item is 50 tokens, so 4 items fit (200 / 50 = 4)
        assert len(result.items) == 4
        assert result.pagination and result.pagination.has_next_page is True
