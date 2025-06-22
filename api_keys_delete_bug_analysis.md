# API Keys Delete Endpoint Bug Analysis

## Issue Description

The bug occurs when using the API keys delete endpoint (`DELETE /{tenant}/api/keys/{key_id}`) with API key authentication, particularly when deleting the last API key. This results in a 500 error due to an inconsistent state between the operation result and the HTTP response.

## Root Cause Analysis

### The Original Problematic Code

```python
@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    api_keys_service: APIKeyServiceDep,
    user: UserDep,  # Can be None with API key auth
) -> None:
    # BUG: Delete operation happens FIRST
    deleted = await api_keys_service.delete_key(key_id)

    if not deleted:
        raise HTTPException(404, "API key not found")
    
    # BUG: Authorization check happens AFTER delete
    if not user or user.user_id == "":
        raise HTTPException(401, "You are not authorized to delete this API key")

    return
```

### Problems Identified

1. **Logic Order Bug**: The delete operation executes before the authorization check
   - API key gets deleted from database
   - Then authorization is checked
   - If authorization fails, a 401 error is returned despite successful deletion

2. **API Key Authentication Handling Bug**: When using API key authentication:
   - The `user_auth_dependency` returns `None` for API key authentication
   - The check `if not user or user.user_id == ""` fails for `user = None`
   - This causes a 401 error even though API key authentication is valid

3. **Inconsistent State**: The combination creates a scenario where:
   - The API key is successfully deleted from the database
   - But the endpoint returns a 401 error
   - This creates confusion and potential data inconsistency

## The Fix

### Updated Code

```python
@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    api_keys_service: APIKeyServiceDep,
    user: UserDep,
) -> None:
    # FIX: Check authorization FIRST before any operations
    # Note: user can be None when using API key authentication, which is valid
    # The non_anonymous_organization dependency already ensures proper authentication
    if user is not None and user.user_id == "":
        raise HTTPException(401, "You are not authorized to delete this API key")

    # FIX: Perform delete operation ONLY after authorization passes
    deleted = await api_keys_service.delete_key(key_id)

    if not deleted:
        raise HTTPException(404, "API key not found")

    return
```

### Key Changes

1. **Reordered Logic**: Authorization check now happens BEFORE the delete operation
2. **Fixed API Key Authentication**: Changed `if not user or user.user_id == ""` to `if user is not None and user.user_id == ""`
   - Now correctly handles `user = None` (API key auth) as valid
   - Only rejects users with empty `user_id` (invalid JWT tokens)
3. **Consistent Behavior**: Operations only proceed if authorization passes

## Authentication Context

The endpoint supports two authentication methods:

1. **JWT Token Authentication**: `user` contains user data
2. **API Key Authentication**: `user` is `None` but authentication is valid

The `non_anonymous_organization` dependency already ensures proper authentication at the router level, so checking `user is not None` is not necessary for basic authentication validation.

## Testing

Added comprehensive tests to verify:

1. ✅ API key authentication works correctly (`user = None`)
2. ✅ JWT authentication works correctly (`user` with valid `user_id`)
3. ✅ Invalid users are rejected (`user` with empty `user_id`)
4. ✅ Non-existent keys return 404
5. ✅ Authorization is checked before deletion attempts

## Impact

This fix resolves:
- The 500 error when deleting the last API key using API key authentication
- Data consistency issues between operation success and HTTP response
- Confusion for users experiencing successful deletions with error responses

The fix maintains backward compatibility while ensuring proper authorization flow and consistent API behavior.