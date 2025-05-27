# LangChain (Python)

LangChain is a popular framework for building applications with large language models (LLMs). This guide shows how to use LangChain together with WorkflowAI **only** using the functionality covered in the reference test-suite (`tests/langchain_start_test.py`).

---

## Basic Setup

All examples use the `ChatOpenAI` class from the `langchain-openai` package and point it to WorkflowAI's OpenAI-compatible endpoint.

```python
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

WORKFLOWAI_API_URL = "https://run.workflowai.com/v1"  # Endpoint
WORKFLOWAI_API_KEY = "wai-***"                        # https://workflowai.com/keys

llm = ChatOpenAI(
    base_url=WORKFLOWAI_API_URL,
    api_key=SecretStr(WORKFLOWAI_API_KEY),
    model="my-assistant/gpt-4o-mini-latest",  # Any model supported by WorkflowAI
)
```

---

## 1. Simple Completion

```python
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

chat = ChatOpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key=SecretStr(WORKFLOWAI_API_KEY),
    model="my-assistant/gpt-4o-mini-latest",
)

response = chat.invoke("Hello, how are you?")
print(response.content)
```

### Switching Models

Updating the `model` string is all that's needed to swap providers:

```python
chat = ChatOpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key=SecretStr(WORKFLOWAI_API_KEY),
    model="my-assistant/claude-3-7-sonnet-latest",  # ← Anthropic
)
```

---

## 2. Passing Input Variables (`extra_body`)

WorkflowAI supports server-side prompt templating. To supply values for the `{{variable}}` placeholders in those templates, pass an `input` dict inside `extra_body`.

```python
from langchain.schema import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="Analyze the sentiment of: {{text}}"),
]

llm = ChatOpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key=SecretStr(WORKFLOWAI_API_KEY),
    model="sentiment-analyzer/gpt-4o-mini-latest",
)

response = llm.invoke(
    messages,
    extra_body={"input": {"text": "I had a wonderful day at the park!"}},
)
print(response.content)
```

---

## 3. Structured Output

WorkflowAI can return responses parsed directly into Pydantic models via LangChain's `.with_structured_output()` helper.

```python
from typing import Literal
from pydantic import BaseModel, Field, SecretStr
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

class SentimentAnalysis(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(...)
    confidence: float = Field(..., ge=0, le=1)
    explanation: str

llm = ChatOpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key=SecretStr("wai-***"),
    model="sentiment-analyzer/gpt-4o-mini-latest",
).with_structured_output(SentimentAnalysis)

messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="Analyze the sentiment of: {{text}}"),
]

result: SentimentAnalysis = llm.invoke(
    messages,
    extra_body={"input": {"text": "I had a wonderful day at the park!"}},
)
print(result)
```

---

## 4. Using Deployments

A **Deployment** in WorkflowAI binds a specific version of a prompt (schema) to an environment, e.g. `production`. You can target a deployment by structuring the `model` parameter as:

```
<agent-name> / #<schema_id> / <environment>
```

```python
from typing import Literal
from pydantic import BaseModel, Field, SecretStr
from langchain_openai import ChatOpenAI

class SentimentAnalysis(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: float
    explanation: str

llm = ChatOpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key=SecretStr("wai-***"),
    model="sentiment-analyzer/#3/production",  # ← deployment reference
).with_structured_output(SentimentAnalysis)

result: SentimentAnalysis = llm.invoke(
    input=[],  # No messages are needed since those are registered in the deployment, you must pass '[]', without the 'messages='
    extra_body={"input": {"text": "I had a terrible day at the park!"}},
)
print(result)
```

---

## Conclusion

With just a handful of lines you can:

1. Send chat prompts (`invoke`)
2. Pass template variables via `extra_body`
3. Receive validated structured data via `.with_structured_output()`
4. Target server-managed prompt deployments

—all while retaining the familiar LangChain API surface.
