OPENAI_SDK_PYTHON_LANDING_PAGE_SNIPPET = """```python
import os
import openai

# Configure the OpenAI client to use the WorkflowAI endpoint and API key
openai.api_key = os.environ.get("WORKFLOWAI_API_KEY")  # Use your WorkflowAI API key
openai.api_base = "https://run.workflowai.com/v1"

response = openai.chat.completions.create(
    model="gpt-4o-2024-11-20",  # Or any model supported by your WorkflowAI setup
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ],
)

print(response.choices[0].message.content)
```"""

# For integrations that showcase structured generation we reuse the landing page snippet
# In future this can be swapped for a dedicated structured output example using `.parse()`.
OPENAI_SDK_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET = """```python
import os
import openai
from pydantic import BaseModel


# Configure the OpenAI client to use the WorkflowAI endpoint and API key
client = openai.OpenAI(
    api_key=os.environ.get("WORKFLOWAI_API_KEY"),  # Use your WorkflowAI API key
    base_url="https://run.workflowai.com/v1",
)


class CountryInfo(BaseModel):
    country: str


def get_country(city: str) -> CountryInfo:
    # Return the country of a city, parsed as a Pydantic object.

    completion = client.beta.chat.completions.parse(
        # Always prefix the model with an agent name for clear organization in WorkflowAI
        model="country-extractor/gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that extracts geographical information.",
            },
            {"role": "user", "content": f"What is the country of {city}?"},
        ],
        # Pass the Pydantic class directly as the response format
        response_format=CountryInfo,
    )

    # Access the parsed Pydantic object directly
    return completion.choices[0].message.parsed
```"""

OPENAI_SDK_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET = """```python
import openai

# After (WorkflowAI Proxy)
openai.api_key = <WORKFLOWAI_API_KEY_PLACEHOLDER>
openai.api_base = "https://run.workflowai.com/v1" # OpenAI SDK now uses WorkflowAI's chat completion API endpoint

# Everything else (model calls, parameters) stays the same
response = openai.chat.completions.create(
    ...,
)
```"""

OPENAI_SDK_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET = """```python
response = openai.chat.completions.create(
    model="<PROPOSED_AGENT_NAME_PLACEHOLDER>",
    ...
)
```"""
