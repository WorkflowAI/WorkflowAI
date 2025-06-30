## Tracking Multi-Step Workflows

🚧 This feature is currently not implemented.

Often, complex tasks are broken down into multi-step workflows where the output of one LLM call becomes the input for the next, potentially involving different models or specialized agents (as discussed in patterns like [prompt chaining or orchestrator-workers](https://www.anthropic.com/engineering/building-effective-agents)).

WorkflowAI allows you to link these individual, stateless API calls together into a single logical workflow trace for better observability and debugging in the web UI. This helps visualize the entire flow of requests for a specific task instance.

![Placeholder Trace ID](../assets/proxy/workflow.png)

**Mechanism: Using `trace_id`**

To group calls into a workflow, include a unique identifier in the `extra_body` parameter of each API request belonging to that specific workflow instance. This parameter is passed directly to the OpenAI client's `create` or `parse` method when using the WorkflowAI proxy.

We recommend using the key `trace_id` within `extra_body` and structuring its value to include both a human-readable workflow name prefix and a unique instance identifier. This aids in identifying and filtering workflows in the UI.

1.  Define a short, descriptive name for your workflow type (e.g., `summarize-translate`).
2.  Generate a unique instance ID, preferably a time-ordered UUIDv7.
3.  Combine them into a single string, like `workflow_name/uuid`, and pass this as the `trace_id` value within the `extra_body` dictionary for every call belonging to that workflow instance:

```python
# Example structure of the API call using the recommended trace_id format
response = client.chat.completions.create(
    model="your-agent/your-model",
    messages=[...],
    # ... other standard parameters like temperature, max_tokens ...
    extra_body={ # Pass custom data relevant to WorkflowAI here
        # Format: "<workflow_name>/<unique_instance_id>"
        "trace_id": "summarize-translate/0190fba2-c61e-7f4b-8000-11a3d8f398e5",
        # If using templating, 'input' would also go here:
        # "input": { "variable_name": value }
    }
)
```

WorkflowAI will use this `trace_id` to group the associated runs together in the dashboard, providing a consolidated view of the entire workflow execution.

**Example: Summarization followed by Translation**

Let's illustrate this with a Python example where we first summarize a text and then translate the summary. Both steps will share the same `trace_id`.

```python
import openai
import os
import uuid
from pydantic import BaseModel

# 1. Configure the OpenAI client to use WorkflowAI
client = openai.OpenAI(
    api_key=os.environ.get("WORKFLOWAI_API_KEY"),
    base_url="https://run.workflowai.com/v1"
)

# 2. Define Pydantic models for structured output
class SummaryResult(BaseModel):
    summary_text: str

class TranslationResult(BaseModel):
    translated_text: str

def generate_trace_id(workflow_name: str) -> str:
    """Generates a trace ID prefixed with the workflow name.

    Args:
        workflow_name: A short, descriptive name for the workflow (e.g., 'summarize-translate').

    Returns:
        A string combining the workflow name and a UUIDv7, suitable for the trace_id.
        Example: 'summarize-translate/0190fba2-...' 
    """
    # Note: uuid.uuid7() requires Python 3.11+ or a backport library
    instance_id = uuid.uuid7()
    return f"{workflow_name}/{instance_id}"

def summarize_text(client: openai.OpenAI, text: str, trace_id: str) -> str:
    """Calls the summarizer agent using prompt templating and structured output."""
    # Use .parse() for structured output
    completion = client.beta.chat.completions.parse(
        model="article-summarizer/gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert summarizer. Output the concise summary."},
            {"role": "user", "content": "{{article_text}}"} # Template variable for text
        ],
        response_format=SummaryResult, # Specify Pydantic model for structured output
        extra_body={
            "trace_id": trace_id, # Include the workflow trace_id
            "input": { # Pass template variable values via 'input'
                "article_text": text
            }
        }
    )
    # Access the structured output via the .parsed attribute
    parsed_summary: SummaryResult = completion.choices[0].message.parsed
    return parsed_summary.summary_text

def translate_text(client: openai.OpenAI, text_to_translate: str, language: str, trace_id: str) -> str:
    """Calls the translator agent using prompt templating and structured output."""
    # Use .parse() for structured output
    completion = client.beta.chat.completions.parse(
        model=f"text-translator/claude-3.5-sonnet-latest",
        messages=[
            {"role": "system", "content": "Translate the following text to {{target_language}}."},
            {"role": "user", "content": "{{text_to_translate}}"} # Template variables
        ],
        response_format=TranslationResult, # Specify Pydantic model for structured output
        extra_body={
            "trace_id": trace_id, # Include the same workflow trace_id
            "input": { # Pass template variable values via 'input'
                "target_language": language,
                "text_to_translate": text_to_translate
            }
        }
    )
    # Access the structured output via the .parsed attribute
    parsed_translation: TranslationResult = completion.choices[0].message.parsed
    return parsed_translation.translated_text

def run_summarization_translation_workflow(article_text: str, target_language: str):
    """Orchestrates the summarization and translation workflow."""
    # Generate a unique, time-ordered trace ID for this workflow instance
    workflow_trace_id = generate_trace_id("summarize-translate")

    # Summarize step
    summary = summarize_text(client, article_text, workflow_trace_id)

    # Translate step (uses the summary from the previous step)
    translation = translate_text(client, summary, target_language, workflow_trace_id)

    return summary, translation

# --- Example Usage ---
long_article = "Sustainable agriculture is the production of food, fiber, or other plant or animal products using farming techniques that protect the environment, public health, human communities, and animal welfare..." # (truncated for brevity)

summary_result, translation_result = run_summarization_translation_workflow(long_article, "French")
```
