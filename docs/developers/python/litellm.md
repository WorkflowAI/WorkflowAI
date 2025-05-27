****# LiteLLM (Python)

LiteLLM is a drop-in replacement for the OpenAI client. This guide shows how to use LiteLLM together with WorkflowAI **only** using the functionality covered in the reference test-suite (`tests/litellm_start_test.py`).

---

## Basic Setup

All examples configure LiteLLM's global settings to point to WorkflowAI's OpenAI-compatible endpoint.

```python
import os
import litellm

litellm.api_base = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
litellm.api_key = os.environ.get("WORKFLOWAI_API_KEY")  # https://workflowai.com/keys
```

If you prefer, just set the two environment variables and skip the assignment.

---

## 1. Simple Completion

```python
response = litellm.completion(  # type: ignore
    model="openai/my-assistant/gpt-4o-mini-latest",
    messages=[{"role": "user", "content": "Hello, how are you?"}],
)
print(response.choices[0].message.content)
```

### Switching Models

Updating the `model` string is all that's needed to swap providers:

```python
response = litellm.completion(  # type: ignore
    model="openai/my-assistant/claude-3-7-sonnet-latest",  # ← Anthropic
    messages=[{"role": "user", "content": "Hello, Claude!"}],
)
```

---

## 2. Passing Input Variables (`extra_body`)

```python
response = litellm.completion(  # type: ignore
    model="openai/sentiment-analyzer/gpt-4o-mini-latest",
    messages=[{"role": "user", "content": "Analyze the sentiment of: {{text}}"}],
    extra_body={"input": {"text": "I had a wonderful day at the park!"}},
)
print(response.choices[0].message.content)
```

---

## 3. Structured Output

```python
from typing import Literal
from pydantic import BaseModel, Field
import litellm

class SentimentAnalysis(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(...)
    confidence: float = Field(..., ge=0, le=1)
    explanation: str

litellm.enable_json_schema_validation = True

response = litellm.completion(  # type: ignore
    model="openai/sentiment-analyzer/gpt-4o-mini-latest",
    messages=[
        {
            "role": "user",
            "content": "Analyze the sentiment of: {{text}}",
        }
    ],
    response_format=SentimentAnalysis,  # <- pass the Pydantic model
    extra_body={"input": {"text": "I had a terrible day at the park!"}},
)

result = SentimentAnalysis.model_validate_json(response.choices[0].message.content)
print(result)
```

---

## 4. Using Deployments

A **Deployment** in WorkflowAI binds a specific version of a prompt (schema) to an environment, e.g. `production`. You can target a deployment by structuring the `model` parameter as:

```
openai/<agent-name>/#<schema_id>/<environment>
```

```python
response = litellm.completion(  # type: ignore
    model="openai/sentiment-analyzer/#3/production",
    messages=[],  # instructions come from the deployment
    extra_body={"input": {"text": "I had a terrible day at the park!"}},
)
print(response.choices[0].message.content)
```

---

## Conclusion

With just a handful of lines you can:

1. Send chat prompts (`completion` / `acompletion`)
2. Pass template variables via `extra_body`
3. Receive validated structured data via `response_format`
4. Target server-managed prompt deployments

—all while retaining the familiar LiteLLM API surface.
