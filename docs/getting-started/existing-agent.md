# Quickstart: existing agent

{% stepper %}
{% step %}
### Create an API key

Go to [https://workflowai.com/keys](https://workflowai.com/keys) and create a new API key.
{% endstep %}

{% step %}
### Integrate with your existing code

The only changes you need to make are updating the base URL and API key. Choose the integration method that matches your current setup:

{% tabs %}

{% tab title="OpenAI SDK (Python)" %}

```python
from openai import OpenAI

# setup WorkflowAI client
client = OpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key="wai--***",
)

response = client.chat.completions.create(
    ... # your existing code
)
```
{% endtab %}

{% tab title="TypeScript" %}

```typescript
import OpenAI from 'openai';

// setup WorkflowAI client
const client = new OpenAI({
  baseURL: "https://run.workflowai.com/v1",
  apiKey: "wai--***",
});

const response = await client.chat.completions.create({
    ... # your existing code
});
```
{% endtab %}

{% tab title="CURL" %}

```bash
curl -X POST "https://run.workflowai.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer wai--***" \
  -d '{
    "model": "gpt-4o-mini-latest",
    "messages": [
      {
        "role": "user",
        "content": "Hello, how are you?"
      }
    ]
  }'
```
{% endtab %}

{% tab title="Instructor (Python)" %}

```python
# setup WorkflowAI client
workflowai_client = OpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key="wai--***",
)

client = instructor.from_openai(workflowai_client,
    # recommended mode, but other modes are supported
    mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
    ... # your existing code
)
```
{% endtab %}

{% endtabs %}
{% endstep %}

{% step %}
### Run your agent once

Execute your code to start making requests through WorkflowAI. Your agent will automatically appear in the WorkflowAI dashboard once it makes its first request.
{% endstep %}

{% step %}
### View your dashboard

{% hint style="success" %}
🎉 **Success!** Your agent is running on WorkflowAI! Go to [https://workflowai.com](https://workflowai.com) to access the dashboard and see your agent.
{% endhint %}
{% endstep %}
{% endstepper %}

## Next steps:
- ...

## Troubleshooting

<details>
<summary>I don't see my agent in the dashboard</summary>

- Check that your agent has made at least one request through WorkflowAI. The agent will appear in the dashboard after its first successful request.
- Verify there are no errors in your application logs when making the API request.
- Ensure you're using the correct API key and base URL (`https://run.workflowai.com/v1`).

</details>

<details>
<summary>I'm using OpenAI for multiple endpoints (embeddings, audio, etc.)</summary>

If you are using OpenAI for multiple endpoints in your application:
- **Only modify the client used for `chat/completions` requests** to point to WorkflowAI
- **Keep using the standard OpenAI client** for all other endpoints (embeddings, Responses API, audio transcriptions, etc.)

WorkflowAI only supports the `chat/completions` endpoint, so other OpenAI functionality should continue using the standard OpenAI client.

</details>

<details>
<summary>What parameters (`stream`, `temperature`, `max_tokens`, etc.) are supported?</summary>

See the [reference/parameters.md](reference/parameters.md) documentation for a full list of supported parameters.

</details>