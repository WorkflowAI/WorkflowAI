# OpenAI (Python)

## Basic Usage

```python
import openai
import os

# Configure the OpenAI client to use the WorkflowAI endpoint and API key
openai.api_key = os.environ.get("WORKFLOWAI_API_KEY") # Use your WorkflowAI API key
openai.api_base = "https://run.workflowai.com/v1"

response = openai.ChatCompletion.create(
  model="gpt-4", # Or any model supported by your WorkflowAI setup
  messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ]
)

print(response.choices[0].message.content)
```

## Identifying your agent

```python
response = client.chat.completions.create(
  model="my-agent/gpt-4o",
  messages=[...]
)

print(response.choices[0].message.content)
```

## Switching models

```python
# Original call using GPT-4o
response = client.chat.completions.create(
  model="my-agent/gpt-4o",
  messages=[...]
)

# Switching to Claude 3.7 Sonnet (verify exact ID on workflowai.com/models)
response = client.chat.completions.create(
  model="my-agent/claude-3.7-sonnet-latest", # Simply change the model name
  messages=[...] 
)

# Switching to Google's Gemini 2.5 Pro (verify exact ID on workflowai.com/models)
response = client.chat.completions.create(
  model="my-agent/gemini/gemini-2.5pro-latest", # Use the appropriate model identifier
  messages=[...]
)
```

```python
# Assuming 'client' is your configured OpenAI client pointing to WorkflowAI
available_models = client.models.list()

for model in available_models.data:
    print(model.id)

# This will print the identifiers for all models enabled in your WorkflowAI setup
# e.g., gpt-4o, claude-3-sonnet-latest, gemini-1.5-flash-latest, etc.
```

## Reliable Structured Output

{% hint style="info" %}
**Note on Chatbots:** For purely conversational use cases where you only need text responses and not structured data extraction, this step might not be necessary.
{% endhint %}

Getting consistent, machine-readable output (like JSON) from language models often requires careful prompt engineering and post-processing. WorkflowAI simplifies this significantly by supporting OpenAI's structured output capabilities, enhanced with broader model compatibility. By defining your desired output structure using Pydantic, you can reliably get parsed data objects without complex prompting or manual validation.

The `openai` Python library offers a highly convenient way to achieve this by directly providing a [Pydantic](https://docs.pydantic.dev/latest/) model definition.

To get structured output using the `openai` Python library with WorkflowAI:

1.  Define your desired output structure as a Pydantic `BaseModel`.
2.  Use the `client.beta.chat.completions.parse()` method (note the `.parse()` instead of `.create()`).
3.  Pass your Pydantic class directly to the `response_format` parameter.
4.  Access the parsed Pydantic object directly from `response.choices[0].message.parsed`.

![Placeholder Structured Output](../assets/proxy/schema.png)

**Example: Getting Country using a Pydantic Model**

Let's redefine the `get_country` example using a Pydantic model:

```python
from pydantic import BaseModel
# Assuming `openai` client is configured as `client`

class CountryInfo(BaseModel):
    country: str

def get_country(city: str):
    # Use the `.parse()` method for structured output with Pydantic
    completion = client.beta.chat.completions.parse(
      # Use a descriptive agent prefix for organization
      model="country-extractor/gpt-4o",
      messages=[
        {"role": "system", "content": "You are a helpful assistant that extracts geographical information."},
        {"role": "user", "content": f"What is the country of {city}?"}
      ],
      # Pass the Pydantic class directly as the response format
      response_format=CountryInfo
    )
    
    parsed_output: CountryInfo = completion.choices[0].message.parsed
    return parsed_output
```

This approach leverages the `openai` library's integration with Pydantic to abstract away the manual JSON schema definition and response parsing, providing a cleaner developer experience.

**WorkflowAI Compatibility Advantage:**
A key benefit of using the WorkflowAI proxy is extended compatibility. While native OpenAI structured output requires specific models (like `gpt-4o`), WorkflowAI guarantees this structured output method works **100% of the time across all models** available through the proxy when using the `openai` Python library with Pydantic. You reliably get a parsed object matching your Pydantic class, regardless of the underlying model's native capabilities.

{% hint style="info" %}
**Team Note:** Clarify in examples that when using Pydantic/structured output, the prompt does *not* need to explicitly ask for JSON output, as WorkflowAI handles the formatting.
{% endhint %}

## Input Variables

...

## Deployments

```python
# Code after Step 4
from pydantic import BaseModel
import openai
import os

# Assuming client is configured for WorkflowAI
client = openai.OpenAI(
    api_key=os.environ.get("WORKFLOWAI_API_KEY"),
    base_url="https://run.workflowai.com/v1"
)

class EventDetails(BaseModel):
    event_name: str
    date: str
    time: str
    location: str

email_content = """Subject: Meeting Confirmation

Hi team,

Just confirming our project sync meeting for tomorrow, June 15th, at 2:00 PM PST in the Main Conference Room.

Please come prepared to discuss Q3 planning.

Thanks,
Alex
"""

# Call the deployment directly
completion = client.beta.chat.completions.parse(
  # Reference agent, schema ID, and deployment ID
  model="event-extractor/#1/production",
  messages=[],
  response_format=EventDetails,
  extra_body={
      # Only input variable is needed
      "input": {
          "email_body": email_content
      }
  }
)

# Access the parsed Pydantic object as before
parsed_event: EventDetails = completion.choices[0].message.parsed
print(f"Event Name: {parsed_event.event_name}")
print(f"Date: {parsed_event.date}")
# ... and so on
```

## Automatic Cost Calculation

While most standard LLM APIs return usage metrics (like input and output token counts), they typically don't provide the actual monetary cost of the request. Developers are often left to calculate this themselves, requiring them to maintain and apply up-to-date pricing information for each model.

WorkflowAI simplifies this significantly. The proxy automatically calculates the estimated cost for each LLM request based on the specific model used and WorkflowAI's current pricing data. This calculated cost is then conveniently included directly within the response object returned by the API call, making it easy to access the price for each completion.

Here's an example of how you access this cost data in Python:

🚧 [TODO: add tests in autopilot, update backend + code (below) to include latency as well]

```python
response = client.chat.completions.create(
  model="country-extractor/gpt-4o",
  messages=[
      {"role": "system", "content": "You extract the country from a given city."},
      {"role": "user", "content": "What country is Paris in?"}
  ]
)

print(f"Estimated cost for this request: ${response.choices[0].cost_usd:.6f}")
print(f"Latency for this request: {response.choices[0].duration_seconds:.2f} seconds")
```

You can also see the cost in WorkflowAI by going to the Cost page

![Placeholder Cost](/docs/assets/images/monitoring.png)

## User Feedback

As described in the [User Feedback](/docs/guides/user-feedback) guide, you can collect feedback from users about your AI features.

The feedback token is added to the choice object as `feedback_token` and allows you to submit feedback to WorkflowAI for the specific run without any additional authentication.

```python
response = client.chat.completions.create(
  model="my-agent/gpt-4o",
  messages=[...],
)

print(response.choices[0].feedback_token)
```

## Multimodality Support

WorkflowAI extends the OpenAI proxy functionality to support multimodal models, allowing you to process requests that include not only text but also other data types like images, PDFs and other documents, and audio. This is achieved by adhering to the OpenAI API format for multimodal inputs where applicable, or by providing specific WorkflowAI mechanisms.

### Image Input

You can send image data directly (as base64 encoded strings) or provide image URLs within the `messages` array, following the standard OpenAI format. WorkflowAI ensures these requests are correctly routed to compatible multimodal models like GPT-4o or Gemini models.

**Example: Structured Output from Image Analysis**

Here's how you can use the `openai` Python library with WorkflowAI to get structured data (like the city identified) from an image:

```python
import openai
import os
from pydantic import BaseModel, Field

# Configure the OpenAI client to use the WorkflowAI endpoint and API key
client = openai.OpenAI(
    api_key=os.environ.get("WORKFLOWAI_API_KEY"),
    base_url="https://run.workflowai.com/v1"
)

# Define the desired structured output using Pydantic
class LocationInfo(BaseModel):
    explanation: str = Field(description="Brief explanation of how the city was identified from the image.")
    city: str = Field(description="The city depicted in the image.")

# Use .parse() for structured output
completion = client.beta.chat.completions.parse(
  # Use a multimodal model available through WorkflowAI
  model="image-analyzer/gpt-4o",
  messages=[
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "Analyze this image and identify the city depicted. Provide a brief explanation for your identification."},
        {
          "type": "image_url",
          "image_url": {
            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Louvre_Courtyard%2C_Looking_West.jpg/2880px-Louvre_Courtyard%2C_Looking_West.jpg",
          },
        },
      ],
    }
  ],
  # Specify the Pydantic model as the response format
  response_format=LocationInfo
)

# Access the parsed Pydantic object
location_info: LocationInfo = completion.choices[0].message.parsed
```

### PDF Document Input

{% hint style="info" %}
**Team Note:** Add details and examples for processing PDF documents via the proxy.
{% endhint %}

### Audio Input

{% hint style="info" %}
**Team Note:** Add details and examples for processing audio files (e.g., transcription, analysis) via the proxy.
{% endhint %}
