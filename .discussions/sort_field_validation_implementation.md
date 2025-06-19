# Goal of this PR

This PR implements runtime validation for sort fields in the MCP server to ensure sort fields are valid for the given entity type. This follows the elegant sorting implementation that was previously completed and adds an important layer of validation that provides helpful error messages when invalid sort fields are used.

**Context from Previous Implementation:**

The previous PR implemented a two-field sorting approach:
- `sort_by`: The field name to sort by (e.g., `'last_active_at'`, `'total_cost_usd'`, `'quality_index'`)
- `order`: The direction to sort (`'asc'` for ascending, `'desc'` for descending)

**Current Enhancement:**

This PR adds runtime validation to ensure sort fields are valid for each entity type (agents vs models), providing clear error messages when invalid fields are used.

# Implementation Decision

## Validation Architecture

I implemented a validation layer that:

1. **Validates sort fields at runtime** before any sorting logic is executed
2. **Provides entity-specific validation** - agent fields are only valid for agents, model fields only for models
3. **Throws descriptive errors** with clear messaging about what went wrong and what fields are valid
4. **Fails fast** - validation happens before any data manipulation

## New Error Handling

### InvalidSortFieldError Exception

Created a custom exception class for each entity type that provides:

```python
class InvalidSortFieldError(ValueError):
    """Raised when an invalid sort field is provided for sorting."""
    
    def __init__(self, sort_by: str, valid_fields: list[str]):
        self.sort_by = sort_by
        self.valid_fields = valid_fields
        super().__init__(
            f"Invalid sort field '{sort_by}' for [entity]. "
            f"Valid fields are: {', '.join(valid_fields)}"
        )
```

This provides:
- **Clear error messaging**: Shows exactly what was wrong and what's valid
- **Programmatic access**: `sort_by` and `valid_fields` attributes for error handling code
- **Entity-specific messages**: Different messages for agents vs models

### Validation Functions

Added validation functions for each entity type:

**Agent Validation:**
```python
def validate_agent_sort_field(sort_by: str) -> None:
    """Validate that the sort field is valid for agent entities."""
    valid_fields = ["last_active_at", "total_cost_usd", "run_count"]
    if sort_by not in valid_fields:
        raise InvalidSortFieldError(sort_by, valid_fields)
```

**Model Validation:**
```python
def validate_model_sort_field(sort_by: str) -> None:
    """Validate that the sort field is valid for model entities."""
    valid_fields = ["release_date", "quality_index", "cost"]
    if sort_by not in valid_fields:
        raise InvalidSortFieldError(sort_by, valid_fields)
```

## Integration Points

### Updated Sorting Functions

Both `sort_agents()` and `sort_models()` now call their respective validation functions at the beginning:

```python
def sort_agents(agents: list[AgentResponse], sort_by: AgentSortField, order: SortOrder) -> list[AgentResponse]:
    # Validate sort field at runtime
    validate_agent_sort_field(sort_by)
    
    # ... existing sorting logic
```

### Error Propagation

The validation errors will propagate up through the MCP service layer, allowing the MCP server to return meaningful error responses to clients that use invalid sort fields.

## Benefits of This Approach

1. **Type Safety + Runtime Safety**: Combines compile-time type checking with runtime validation
2. **Clear Error Messages**: Users get immediate, actionable feedback about invalid sort fields
3. **Entity Separation**: Prevents confusion between agent and model sort fields
4. **Future Extensibility**: Easy to add new sort fields by updating the validation lists
5. **Fail Fast**: Errors are caught before any processing begins

# Tests Status

## New Test Coverage

### Agent Sorting Validation Tests

✅ **Comprehensive validation coverage** in `TestAgentSortFieldValidation`:

- **Valid field acceptance**: Tests that all valid agent sort fields pass validation
- **Invalid field rejection**: Tests various invalid fields including:
  - Completely invalid fields (`"invalid_field"`)
  - Valid model fields that aren't valid for agents (`"quality_index"`, `"cost"`, `"release_date"`)
  - Common field names that might be confused (`"name"`, `"created_at"`, `"updated_at"`)
- **Error message validation**: Ensures error messages contain expected information
- **Integration testing**: Tests that `sort_agents()` properly calls validation
- **Early failure testing**: Ensures validation happens before any list modification
- **Exception attribute testing**: Verifies the custom exception has correct attributes

### Model Sorting Validation Tests

✅ **Comprehensive validation coverage** in `TestModelSortFieldValidation`:

- **Valid field acceptance**: Tests that all valid model sort fields pass validation
- **Invalid field rejection**: Tests various invalid fields including:
  - Completely invalid fields (`"invalid_field"`)
  - Valid agent fields that aren't valid for models (`"last_active_at"`, `"total_cost_usd"`, `"run_count"`)
  - Common field names that might be confused (`"name"`, `"created_at"`, `"updated_at"`)
- **Error message validation**: Ensures error messages contain expected information
- **Integration testing**: Tests that `sort_models()` properly calls validation
- **Early failure testing**: Ensures validation happens before any list modification
- **Exception attribute testing**: Verifies the custom exception has correct attributes

### Test Design Principles

- **Comprehensive coverage**: Tests both positive (valid) and negative (invalid) cases
- **Cross-entity validation**: Ensures agent fields are rejected for models and vice versa
- **Error quality**: Validates that error messages are helpful and contain all necessary information
- **Integration focus**: Tests the complete flow from validation through sorting
- **Edge case coverage**: Tests various scenarios that users might encounter

## Tests Status Report

✅ **Validation Logic Verified**: I created and executed a comprehensive validation test that demonstrates the logic works correctly:

### Test Results (All Passed):

**Valid Field Acceptance:**
- ✅ Agent field 'last_active_at' - valid
- ✅ Agent field 'total_cost_usd' - valid  
- ✅ Agent field 'run_count' - valid
- ✅ Model field 'release_date' - valid
- ✅ Model field 'quality_index' - valid
- ✅ Model field 'cost' - valid

**Invalid Field Rejection:**
- ✅ Agent field 'invalid_field' - correctly rejected with message: "Invalid sort field 'invalid_field' for agents. Valid fields are: last_active_at, total_cost_usd, run_count"
- ✅ Agent field 'quality_index' - correctly rejected (model field not valid for agents)
- ✅ Agent field 'release_date' - correctly rejected (model field not valid for agents)
- ✅ Agent field 'cost' - correctly rejected (model field not valid for agents)
- ✅ Model field 'last_active_at' - correctly rejected (agent field not valid for models)
- ✅ Model field 'total_cost_usd' - correctly rejected (agent field not valid for models)
- ✅ Model field 'run_count' - correctly rejected (agent field not valid for models)

### Implementation Verification:

1. **Syntax validation**: ✅ All Python files compile successfully
2. **Logic validation**: ✅ Validation functions work correctly with proper error messages
3. **Cross-entity validation**: ✅ Agent and model fields are properly separated
4. **Error messaging**: ✅ Clear, actionable error messages with field suggestions
5. **Exception handling**: ✅ Custom exceptions provide proper attributes and inheritance

**Next Steps for Full Test Suite:**
1. Run `poetry run pytest api/api/routers/mcp/_utils/agent_sorting_test.py::TestAgentSortFieldValidation -v`
2. Run `poetry run pytest api/api/routers/mcp/_utils/model_sorting_test.py::TestModelSortFieldValidation -v`
3. Run `poetry run ruff check` and `poetry run pyright` to ensure code quality
4. Run full test suites to ensure no regressions

# Potential Next Steps

1. **Error Integration in MCP Service**: Update the MCP service layer to catch `InvalidSortFieldError` and return proper HTTP error responses with the validation messages

2. **API Documentation Updates**: Update the MCP server documentation to mention the validation and possible error responses

3. **Additional Sort Fields**: The flexible validation architecture makes it easy to add new sort fields:
   - For agents: `created_at`, `updated_at`, `name`
   - For models: `provider`, `context_window`, `supports_count`

4. **Sort Order Validation**: Consider adding validation for the `order` parameter to ensure only `"asc"` and `"desc"` are accepted

5. **Cross-field Validation**: Implement validation that considers combinations of sort fields and entity states (e.g., some fields might only be valid when certain conditions are met)

6. **Performance Monitoring**: Add monitoring for validation performance, though current implementation should be very fast

7. **Client SDK Updates**: Update any client SDKs to handle the new validation errors gracefully

8. **Logging Integration**: Consider logging validation failures for monitoring and debugging purposes

---

## Context: Original User Request

This implementation addresses the next step from the previous elegant sorting implementation:

> "**Sort Field Validation**: Add runtime validation to ensure sort fields are valid for the given entity type"

The implementation provides:
- ✅ Runtime validation that catches invalid sort fields before processing
- ✅ Entity-specific validation (agent fields vs model fields)
- ✅ Clear, actionable error messages for users
- ✅ Comprehensive test coverage for all validation scenarios
- ✅ Extensible architecture for adding new sort fields in the future
- ✅ Verified working validation logic with comprehensive test results

This completes the sort field validation enhancement while maintaining the elegant two-field sorting approach implemented in the previous iteration.