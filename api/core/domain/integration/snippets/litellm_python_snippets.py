LITELLM_PYTHON_LANDING_PAGE_SNIPPET = """```python
import os
import litellm

litellm.api_base = "https://run.workflowai.com/v1"
litellm.api_key = os.environ.get("WORKFLOWAI_API_KEY")

response = litellm.completion( # type: ignore
    model="openai/user-info-extraction/gpt-4o-mini-latest",
    messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Hello, how are you?"}],
)
```"""

LITELLM_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET = """```python
import os
import litellm

litellm.api_base = "https://run.workflowai.com/v1"
litellm.api_key = os.environ.get("WORKFLOWAI_API_KEY")

class UserDetails(BaseModel):
    name: str = Field(description="User's name")
    age: int = Field(description="User's age")

response = litellm.completion( # type: ignore
    model="openai/user-info-extraction/claude-3-7-sonnet-latest",
    messages=[
        {
            "role": "user",
            "content": "Extract user details from the following text: '{{text}}'",
        }
    ],
    response_format=UserDetails, # Pass the Pydantic model class
    extra_body={"input": {"text": "Hello, I'm Bob and I'm 30 years old."}},
)
```"""

LITELLM_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET = """```python
import os
import litellm

litellm.api_base = "https://run.workflowai.com/v1")
litellm.api_key = <WORKFLOWAI_API_KEY_PLACEHOLDER>

response = litellm.completion( # type: ignore
    model=f"openai/"gpt-4o-mini-latest"", # The model string includes 'openai', because WorkflowAI is an OpenAI compatible endpoint
    ...,
)

print(response.choices[0].message.content)
```"""

LITELLM_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET = """```python
response = litellm.completion( # type: ignore
    model="openai/<PROPOSED_AGENT_NAME_PLACEHOLDER>", # The model string includes 'openai', because WorkflowAI is an OpenAI compatible endpoint
    ...,
)
```"""
