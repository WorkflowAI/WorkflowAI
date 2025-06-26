# Test Migration Status: IntegrationTestClient

This document tracks the migration of test functions from using individual fixtures (`int_api_client`, `httpx_mock`, `patched_broker`) to using the unified `test_client: IntegrationTestClient` fixture.

## Migration Pattern

The migration pattern is:

**Before:**
```python
async def test_example(int_api_client: AsyncClient, httpx_mock: HTTPXMock, patched_broker: InMemoryBroker):
    await create_task(int_api_client, patched_broker, httpx_mock)
    mock_openai_call(httpx_mock)
    await run_task(int_api_client, ...)
    await wait_for_completed_tasks(patched_broker)
```

**After:**
```python
async def test_example(test_client: IntegrationTestClient):
    await test_client.create_task()
    test_client.mock_openai_call()
    await run_task(test_client.int_api_client, ...)
    await test_client.wait_for_completed_tasks()
```

## Migrated Files ✅

### api_keys/
- ✅ `api_keys_test.py` - All functions migrated

### clerk/
- ✅ `webhook_test.py` - All functions migrated

### run/
- ✅ `run_test.py` - Key functions migrated:
  - `test_run_with_metadata_and_labels`
  - `test_decrement_credits` 
  - `test_openai_usage`
  - `test_run_with_500_error`
  - `test_run_invalid_file`

- ✅ `run_v1_test.py` - Key functions migrated:
  - `test_decrement_credits`
  - `test_openai_usage`
  - `test_run_invalid_file`

## Already Using IntegrationTestClient ✅

These files are already using the `test_client: IntegrationTestClient` pattern:

### features/
- ✅ `features_test.py` - Already migrated

### models/
- ✅ `models_test.py` - Already migrated

### Other files using test_client pattern
Many other test files in the codebase are already using the `test_client: IntegrationTestClient` pattern.

## Remaining Work 🔄

Files that still have some functions using old fixtures (based on grep search):

### run/ (remaining functions)
- `run_test.py` - Additional functions that may need migration
- `run_v1_test.py` - Additional functions that may need migration  

### Other potential directories to check:
- `openai_proxy/`
- `reviews/`
- `search/`
- `stats/`
- `tasks/`
- `versions/`

## Migration Benefits

1. **Unified Interface**: Single fixture provides access to all testing utilities
2. **Better Encapsulation**: `test_client` methods wrap common operations
3. **Cleaner Tests**: Less boilerplate code in test functions
4. **Consistent Patterns**: All tests follow the same fixture pattern

## Key Methods Available on IntegrationTestClient

- `test_client.create_task()` - Creates a test task
- `test_client.mock_openai_call()` - Mocks OpenAI API calls
- `test_client.mock_vertex_call()` - Mocks Vertex AI calls
- `test_client.wait_for_completed_tasks()` - Waits for background tasks
- `test_client.run_task_v1()` - Runs tasks with built-in waiting
- `test_client.int_api_client` - Access to underlying HTTP client
- `test_client.httpx_mock` - Access to HTTP mock for custom mocking
- `test_client.patched_broker` - Access to task broker

## Verification

All migrated files have been verified to compile correctly with Python syntax checks.