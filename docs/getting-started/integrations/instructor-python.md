# Instructor (Python) + WorkflowAI = 🫶

Instructor is powerful — but as you build with it, a few common pain points start to show up:

| Pain Points | Solutions |
|-------------|-----------|
| **Ever wish you could see outputs from different models side-by-side?** | WorkflowAI's [Playground](#comparing-models-side-by-side) lets you compare 100+ models on the same input with visual side-by-side results, latency, and cost analysis. |
| **When something breaks in production, do you have to guess what the LLM saw?** | Full [observability](#observability): see every input, output, cost, latency, and more. Share runs with your team and re-run them on different models for debugging. |
| **How do you run consistent evaluations across prompts and models?** | Built-in [evaluation system](#evaluations-and-benchmarks) with automated benchmarks. Compare configurations, track performance metrics, and make data-driven decisions. |
| **Is your team blocked every time someone wants to tweak a prompt?** | [Deployments](#update-prompts-and-models-without-deploying-code) let anyone in your team update prompts and models directly in the web interface, no code changes required. |
| **And when your AI provider is slow or down — is your app just… stuck?** | [Multi-provider fallbacks](#100-uptime) ensure 100% uptime. If your AI provider has issues, automatically fallback to other providers with zero downtime. |

We built WorkflowAI to address these problems — and it integrates with Instructor in just one line of code.

{% hint style="info" %}
WorkflowAI is free to use: we price match the providers and make our margin through volume discounts. [Learn more](/docs/getting-started/pricing.md).
{% endhint %}

## Get started in 1-minute

WorkflowAI integrates seamlessly with your existing [Instructor](https://github.com/instructor-ai/instructor) code.

```python
# setup WorkflowAI client
workflowai_client = OpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key="wai--***", # https://workflowai.com/keys
)

client = instructor.from_openai(workflowai_client,
    # recommended mode, but other modes are supported
    mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
)

client.chat.completions.create(
    # optional: prefix the model with the agent name
    model="user-info-extraction-agent/gpt-4o-mini-latest",
    ... # your existing Instructor code
)
```

- ✅ Get your API key from [https://workflowai.com/keys](https://workflowai.com/keys) (includes $5 free credits to get started)
- ✅ Set `base_url` to `https://run.workflowai.com/v1`
- ✅ Set `mode` to `OPENROUTER_STRUCTURED_OUTPUTS` ([recommended](#mode-parameter))
- ✅ Use the `<agent_name>/<model_name>` format for the `model` parameter ([optional but recommended](#identifying-your-agent))

{% hint style="info" %}
Prefixing the `model` parameter with an `agent-name` is optional but recommended. It allows you to organize your agents properly in the WorkflowAI web application, making them easier to find and manage.
{% endhint %}

### `mode` parameter

We strongly recommend `mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS`. This mode offers the highest reliability for structured outputs by:

*   **Leveraging native structured generation:** For models that support it, this guarantees the output object perfectly matches your `response_model`.
*   **Employing intelligent fallbacks:**
    *   If a model lacks native structured generation, WorkflowAI seamlessly transitions to JSON-mode. It instructs the model using the schema provided in the system message.
    *   If JSON-mode is also unsupported by the model, WorkflowAI will parse a JSON object from the model's raw completion. It includes an automatic retry mechanism if the generated JSON is malformed or doesn't conform to the required schema.

This multi-layered approach maximizes the chances of receiving a well-formed, schema-compliant output.

**Other Modes:**

*   If the `mode` parameter is omitted, Instructor defaults to `TOOLS` mode.
*   Other supported modes include `TOOLS_STRICT`, `JSON`, and `JSON_SCHEMA`. While these can also produce well-formed objects, `OPENROUTER_STRUCTURED_OUTPUTS` is the preferred choice. It's designed to make the most of native structured generation capabilities offered by various LLM providers.

## Identifying your agent

When using WorkflowAI with Instructor, the `model` parameter serves a dual purpose: it specifies the underlying language model to use and can optionally identify your agent within the WorkflowAI platform. While providing an agent identifier is not required, it offers organizational benefits for managing your agents.

We recommend using the format `<agent_name>/<model_name>` for the `model` parameter, such as:
- `model="user-info-extraction-agent/gpt-4o-mini-latest"`

By adding an agent name prefix (like `user-info-extraction-agent`), you'll create a more organized workspace in your WorkflowAI dashboard. This makes it significantly easier to locate specific agents, track their performance, and manage them effectively across your projects, as shown below:

![Agent list](</docs/assets/images/agent-list.png>)

{% hint style="info" %}
If you don't provide an agent name prefix in the `model` parameter (e.g., using just `"gpt-4o-mini-latest"` instead of `"user-info-extraction-agent/gpt-4o-mini-latest"`), your requests will automatically be assigned to the `default` agent. While this works perfectly fine, using named agents helps organize your LLM usage in the WorkflowAI dashboard, especially when working with multiple AI features.
{% endhint %}

## Accessing over 100+ models, without any setup

To change the model to use, simply update the `model` string:

```python
# Claude 3.7 Sonnet
client.chat.completions.create(
    model="user-info-extraction-agent/claude-3-7-sonnet-latest",
    ... # your existing Instructor code
)

# Gemini 2.5 Pro
client.chat.completions.create(
    model="user-info-extraction-agent/gemini-2.5-pro-preview-05-06",
    ...
)

# Grok
client.chat.completions.create(
    model="user-info-extraction-agent/grok-3-mini-fast-beta-high",
    ... # your existing Instructor code
)
```

This unified approach means you only need one API key (WorkflowAI's) instead of managing separate keys for OpenAI, Anthropic, Google, and other providers. WorkflowAI also handles the API differences between providers behind the scenes.

The complete list of our supported models is available [here](/docs/reference/models.md) or from the playground.

You can also get the list of models programmatically:
```python
# List all available models
models = client.models.list()
print(f"Found {len(models.data)} models:")
for model in models.data:
    print(f"- {model.id}")
```

## Comparing models side-by-side

WorkflowAI's 'Playground' allows you to run models side-by-side on the same input, in order to compare the model's output quality, latency and price, as shown below:

![Playground](/docs/assets/proxy/playground-outputs.png)

[Learn more about the playground](/docs/guides/playground.md)

## Observability

WorkflowAI allows you to view all the runs that were made for your agent:

![Run list](</docs/assets/images/runs/list-runs.png>)

[Learn more about observability](/docs/guides/observability.md)

### Input Variables

Introducing input variables separates static instructions from dynamic content. The separation makes your agents easier to observe, since WorkflowAI logs these input variables separately.

We'll introduce a new use case to showcase this feature: classifying an email address as 'personal', 'work' or 'unsure'.

You can see in the code snippet below that the instructions now contain `{{variable}}` placeholders to inject variables and input variables are passed separately in `extra_body['input']`.

```python
class EmailAddressClassificationOutput(BaseModel):
    kind: Literal["personal", "work", "unsure"]

instructions = """You must classify the email address as:
- 'personal' (gmail, yahoo, etc.),
- 'work' (company email address)
- or 'unsure'.
The email address is:
{{email_address}}"""

client.chat.completions.create(
    model="email-classifier-agent/gpt-4o-mini",
    response_model=EmailAddressClassificationOutput,
    messages=[{"role": "system", "content": instructions}],
    extra_body={"input": {"email_address": email_address}},
)
```

![Playground with input variables](/docs/assets/proxy/input-variables.png)

WorkflowAI, at run-time, will render your messages' templates with the provided input variables, before sending them to the underlying LLM.

{% hint style="info" %}
WorkflowAI's instructions templates support all [Jinja2](/docs/reference/prompt-templating-syntax.md) features.
{% endhint %}

## Update prompts and models without deploying code

Deployments is a feature that lets you update your agent's instructions, model, and temperature directly in the WorkflowAI UI—no code deployment required. This dramatically accelerates your iteration cycle, allowing you to make and test changes in seconds rather than waiting for engineering releases.

With deployments, anyone at your company (such as a product manager) can quickly maintain, improve, and adapt an agent to new requirements, ensuring your agents stay up-to-date and effective.


## Evaluations and benchmarks

🚧 [TODO: ...]
![Benchmarks](/docs/assets/images/benchmarks/benchmark-table.png)

## 100% uptime 

Our goal with WorkflowAI is to provide a 100% uptime for your AI agents. We have a multi-provider infrastructure with automatic fallbacks to ensure high availability.

Read more about our infrastructure and how to set up provider fallbacks [here](/docs/getting-started/reliability.md).

```python
completion = client.chat.completions.create(
    model="email-classifier-agent/gpt-4o-mini",
    messages=[..],
    extra_body={"use_fallback": ["gemini-2.0-flash-001", "o3-mini-latest-medium"]}, # if gpt-4o-mini is down, fallback to gemini-2.0-flash-001 then o3-mini-latest-medium
)
```

## Advanced Features

### Migrating from Instructor's `context` to WorkflowAI's `extra_body`

If you previously used Instructor's `context` parameter to pass variables for Jinja templating within your messages or for use in Pydantic validators, you'll need to adapt this when using WorkflowAI.

WorkflowAI uses the `extra_body={"input": ...}` structure to handle these variables. Your Jinja templates in messages remain the same (`{{ variable_name }}`).

**Previously (Standard Instructor):**
```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{
        "role": "user",
        "content": "User asked: {{ user_query }}"
    }],
    response_model=MyResponseModel,
    context={"user_query": "Tell me about machine learning."}
)
```

**Now (WorkflowAI with Instructor):**
```python
response = client.chat.completions.create(
    model="my-agent/gpt-4o-mini", # Note the agent/model naming
    messages=[{
        "role": "user",
        "content": "User asked: {{ user_query }}" # Jinja template is the same
    }],
    response_model=MyResponseModel,
    extra_body={"input": {"user_query": "Tell me about machine learning."}}
)
```

### Streaming

🚧 [TODO: ...]
Streaming requires a change in the Instructor client to support `stream=true` when a `mode=OPENROUTER_STRUCTURED_OUTPUTS` is used.

### Async Support

You can run generation asynchronously, using `AsyncOpenAI` as you would with the normal Instructor implementation:

```python
workflowai_async_client = AsyncOpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key="wai--***", # https://workflowai.com/keys
)
async_client = instructor.from_openai(
    workflowai_async_client,
    mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
)
```

### Description and Examples

You can significantly improve the LLM's understanding of the desired output structure by providing `description` and `examples` directly within your `response_model` schema. By using `pydantic.Field`, you can annotate each field with a clear description of its purpose and provide a list of illustrative examples. These descriptions and examples are passed along to the LLM as part of the schema definition, helping it grasp the expected data format and content for each attribute.

Here's an example:

```python
from typing import Optional, List
from pydantic import BaseModel, Field

class CalendarEvent(BaseModel):
    title: Optional[str] = Field(
        None, 
        description="The event title/name", 
        examples=["Team Meeting", "Quarterly Review"]
    )
    date: Optional[str] = Field(
        None, 
        description="Date in YYYY-MM-DD format", 
        examples=["2023-05-21", "2023-06-15"]
    )
    start_time: Optional[str] = Field(
        None, 
        description="Start time in 24-hour format", 
        examples=["14:00", "09:30"]
    )
    ...
```

By providing these details, you make the task clearer for the LLM, reducing ambiguity and leading to better, more reliable structured data extraction.

[Learn more about description and examples](/docs/guides/structured-outputs.md#description-and-examples)

### Cost, Latency

While most standard LLM APIs return usage metrics (like input and output token counts), they typically don't provide the actual monetary cost of the request. Developers are often left to calculate this themselves, requiring them to maintain and apply up-to-date pricing information for each model.

WorkflowAI simplifies cost tracking by automatically calculating the estimated cost for each LLM request based on the specific model used and WorkflowAI's current pricing data.

```python
class Answer(BaseModel):
    sentiment: str
    score: float

answer, completion = client.chat.completions.create_with_completion(
    model="sentiment-analysis-agent/gpt-4o-mini",
    response_model=Answer,
    messages=[{"role": "user", "content": "I love Workflow AI!"}],
)

# print("Structured answer:", answer)

cost = completion.model_extra.get('cost_usd')
latency = completion.model_extra.get("duration_seconds")
print(f"Latency (s): {latency:.2f}")
print(f"Cost   ($): ${cost:.6f}")
```

[Learn more about cost and latency](/docs/guides/costs.md)

### Multimodality

WorkflowAI fully supports multimodal inputs with Instructor, requiring no code changes to your existing implementation. You can seamlessly pass images, PDFs, and other supported media types using the standard Instructor syntax, and WorkflowAI will handle the processing automatically.

[Learn more about multimodality](/docs/guides/multimodality.md)

### Caching

WorkflowAI offers caching capabilities that allow you to reuse the results of identical requests, saving both time and cost. When enabled, the system will return stored results for matching requests instead of making redundant calls to the LLM.

[Learn more about caching](/docs/reference/caching.md)

## Using Other OpenAI Endpoints

{% hint style="warning" %}
**Endpoint Support Note:** The WorkflowAI `OpenAI` client (e.g., `workflowai_client` in the example above) is specifically designed to work with the `chat.completions` endpoint. If you need to use other OpenAI endpoints, such as `v1/audio/transcriptions` for audio transcription or `v1/embeddings` for creating embeddings, you should use a standard OpenAI Python client initialized with your OpenAI API key.
```python
# Example for using other OpenAI endpoints
from openai import OpenAI as StandardOpenAI

# Standard OpenAI client for other endpoints
standard_openai_client = StandardOpenAI(api_key="sk-...") # Your OpenAI API key

# Example: Transcribing an audio file
# with open("path_to_your_audio_file.mp3", "rb") as audio_file:
#     transcript = standard_openai_client.audio.transcriptions.create(
#         model="whisper-1",
#         file=audio_file
#     )
#     print(transcript.text)
```
{% endhint %}