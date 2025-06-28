# Caching

WorkflowAI offers caching capabilities that allow you to reuse the results of identical requests, saving both time and cost. When enabled, the system will return stored results for matching requests instead of making redundant calls to the LLM.

### How Caching Works

1.  **Input Hash:** A unique hash is calculated based on the input provided to the model. This can be:
    *   The list of `messages` if no specific input variables are used.
    *   A combination of defined `input` variables (passed via `extra_body`) and the list of `messages` (relevant for replies or when messages supplement templated prompts).
2.  **Version Hash:** A hash representing the agent's configuration is computed. This typically includes:
    *   The model identifier (e.g., `gpt-4o`).
    *   The `temperature` setting.
    *   Other version parameters (such as `top_p`, `max_tokens`, etc.).
    *   For calls using input variables: the message templates are also factored in.
3.  **Cache Check:** Before calling the LLM provider and depending on the caching option (see below), WorkflowAI checks if a previous run exists with the exact same **Input Hash** and **Version Hash**.
4.  **Cache Hit:** If a matching run is found, its saved output is returned immediately, bypassing the actual model call.

## Caching Options

The behavior is controlled by the `use_cache` parameter, which can be passed in the `extra_body` of your API request. It accepts the following values:

*   `"auto"` (Default): The cache is checked **only if** the request's `temperature` is set to `0` and no `tools` are used in the request. This is the default behavior if `use_cache` is not specified.
*   `"always"`: The cache is always checked, regardless of the `temperature` setting or the use of `tools`.
*   `"never"`: The cache is never checked.

**Default Behavior with the Proxy:**

It's important to note that the standard OpenAI `chat/completions` endpoint, and thus the WorkflowAI proxy mimicking it, defaults to a `temperature` of `1`.

Since the default `use_cache` setting is `"auto"`, which requires `temperature=0` (and no `tools` in the request) for a cache check, **caching is effectively OFF by default when using the proxy with standard parameters.** You need to explicitly set `temperature=0` (and not use `tools`) or `use_cache="always"` to potentially benefit from caching.

*   Default `temperature = 1`
*   Default `use_cache = "auto"`
*   Using `tools` in the request
*   ➡️ Cache is **NOT** checked by default under these conditions.

**Examples:**

```python
# Assume 'client' is your configured OpenAI client pointing to WorkflowAI

# Example 1: Cache is NEVER hit (Default behavior)
# Reason: temperature defaults to 1, and use_cache defaults to "auto"
completion = client.chat.completions.create(
  model="my-chatbot/gpt-4o-mini",
  messages=[{"role": "user", "content": "Describe the meaning of life"}]
)

# Example 2: Cache CAN be hit
# Reason: temperature is explicitly 0, meeting the "auto" cache condition.
# A subsequent identical request will hit the cache.
completion = client.chat.completions.create(
  model="my-chatbot/gpt-4o-mini",
  messages=[{"role": "user", "content": "Describe the meaning of life"}],
  temperature=0
)

# Example 3: Cache CAN be hit (using Deployment and "always")
# Reason: use_cache="always" forces a cache check regardless of temperature.
# Assumes "my-agent/#1/production" defines a specific version (model + prompt).
completion = client.chat.completions.create(
  model="my-agent/#1/production", # Using a deployment
  # messages might be empty if the prompt is fully server-side
  messages=[], # required by SDK so pass a empty array
  extra_body={
    "input": {"variable_name": "variable_value"}, # Example input variable
    "use_cache": "always" # Force cache check
  }
  # response_format=MyPydanticModel # If expecting structured output
)

```

[TODO: add caching with SDK from WorkflowAI]

## Caching with Images

When using images as input to your models, it's important to understand how the caching mechanism handles different image formats:

### Image Input Formats and Cache Behavior

The cache hash is computed based on the **exact input provided**, not the actual content of the image. This means:

- If you provide an image as **base64-encoded data**, the cache hash will be calculated from that base64 string.
- If you provide an image as a **URL** (e.g., S3 URL), the cache hash will be calculated from the URL string itself.

**Important:** Even if both inputs represent the same image content, they will produce **different cache hashes** because the input format differs. The system does not download and compare image contents when computing cache hashes, as this would defeat the performance benefits of caching.

**Example:**

```python
# These two requests will have DIFFERENT cache hashes, even if the image is the same
 
# Request 1: Using base64
completion1 = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."}}
        ]
    }],
    temperature=0
)

# Request 2: Using S3 URL for the same image
completion2 = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user", 
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "https://s3.amazonaws.com/bucket/image.jpg"}}
        ]
    }],
    temperature=0
)

# These will NOT hit the same cache entry
```

### Best Practices for Image Caching

To maximize cache hits when working with images:

1. **Be consistent with your image format**: Choose either base64 or URL format and stick to it across your application.
2. **Use stable URLs**: If using URLs, ensure they don't contain changing parameters (like timestamps or signatures) that would alter the cache hash.
3. **Consider preprocessing**: If you need flexibility in image sources, consider standardizing to one format before making API calls.