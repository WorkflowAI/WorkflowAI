from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies.security import RequiredUserDep, UserDep, non_anonymous_organization
from api.dependencies.services import APIKeyServiceDep
from core.domain.api_key import APIKey
from core.domain.users import UserIdentifier

router = APIRouter(prefix="/api/keys", tags=["API Keys"], dependencies=[Depends(non_anonymous_organization)])


class CreateAPIKeyRequest(BaseModel):
    name: str


class APIKeyResponse(BaseModel):
    id: str
    name: str
    partial_key: str
    created_at: datetime
    last_used_at: datetime | None
    created_by: UserIdentifier

    @classmethod
    def from_domain(cls, key: APIKey) -> "APIKeyResponse":
        return cls(
            id=key.id,
            name=key.name,
            partial_key=key.partial_key,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            created_by=key.created_by,
        )


class APIKeyResponseCreated(APIKeyResponse):
    key: str


@router.post("", response_model=APIKeyResponseCreated, status_code=201)
async def create_api_key(
    api_keys_service: APIKeyServiceDep,
    user: RequiredUserDep,
    key_create: CreateAPIKeyRequest,
) -> APIKeyResponseCreated:
    """
    Create a new API key for the current organization
    Endpoint : POST {tenant}/api/keys

    Args:
        key_create (CreateAPIKeyRequest): Name to create the API key with

    Raises:
        HTTPException: 400 Bad Request
        HTTPException: 422 API key generation failed to create a unique key. Please try again.

    Returns:
        APIKeyResponseCreated
    """

    if not key_create or not key_create.name or len(key_create.name) < 3:
        raise HTTPException(400, "API Key name is required and must be at least 3 characters long")

    key_doc, key = await api_keys_service.create_key(
        key_create.name,
        user.identifier(),
    )
    return APIKeyResponseCreated(
        id=key_doc.id,
        name=key_create.name,
        partial_key=key_doc.partial_key,
        created_at=key_doc.created_at,
        last_used_at=key_doc.last_used_at,
        created_by=key_doc.created_by,
        key=key,
    )


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(api_keys_service: APIKeyServiceDep) -> List[APIKeyResponse]:
    """
    List all API keys for the current organization
    Endpoint : GET {tenant}/api/keys

    Returns:
        List[APIKeyResponse]
    """

    keys: List[APIKey] = await api_keys_service.get_keys()

    return [APIKeyResponse.from_domain(key) for key in keys]


@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    api_keys_service: APIKeyServiceDep,
    user: UserDep,
) -> None:
    """
    Delete an API key for the current organization
    Endpoint : DELETE {tenant}/api/keys/{key_id}

    Note: This endpoint supports both user JWT authentication and API key authentication.
    When using API key authentication, the user parameter will be None, which is valid.

    Raises:
        HTTPException: 404 Not Found
        HTTPException: 401 Unauthorized (only when user is not authenticated via JWT or API key)
    """

    # Check authorization first before performing any operations
    # Note: user can be None when using API key authentication, which is valid
    # The non_anonymous_organization dependency already ensures proper authentication
    if user is not None and user.user_id == "":
        raise HTTPException(401, "You are not authorized to delete this API key")

    # Perform the delete operation only after authorization checks pass
    deleted = await api_keys_service.delete_key(key_id)

    if not deleted:
        raise HTTPException(404, "API key not found")

    return
