# DSPy (Python) + WorkflowAI = 🫶

## Why use WorkflowAI with DSPy?

WorkflowAI integrates seamlessly with your existing [DSPy](https://github.com/stanfordnlp/dspy) code. Simply configure DSPy to use WorkflowAI's OpenAI-compatible endpoint, and you instantly get:

- **Access to over [100+ models](https://workflowai.com/developers/python/dspy) (and counting)** from OpenAI, Google, Anthropic, Llama, Grok, Mistral, etc. New models are usually added to WorkflowAI just a few hours after their public release.
- **High Reliability with Automatic Fallback** thanks to our multi-provider infrastructure. For example, we fall back on Azure OpenAI when OpenAI is down. If using Claude, we fall back on AWS Bedrock when Anthropic is down.
- **Type-safe structured outputs** using DSPy's signature-based approach, enhanced by WorkflowAI's robust parsing and retry mechanisms for models that support it.
- **Unlimited, free observability** visualize all your LLMs [runs](https://docs.workflowai.com/concepts/runs), share runs with your team, [evaluate](https://docs.workflowai.com/features/reviews) runs, add runs to [benchmarks](https://docs.workflowai.com/features/benchmarks), etc.
- **Fix your agents in seconds without deploying code** Use our [deployment](#using-deployments-for-server-managed-instructions) features to enhance & deploy your agent's instructions right from our web-app.
- **Zero token price markup** because we negotiate bulk deals with major providers, you will pay exactly the same price as if you were going directly to the provider.
- **Cloud-based or self-hosted** thanks to our [open-source](https://github.com/WorkflowAI/WorkflowAI/blob/main/LICENSE) licensing model
- **We value your privacy** and we are SOC-2 Type 1 certified. We do not train models on your data, nor do the LLM providers we use.

Learn more about all WorkflowAI's features in our [docs](https://docs.workflowai.com/).

## 1-minute integration of WorkflowAI in existing DSPy code

### DSPy Setup (optional)

If not done already, install the required packages:
```bash
pip install dspy
```

### WorkflowAI credentials config

You can obtain your WorkflowAI API key with **$5 of free credits** [here](https://workflowai.com/developers/python/dspy/).

Then either export your credentials:
```bash
export WORKFLOWAI_API_KEY=<your-workflowai-api-key>
export WORKFLOWAI_API_URL=https://run.workflowai.com/v1
```

or add those to a .env:
```bash
WORKFLOWAI_API_KEY=<your-workflowai-api-key>
WORKFLOWAI_API_URL=https://run.workflowai.com/v1
```

## Basic Setup

All examples use DSPy's `LM` class configured to work with WorkflowAI's OpenAI-compatible endpoint.

```python
import os
import dspy

# Configure DSPy to use the WorkflowAI API
# Get your API key with $5 free credits at workflowai.com/developers/python/dspy/
WORKFLOWAI_API_URL = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
WORKFLOWAI_API_KEY = os.environ.get("WORKFLOWAI_API_KEY")  # Replace with your actual API key if not using env vars

lm = dspy.LM(
    "openai/sentiment-analyzer/gpt-4o-mini-latest",  # Any model supported by WorkflowAI
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL
)
dspy.configure(lm=lm)
```

### Why use `model=openai/<agent_name>/<model_details>`?

When specifying the `model` parameter for `dspy.LM` with WorkflowAI, the string is structured to include:
- `openai/` - indicates we're using the OpenAI-compatible API format
- `<agent_name>/` - becomes the agent name in your WorkflowAI dashboard for organization
- `<model_details>` - the specific model identifier that WorkflowAI will use

Using a consistent `<agent_name>` for related tasks allows your different use-cases to be properly organized in your WorkflowAI account.

## Simple Sentiment Analysis

Here's how to perform sentiment analysis using DSPy's signature-based approach:

```python
import os
import dspy
from typing import Literal

# Configure DSPy
WORKFLOWAI_API_URL = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
WORKFLOWAI_API_KEY = os.environ.get("WORKFLOWAI_API_KEY")

lm = dspy.LM(
    "openai/sentiment-analyzer/gpt-4o-mini-latest",
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL
)
dspy.configure(lm=lm)

# Define the signature
class SentimentAnalysis(dspy.Signature):
    """Classify sentiment of a given sentence."""

    sentence: str = dspy.InputField()
    sentiment: Literal["positive", "negative", "neutral"] = dspy.OutputField()
    confidence: float = dspy.OutputField()

# Create predictor
classify = dspy.Predict(SentimentAnalysis)

# Run analysis
response = classify(sentence="This book was super fun to read, though not the last chapter.")
print(f"Sentiment: {response.sentiment}")
print(f"Confidence: {response.confidence}")
```

## Switching Models

Updating the model string is all that's needed to swap providers:

```python
# Using Claude instead of GPT
lm = dspy.LM(
    "openai/sentiment-analyzer/claude-3-7-sonnet-latest",  # ← Anthropic model
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL
)
dspy.configure(lm=lm)
```

The complete list of our supported models is available [here](https://workflowai.com/developers/python/dspy).

## Passing Input Variables

WorkflowAI supports server-side prompt templating. To supply values for the `{{variable}}` placeholders in those templates, pass an `input` dict inside `extra_body` via the `config` parameter:

```python
import os
import dspy
from typing import Literal

# Configure DSPy
WORKFLOWAI_API_URL = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
WORKFLOWAI_API_KEY = os.environ.get("WORKFLOWAI_API_KEY")

lm = dspy.LM(
    "openai/sentiment-analyzer/claude-3-7-sonnet-latest",
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL
)
dspy.configure(lm=lm)

# Define signature with custom instructions
class SentimentAnalysis(dspy.Signature):
    """Classify sentiment of a given sentence."""

    sentiment: Literal["positive", "negative", "neutral"] = dspy.OutputField()
    confidence: float = dspy.OutputField()
    explanation: str = dspy.OutputField()

# Create predictor with templated instructions
classify = dspy.Predict(
    SentimentAnalysis.with_instructions(
        "Analyze the sentiment of the following text: {{text}}. "
        "Provide your reasoning in the explanation field."
    )
)

# Run with input variables
response = classify(
    config={"extra_body": {"input": {"text": "I had a wonderful day at the park!"}}}
)
print(f"Sentiment: {response.sentiment}")
print(f"Confidence: {response.confidence}")
print(f"Explanation: {response.explanation}")
```

## Using structured output

class SentimentAnalysis(dspy.Signature):
    """Classify sentiment of a given sentence."""

    sentiment: Literal["positive", "negative", "neutral"] = dspy.OutputField()
    confidence: float = dspy.OutputField()
    explanation: str = dspy.OutputField()

Just pass a response_format in the dspy.LM to leverage structured generation:
````
lm = dspy.LM(
    "openai/sentiment-analyzer/claude-3-7-sonnet-latest",
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL,
    response_format={
        "type": "json_schema",
        "json_schema": {"name": "SentimentAnalysis", "schema": SentimentAnalysis.model_json_schema()},
    },
)
```


## Using Deployments

A **Deployment** in WorkflowAI binds a specific version of a prompt (schema) to an environment. You can target a deployment by structuring the `model` parameter as:

```
openai / <agent-name> / #<schema_id> / <environment>
```

```python
import os
import dspy
from typing import Literal

# Configure DSPy
WORKFLOWAI_API_URL = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
WORKFLOWAI_API_KEY = os.environ.get("WORKFLOWAI_API_KEY")

# Use a deployed version
lm = dspy.LM(
    "openai/sentiment-analyzer/#3/production",  # ← deployment reference
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL
)
dspy.configure(lm=lm)

class SentimentAnalysis(dspy.Signature):
    """Classify sentiment of a given sentence."""

    sentiment: Literal["positive", "negative", "neutral"] = dspy.OutputField()
    confidence: float = dspy.OutputField()
    explanation: str = dspy.OutputField()

# When using deployments, instructions are managed server-side
classify = dspy.Predict(SentimentAnalysis)

# Run with input variables
response = classify(
    config={"extra_body": {"input": {"text": "The customer service was absolutely terrible!"}}}
)
print(f"Sentiment: {response.sentiment}")
print(f"Confidence: {response.confidence}")
```

## Observing your agent's runs in WorkflowAI

WorkflowAI allows you to view all the runs that were made for your agent:

![Run list](</docs/assets/images/runs/list-runs.png>)

You can also inspect a specific run and review the run:

![Run details](</docs/assets/images/runs/run-view.png>)

### Comparing models side-by-side

In the WorkflowAI's 'Playground', you can run models side-by-side on the same input, to compare model output quality, latency and price:

![Playground](</docs/assets/images/playground-fullscreen.png>)


## Chain of Thought

DSPy's `ChainOfThought` automatically adds reasoning steps before the final answer:

```python
import os
import dspy

# Configure DSPy
WORKFLOWAI_API_URL = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
WORKFLOWAI_API_KEY = os.environ.get("WORKFLOWAI_API_KEY")

lm = dspy.LM(
    "openai/sentiment-analyzer/claude-3-7-sonnet-latest",
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL
)
dspy.configure(lm=lm)

# Create a chain of thought sentiment analyzer
sentiment_cot = dspy.ChainOfThought(
    "text -> sentiment: Literal['positive', 'negative', 'neutral'], confidence: float"
)

# Run analysis with reasoning
result = sentiment_cot(text="The movie had stunning visuals, but the plot was confusing and the ending disappointing.")
print(f"Reasoning: {result.rationale}")
print(f"Sentiment: {result.sentiment}")
print(f"Confidence: {result.confidence}")
```****

## Conclusion

With just a few lines of code, you can:

1. Use DSPy's elegant signature-based approach
2. Pass template variables via `extra_body`
3. Target server-managed prompt deployments
4. Access 100+ models from various providers

—all while maintaining DSPy's clean, declarative API and gaining WorkflowAI's observability and reliability features.

## Talk with us 💌

For any question or feedback, please contact team@workflowai.support or join us on [Discord](https://workflowai.com/discord).

Thank you and happy agent building!
