LANGCHAIN_PYTHON_LANDING_PAGE_SNIPPET = """```python
import os

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

# Configure ChatOpenAI to use the WorkflowAI endpoint and API key
chat = ChatOpenAI(
    base_url="https://run.workflowai.com/v1",
    api_key=SecretStr(os.environ.get("WORKFLOWAI_API_KEY")),  # Use your WorkflowAI API key
    model="my-assistant/gpt-4o-mini-latest",  # Any model supported by WorkflowAI
)

response = chat.invoke("Hello, how are you?")
print(response.content)
```"""


LANGCHAIN_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET = """```python
import os
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, SecretStr


class SentimentAnalysis(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"] = Field(...)
    confidence: float = Field(..., ge=0, le=1)
    explanation: str


llm = (
    ChatOpenAI(
        base_url="https://run.workflowai.com/v1",
        api_key=SecretStr(os.environ.get("WORKFLOWAI_API_KEY")),
        model="sentiment-analyzer/gpt-4o-mini-latest",
    )
    .with_structured_output(SentimentAnalysis)
)

messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="Analyze the sentiment of: {{text}}"),
]

result: SentimentAnalysis = llm.invoke(
    messages,
    extra_body={"input": {"text": "I had a wonderful day at the park!"}},
)
print(result)
```"""


LANGCHAIN_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET = """```python
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

# After (WorkflowAI Proxy)
chat = ChatOpenAI(
    base_url="https://run.workflowai.com/v1",  # ChatOpenAI now uses WorkflowAI's chat completion endpoint
    api_key=SecretStr(<WORKFLOWAI_API_KEY_PLACEHOLDER>),
    ...
)

response = chat.invoke("Hello!")
```"""


LANGCHAIN_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET = """```python
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

chat = ChatOpenAI(
    ...
    model="<PROPOSED_AGENT_NAME_PLACEHOLDER>",
)

response = chat.invoke("Hello!")
```"""
