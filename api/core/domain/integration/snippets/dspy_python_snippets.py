DSPY_PYTHON_LANDING_PAGE_SNIPPET = """```python
import os

import dspy

# Configure DSPy to use the WorkflowAI API
WORKFLOWAI_API_URL = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
WORKFLOWAI_API_KEY = os.environ.get("WORKFLOWAI_API_KEY")  # Use your WorkflowAI API key

lm = dspy.LM(
    "openai/my-assistant/gpt-4o-mini-latest",  # Any model supported by WorkflowAI
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL
)
dspy.configure(lm=lm)

# Define a simple signature
class BasicQA(dspy.Signature):
    \"\"\"Answer a question with a helpful response.\"\"\"

    question: str = dspy.InputField()
    answer: str = dspy.OutputField()

# Create predictor
qa = dspy.Predict(BasicQA)

# Run prediction
response = qa(question="Hello, how are you?")
print(response.answer)
```"""


DSPY_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET = """```python
import os
from typing import Literal

import dspy

# Configure DSPy to use the WorkflowAI API
WORKFLOWAI_API_URL = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
WORKFLOWAI_API_KEY = os.environ.get("WORKFLOWAI_API_KEY")

lm = dspy.LM(
    "openai/sentiment-analyzer/gpt-4o-mini-latest",
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL
)
dspy.configure(lm=lm)

# Define the signature for structured output
class SentimentAnalysis(dspy.Signature):
    \"\"\"Classify sentiment of a given sentence.\"\"\"

    sentence: str = dspy.InputField()
    sentiment: Literal["positive", "negative", "neutral"] = dspy.OutputField()
    confidence: float = dspy.OutputField()

# Create predictor
classify = dspy.Predict(SentimentAnalysis)

# Run analysis with structured output
response = classify(
    sentence="I had a wonderful day at the park!",
    config={"extra_body": {"input": {"text": "I had a wonderful day at the park!"}}}
)
print(f"Sentiment: {response.sentiment}")
print(f"Confidence: {response.confidence}")
```"""


DSPY_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET = """```python
import dspy

# After (WorkflowAI Proxy)
lm = dspy.LM(
    "openai/gpt-4o-mini-latest",
    api_key=<WORKFLOWAI_API_KEY_PLACEHOLDER>,
    api_base="https://run.workflowai.com/v1"  # DSPy now uses WorkflowAI's OpenAI-compatible endpoint
)
dspy.configure(lm=lm)
```"""


DSPY_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET = """```python
lm = dspy.LM(
    "openai/<PROPOSED_AGENT_NAME_PLACEHOLDER>",
    ...
)
```"""
