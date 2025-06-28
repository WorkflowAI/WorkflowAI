INSTRUCTOR_PYTHON_LANDING_PAGE_SNIPPET = """```python
import os

import instructor
from openai import OpenAI
from pydantic import BaseModel


class UserInfo(BaseModel):
    name: str
    age: int

def extract_user_info(user_message: str) -> UserInfo:
    client = instructor.from_openai(
        OpenAI(base_url="https://run.workflowai.com/v1", api_key="<your-workflowai-key>"),
        mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
    )

    return client.chat.completions.create(
        model="user-info-extraction-agent/claude-3-7-sonnet-latest", # Agent now runs Claude 3.7 Sonnet
        response_model=UserInfo,
        messages=[{"role": "user", "content": user_message}],
    )

if __name__ == "__main__":
    user_info = extract_user_info("John Black is 33 years old.")
    print("Basic example result:", user_info)  # UserInfo(name='John Black', age=33)
```"""

INSTRUCTOR_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET = INSTRUCTOR_PYTHON_LANDING_PAGE_SNIPPET

INSTRUCTOR_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET = """```python
import instructor
from openai import OpenAI

# After (WorkflowAI Proxy)
client = instructor.from_openai(
    OpenAI(
        base_url="https://run.workflowai.com/v1", # Instructor now uses WorkflowAI's chat completion endpoint
        api_key=<WORKFLOWAI_API_KEY_PLACEHOLDER>
    ),
    mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS, # Allows to leverage structured generation
)


# Everything else (model calls, parameters) stays the same
response = client.chat.completions.create(
    ...,
)
```"""

INSTRUCTOR_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET = """```python
response = client.chat.completions.create(
    model="<PROPOSED_AGENT_NAME_PLACEHOLDER>",
    ...
)
```"""
