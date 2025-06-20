# Improving and debugging an existing agent

## Error: `max_tokens_exceeded`

When you encounter a `max_tokens_exceeded` error, this indicates the model hit a token limit. Follow this diagnostic process:

### Step 1: Check the `max_tokens` parameter first

**Most common cause:** The `max_tokens` parameter in your completion call is set too low, not that you've exceeded the model's context window.

```python
# ❌ Problem: max_tokens too low
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    max_tokens=1000  # Too low for complex outputs
)

# ✅ Solution: Increase max_tokens
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    max_tokens=4000  # Higher limit for output
)
```

### Step 2: Check model context window limits

If increasing `max_tokens` doesn't solve the issue, you may be hitting the model's total context window.

**Use MCP tools to find models with larger context windows:**

- Use `list_available_models` with `sort_by="max_tokens"` and `order="desc"` to see models with the highest context windows first
- Alternatively, use the v1/models API endpoint to get current context window information
- Compare your current model's limits with available alternatives

### Step 3: Solutions for context window issues

If you're truly hitting context limits:

1. **Switch to a larger context model** (use MCP tools to identify the best option)
2. **Batch processing for large datasets** - process data in smaller chunks
3. **Optimize output format** - reduce verbosity in structured outputs

### Diagnostic process:

1. ✅ **Check `max_tokens` parameter** - increase if too low
2. ✅ **Use MCP tools to review model options** - find models with higher context windows
3. ✅ **Consider model switch** - based on context window requirements
4. ✅ **Implement batching** - for large datasets
5. ✅ **Optimize output** - reduce unnecessary verbosity
