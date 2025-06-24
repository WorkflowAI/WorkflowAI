# Improving schema validation error messages

## Summary

When a task generation fails due to a mismatch between the model output and the task JSON schema we used to surface a very generic error message:

```
Task output does not match schema
```

This gave users *zero* context about what was actually wrong with the JSON they
produced.  All the information **did** exist (the underlying `jsonschema`
exception contains the failing path and a human-readable explanation) but it was
silently swallowed by `SerializableTaskVariant.validate_output()`.

## Change

* `SerializableTaskVariant.validate_output()` now re-raises
  `JSONSchemaValidationError` **with the original validation message appended**.
  The call-sites that convert this error into `InvalidGenerationError` /
  `FailedGenerationError` will automatically propagate the enriched message.
* A unit test (`TestValidateOutput`) covers the new behaviour.
* Down-stream component test updated to assert that the message *starts with*
  the original prefix rather than matching it exactly.

Example of the new message :

```
Task output does not match schema: at [greeting], 1 is not of type 'string'
```

## Open questions

1. **Should we expose the whole validation path to end users?**
   In some situations the schema can be large/complex and the raw message might
   be hard to parse.  We could consider a more structured payload, e.g.
   ```json
   {
     "path": "greeting",
     "error": "1 is not of type 'string'"
   }
   ```
   and keep the free-text `message` for backwards compatibility.
2. **Input schema errors** already carry details – should we align both input &
   output error messages and maybe factor duplication out of
   `SerializableTaskVariant`?
3. **Provider specific wrapping** – some providers map
   `JSONSchemaValidationError` to `InvalidGenerationError` (… →
   `FailedGenerationError`).  Do we want a dedicated error code for *schema
   mismatch* to make it easier to react programmatically?

Feedback welcome!