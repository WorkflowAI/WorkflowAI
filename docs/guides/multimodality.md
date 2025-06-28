# Process images, PDFs, audio

## From the playground

...

## From code

### Images
You can send image data directly (as base64 encoded strings) or provide image URLs within the messages array, following the standard OpenAI format.

{% tabs %}

{% tab title="OpenAI SDK (Python)" %}

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
{% endtab %}
{% endtabs %}