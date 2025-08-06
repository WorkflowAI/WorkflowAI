# Improving Schema Validation Error Messages

## Problem Statement

Currently, when a JSON output doesn't match the expected schema, users receive a generic error message: "Task output does not match schema". This provides no information about what specifically went wrong, making it difficult for users to understand and fix the issue.

## Current Implementation

The validation happens in several places:

1. **`core/domain/task_io.py`**: The `enforce` method validates JSON against a schema using jsonschema library
2. **`core/domain/task_variant.py`**: The `validate_output` method catches validation errors and raises a generic message
3. **`core/runners/workflowai/workflowai_runner.py`**: The `build_structured_output` method validates the output

The current error flow:
- jsonschema raises a `ValidationError` with detailed information
- This is caught and converted to `JSONSchemaValidationError` with partial path information
- Finally, it's wrapped in another generic message that loses the details

## Proposed Solution

### 1. Enhanced Error Messages

Instead of "Task output does not match schema", provide detailed information:
- What field is missing or invalid
- What type was expected vs what was provided
- The path to the problematic field
- Example of valid values when available

### 2. Implementation Approach

We'll enhance the error handling at multiple levels:

1. **Preserve jsonschema error details**: The jsonschema library already provides rich error information including:
   - `path`: The path to the failing element
   - `message`: A description of what went wrong
   - `validator`: Which validation rule failed
   - `validator_value`: The expected value/constraint
   - `instance`: The actual value that failed validation

2. **Create a structured error formatter**: Build a utility that transforms jsonschema errors into user-friendly messages

3. **Update error propagation**: Ensure error details are preserved through the error handling chain

### 3. Example Error Messages

**Before:**
```
Task output does not match schema
```

**After:**
```
Task output does not match schema:
- Missing required field 'status' at root level
- Invalid type for field 'age': expected integer, got string "twenty-five"
- Value "INVALID" is not one of the allowed values ["ACTIVE", "INACTIVE", "PENDING"] for field 'state'
```

### 4. Implementation Plan

1. Create a new error formatter utility
2. Update `JSONSchemaValidationError` to store structured error information
3. Modify error handling in task validation to use the new formatter
4. Add comprehensive tests for various validation scenarios

## Benefits

1. **Better Developer Experience**: Users can immediately understand what's wrong
2. **Faster Debugging**: No need to manually compare output with schema
3. **Learning Tool**: Helps users understand the schema requirements
4. **Reduced Support Burden**: Fewer questions about validation failures

## Questions for Discussion

1. Should we include the full schema path or use a simplified notation?
2. How much of the actual vs expected values should we show (considering they might be large)?
3. Should we provide suggestions for common mistakes (e.g., "Did you mean 'status' instead of 'Status'?")?
4. Should error messages be different for partial validation vs full validation?

## Implementation Details

### Files Created/Modified

1. **`api/core/utils/schema_error_formatter.py`** - New utility for formatting validation errors
   - `format_validation_error()` - Formats a single validation error
   - `format_validation_errors()` - Formats multiple validation errors
   - `get_validation_error_details()` - Extracts error details for logging

2. **`api/core/domain/errors.py`** - Updated `JSONSchemaValidationError` class
   - Added `validation_errors` parameter to store original jsonschema errors

3. **`api/core/domain/task_io.py`** - Updated validation logic
   - Modified `enforce()` method to use the error formatter
   - Preserves detailed error information

4. **`api/core/domain/task_variant.py`** - Updated error propagation
   - Modified `validate_output()` to preserve detailed error messages

5. **`api/core/utils/schema_error_formatter_test.py`** - Comprehensive test suite
   - Tests for all major validation scenarios
   - Ensures error messages are user-friendly

### Code Examples

#### Before (Generic Error):
```python
# When validation fails, users see:
"Task output does not match schema"
```

#### After (Detailed Errors):
```python
# Missing required field
"Missing required field 'status' at root level"

# Type mismatch
"Invalid type at 'age': expected integer, got string"

# Nested field error
"Invalid type at 'person.age': expected integer, got string"

# Enum validation
"Invalid value at 'status': 'INVALID' is not one of ['ACTIVE', 'INACTIVE', 'PENDING']"

# Array validation
"Array too short at 'items': minimum 1 items, got 0"

# String constraints
"String too long at 'name': maximum length is 10, got 16"

# Additional properties
"Unexpected field 'unknown_field' at root level"

# Multiple errors
"""
Multiple validation errors:
- Missing required field 'name' at root level
- Invalid type at 'age': expected integer, got string
- Invalid value at 'status': 'INVALID' is not one of ['ACTIVE', 'INACTIVE']
"""
```

### How It Works

1. **Error Capture**: When jsonschema raises a `ValidationError`, we capture it with all its details
2. **Error Formatting**: The formatter analyzes the error type and creates a user-friendly message
3. **Path Building**: We construct a readable path to the failing element (e.g., `users[0].name`)
4. **Error Propagation**: The formatted message is passed through the error chain while preserving the original error details

### Future Enhancements

1. **Internationalization**: Support for multiple languages
2. **Error Suggestions**: Provide hints for common mistakes (e.g., "Did you mean 'status' instead of 'Status'?")
3. **Schema Snippets**: Show relevant parts of the schema in error messages
4. **Error Grouping**: Group related errors together (e.g., all missing required fields)
5. **Interactive Mode**: In development environments, provide interactive error fixing suggestions

### Testing Considerations

The implementation includes comprehensive tests covering:
- Required field validation
- Type mismatches
- Enum constraints
- String/number constraints
- Array validation
- Nested object validation
- Additional properties
- Multiple error scenarios

### Integration Notes

The changes are backward compatible and don't break existing functionality. The error messages are now more informative while maintaining the same error codes and structure that downstream code expects.

### Performance Impact

The error formatting adds minimal overhead since:
1. It only runs when validation fails (error path)
2. The formatting logic is simple string manipulation
3. We limit the number of errors shown (default: 5) to prevent excessive output

## Conclusion

This implementation significantly improves the developer experience by providing clear, actionable error messages when JSON validation fails. Users can now quickly identify and fix schema mismatches without having to manually compare their output against the schema.