# Improved Schema Validation Error Messages

## Problem Statement

Currently, when a task output fails schema validation, users receive a generic error message: "Task output does not match schema". This provides little insight into what specifically went wrong, making it difficult for users to understand and fix the issues.

## Current Implementation Analysis

The current error handling flow:

1. `SerializableTaskIO.enforce()` calls `jsonschema.validate()`
2. When validation fails, a `ValidationError` is caught
3. The error is re-raised as `JSONSchemaValidationError` with minimal context
4. This eventually becomes a `FailedGenerationError` with the generic message

**Key locations:**
- `api/core/domain/task_io.py:68-71` - Current basic error handling
- `api/core/domain/task_variant.py:89` - Generic "Task output does not match schema" message
- `api/core/providers/base/httpx_provider_base.py:171` - Where validation errors become provider errors

## Proposed Solution

### 1. Enhanced Schema Validator (`DetailedSchemaValidator`)

Created a new utility class that:
- Leverages `jsonschema`'s detailed error reporting capabilities
- Generates human-readable error messages for different validation failure types
- Provides specific information about what went wrong and where

### 2. Error Message Improvements

The enhanced validator provides detailed messages for:

#### Missing Required Fields
- **Before:** `at [], 'name' is a required property`
- **After:** `Missing required field 'name' at root`

#### Type Mismatches
- **Before:** `at [age], 'thirty' is not of type 'integer'`
- **After:** `Expected integer but got str ('thirty') at age`

#### Invalid Enum Values
- **Before:** `at [status], 'unknown' is not one of ['active', 'inactive', 'pending']`
- **After:** `Value 'unknown' is not allowed at status. Allowed values: 'active', 'inactive', 'pending'`

#### Constraint Violations
- **Before:** `at [age], -5 is less than the minimum of 0`
- **After:** `Value -5 is too small at age. Minimum allowed: 0`

#### Additional Properties
- **Before:** `at [], Additional properties are not allowed ('email', 'phone' were unexpected)`
- **After:** `Unexpected properties at root: 'email', 'phone'`

### 3. Multiple Error Handling

When multiple validation errors occur, the system now:
- Lists up to 5 specific errors with bullet points
- Provides a count of total errors
- Truncates long error lists to avoid overwhelming output

### 4. Path Formatting

Improved JSON path representation:
- `user.profile.age` instead of `['user']['profile']['age']`
- `items[2].name` for array indices
- Clear indication of nested structures

### 5. Value Display

Smart formatting of values in error messages:
- Truncates long strings with ellipsis
- Shows object summaries (`object with 4 keys: 'name', 'email', ...`)
- Handles null, empty arrays, and complex types appropriately

## Implementation Details

### Core Components

1. **`DetailedSchemaValidator`** - Main validation class
2. **`validate_with_detailed_errors()`** - Convenience function
3. **Updated `SerializableTaskIO.enforce()`** - Integration point

### Integration Strategy

- **Backward Compatible**: Existing error handling still works
- **Drop-in Replacement**: Modified `enforce()` method to use detailed validation
- **Minimal Changes**: Only touched the validation layer, not the broader error handling

### Error Message Structure

```
[Single Error]
Expected integer but got str ('thirty') at user.age

[Multiple Errors]
Found 3 validation error(s):
  • Missing required field 'name' at root
  • Expected integer but got str ('thirty') at user.age  
  • Value 'unknown' is not allowed at status. Allowed values: 'active', 'inactive', 'pending'
```

## Benefits

### For Users
- **Clear Understanding**: Immediately know what's wrong and where
- **Faster Debugging**: Specific field names and expected values
- **Better UX**: Actionable error messages instead of cryptic technical details

### For Developers
- **Reduced Support Load**: Users can self-diagnose issues
- **Better Logs**: More informative error messages in logs and monitoring
- **Easier Testing**: Clear error messages make test assertions more meaningful

### For the System
- **Maintains Performance**: No significant overhead in validation
- **Backward Compatible**: Existing error handling continues to work
- **Extensible**: Easy to add new validation error types

## Examples of Improved Messages

### Real-world Schema Validation

**Schema:**
```json
{
  "type": "object",
  "properties": {
    "user": {
      "type": "object", 
      "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
        "email": {"type": "string", "format": "email"}
      },
      "required": ["name", "age"]
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1,
      "maxItems": 5
    }
  },
  "required": ["user"]
}
```

**Invalid Data:**
```json
{
  "user": {
    "age": -5,
    "email": "not-an-email"
  },
  "tags": [],
  "extra_field": "not allowed"
}
```

**New Error Message:**
```
Found 5 validation error(s):
  • Missing required field 'name' at user
  • Value -5 is too small at user.age. Minimum allowed: 0
  • Invalid email format at user.email. Got: 'not-an-email'
  • Array too short at tags. Expected at least 1 items, got 0
  • Unexpected properties at root: 'extra_field'
```

## Testing Strategy

Comprehensive test coverage includes:
- All major validation error types (required, type, enum, constraints)
- Nested object and array validation
- Multiple error scenarios
- Edge cases (empty values, long strings, complex objects)
- Path formatting for various nesting levels
- Value display formatting

## Future Enhancements

### Short-term Improvements
1. **Localization**: Support for multiple languages
2. **Contextual Hints**: Suggest common fixes for typical errors
3. **Schema Documentation**: Include field descriptions in error messages

### Medium-term Enhancements
1. **Interactive Validation**: Real-time validation feedback in UI
2. **Error Categorization**: Group related errors (e.g., all missing fields)
3. **Severity Levels**: Distinguish between critical and minor validation issues

### Long-term Possibilities
1. **AI-Powered Suggestions**: Use LLM to suggest fixes for validation errors
2. **Schema Evolution**: Detect when errors indicate schema changes needed
3. **Custom Validators**: Allow domain-specific validation error messages

## Performance Considerations

- **Minimal Overhead**: Uses the same underlying `jsonschema` library
- **Error Path Optimization**: Only computes detailed messages when validation fails
- **Memory Efficient**: Doesn't store large amounts of error context
- **Lazy Evaluation**: Error message formatting happens only when needed

## Migration Notes

### For Existing Code
- No changes required for existing error handling
- Error types remain the same (`JSONSchemaValidationError`)
- Backward compatible with current test expectations

### For New Code
- Can immediately benefit from detailed error messages
- Use `validate_with_detailed_errors()` for standalone validation
- Error messages are more suitable for user-facing displays

## Questions for Discussion

1. **Error Message Length**: Should we limit the total length of error messages to prevent overwhelming users?

2. **Customization**: Do we need domain-specific error message templates for different types of schemas?

3. **Logging**: Should detailed errors be logged differently (e.g., structured logging with error codes)?

4. **Client Integration**: How should the frontend handle and display these detailed error messages?

5. **Internationalization**: What's the priority for supporting multiple languages in error messages?

6. **Performance Monitoring**: Should we add metrics to track validation error patterns and frequency?

## Conclusion

The enhanced schema validation provides a significant improvement in user experience by replacing generic error messages with specific, actionable feedback. The implementation is backward compatible, well-tested, and designed for easy extension.

The change addresses the core issue of poor error messages while maintaining system performance and reliability. Users will now receive clear guidance on what went wrong and how to fix it, reducing frustration and support burden.

This foundation enables future enhancements like interactive validation, AI-powered suggestions, and better developer tooling around schema validation.