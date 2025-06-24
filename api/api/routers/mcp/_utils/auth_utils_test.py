import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request

from .auth_utils import AuthResult, extract_auth_info_from_request


class TestExtractAuthInfoFromRequest:
    """Test the extract_auth_info_from_request function"""

    async def test_missing_auth_header(self):
        """Test handling of missing Authorization header"""
        # Create a mock request without Authorization header
        request = MagicMock(spec=Request)
        request.headers = {}
        
        result = await extract_auth_info_from_request(request)
        
        assert result is None

    async def test_invalid_auth_header_format(self):
        """Test handling of invalid Authorization header format"""
        # Create a mock request with invalid Authorization header
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "InvalidFormat token123"}
        
        result = await extract_auth_info_from_request(request)
        
        assert result is None

    @patch("api.routers.mcp._utils.auth_utils.storage")
    @patch("api.routers.mcp._utils.auth_utils.SecurityService")
    @patch("api.routers.mcp._utils.auth_utils.system_event_router")
    @patch("api.routers.mcp._utils.auth_utils.analytics_service")
    @patch("api.routers.mcp._utils.auth_utils.OrganizationProperties")
    async def test_successful_auth_extraction(
        self,
        mock_org_properties,
        mock_analytics_service,
        mock_system_event_router,
        mock_security_service_class,
        mock_storage,
    ):
        """Test successful auth extraction with valid token"""
        # Setup mocks
        mock_tenant = MagicMock()
        mock_tenant.slug = "test-org"
        mock_tenant.uid = "tenant-123"
        
        mock_org_props = MagicMock()
        mock_org_props.name = "Test Organization"
        mock_org_properties.build.return_value = mock_org_props
        
        mock_security_service = AsyncMock()
        mock_security_service.tenant_from_credentials.return_value = mock_tenant
        mock_security_service_class.return_value = mock_security_service
        
        # Create a mock request with valid Authorization header
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer valid-token-123"}
        
        result = await extract_auth_info_from_request(request)
        
        # Verify result
        assert result is not None
        assert isinstance(result, AuthResult)
        assert result.tenant_slug == "test-org"
        assert result.tenant_uid == "tenant-123"
        assert result.organization_name == "Test Organization"
        assert result.user_email is None  # Currently not implemented
        
        # Verify mocks were called correctly
        mock_security_service.tenant_from_credentials.assert_called_once_with("valid-token-123")
        mock_org_properties.build.assert_called_once_with(mock_tenant)

    @patch("api.routers.mcp._utils.auth_utils.storage")
    @patch("api.routers.mcp._utils.auth_utils.SecurityService")
    @patch("api.routers.mcp._utils.auth_utils.system_event_router")
    @patch("api.routers.mcp._utils.auth_utils.analytics_service")
    async def test_invalid_token(
        self,
        mock_analytics_service,
        mock_system_event_router,
        mock_security_service_class,
        mock_storage,
    ):
        """Test handling of invalid token"""
        # Setup mocks
        mock_security_service = AsyncMock()
        mock_security_service.tenant_from_credentials.return_value = None  # Invalid token
        mock_security_service_class.return_value = mock_security_service
        
        # Create a mock request with Authorization header
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer invalid-token"}
        
        result = await extract_auth_info_from_request(request)
        
        assert result is None
        mock_security_service.tenant_from_credentials.assert_called_once_with("invalid-token")

    @patch("api.routers.mcp._utils.auth_utils.storage")
    @patch("api.routers.mcp._utils.auth_utils.SecurityService")
    @patch("api.routers.mcp._utils.auth_utils.system_event_router")
    @patch("api.routers.mcp._utils.auth_utils.analytics_service")
    @patch("api.routers.mcp._utils.auth_utils.OrganizationProperties")
    async def test_organization_name_fallback(
        self,
        mock_org_properties,
        mock_analytics_service,
        mock_system_event_router,
        mock_security_service_class,
        mock_storage,
    ):
        """Test fallback to tenant slug when organization name is not available"""
        # Setup mocks
        mock_tenant = MagicMock()
        mock_tenant.slug = "fallback-org"
        mock_tenant.uid = "tenant-456"
        
        # Mock organization properties without a name attribute
        mock_org_props = MagicMock()
        # Remove the name attribute to test fallback
        del mock_org_props.name
        mock_org_properties.build.return_value = mock_org_props
        
        mock_security_service = AsyncMock()
        mock_security_service.tenant_from_credentials.return_value = mock_tenant
        mock_security_service_class.return_value = mock_security_service
        
        # Create a mock request
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer valid-token"}
        
        result = await extract_auth_info_from_request(request)
        
        # Verify fallback to tenant slug
        assert result is not None
        assert result.organization_name == "fallback-org"  # Should fallback to tenant.slug

    @patch("api.routers.mcp._utils.auth_utils.storage")
    async def test_exception_handling(self, mock_storage):
        """Test handling of exceptions during auth extraction"""
        # Make storage.system_storage raise an exception
        mock_storage.system_storage.side_effect = Exception("Storage error")
        
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer some-token"}
        
        result = await extract_auth_info_from_request(request)
        
        assert result is None