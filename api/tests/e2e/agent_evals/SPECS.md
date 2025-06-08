# WorkflowAI Agent Evaluation Framework Specifications

## Overview

This folder provides end-to-end evaluation capabilities for WorkflowAI agents using a combination of deterministic checks and an "LLM as judge" approach. The framework is designed to evaluate agent responses against complex, open-ended criteria that would be difficult to verify with traditional unit tests.

## Core Components

### LLM as Judge System (`judge_agent.py`)

The heart of the evaluation framework is the LLM-powered judge that evaluates agent outputs against specified assertions.

#### Key Functions:

- **`judge_answer(answer_to_judge: str, assertions: List[str]) -> ChatAnswerJudgmentResponse`**
  - Takes an answer and a list of assertions to verify
  - Uses a dedicated judge agent (`chat-answer-judge-agent/gemini-2.0-flash-001`) via the WorkflowAI proxy
  - Returns structured judgments for each assertion including:
    - The assertion itself (repeated exactly)
    - A reason for the judgment
    - Verbatims from the answer that support the judgment
    - Boolean indicating if the assertion is enforced

- **`fuzzy_contains(verbatim: str, text: str, threshold: float = 0.8) -> bool`**
  - Performs fuzzy string matching to verify that verbatims extracted by the judge actually exist in the original answer
  - Normalizes text by removing punctuation, converting to lowercase, and standardizing whitespace
  - Uses sequence matching with a configurable threshold (default 0.8)
  - Handles edge cases like empty strings and None values

- **`check_assertions_llm_as_judge()`**
  - Orchestrates the complete evaluation process
  - Calls the judge agent
  - Validates that all assertions were evaluated
  - Verifies verbatims exist in the answer using fuzzy matching
  - Optionally registers the review results in WorkflowAI
  - Raises assertion errors if any checks fail

### Evaluation Interface (`workflowai_eval.py`)

Provides a unified interface for evaluating different types of agent outputs using `judge_answer(...)`

#### `workflowai_eval()` Function:
- Accepts multiple output types:
  - `workflowai.Run` - SDK run objects (Extracts agent IDs and run IDs automatically)
  - `ParsedChatCompletion` - OpenAI proxy structured outputs (Extracts agent IDs and run IDs automatically)
  - `ChatCompletion` - Standard OpenAI completions
  - `BaseModel` - Pydantic models
  - `dict` - Raw dictionaries
  - `str` - Plain strings

Please note that `workflowai_eval()` experimentally adds an AI review to the run when the function is run.
See "Integration with existing eval / benchmarking features" below for possible next steps.

#### Usage Pattern

```python
# 1. Make an agent call
response = agent_call(...)

# 2. Define assertions
assertions = [
    "The response should mention X",
    "The code example must include Y",
    "The answer must not contain Z"
]

# 3. Evaluate
await workflowai_eval(response, assertions)
```

### Playground Agent E2E Test (`playground_agent_e2e_test.py`)

Tests the "playground agent" (PA) - a meta-agent that guides users through the WorkflowAI platform.

#### 1st Scenario Flow:

1. **Initial Setup**
   - Creates a unique agent via proxy (e.g., `e2e-test-sentiment-analyzer-{hash}`)
   - Makes first run with `gpt-4o-mini-latest`

2. **First PA Interaction**
   - PA greets the user
   - On polling, PA suggests trying different models
   - Validates that PA:
     - Explains model switching capabilities
     - Proposes at least 2 models
     - Provides exact model strings to copy

3. **Second Model Run**
   - User runs with `gemini-2.0-flash-001`
   - PA suggests adding input variables
   - Validates PA provides:
     - Updated messages with `{{variables}}`
     - Code showing `extra_body` usage
     - No structured outputs yet

4. **Input Variables Run**
   - User implements input variables
   - PA suggests structured outputs
   - Validates PA provides:
     - Pydantic model example
     - `response_format` usage
     - `client.beta.chat.completions.parse` method
     - Still shows input variables usage

5. **Structured Output Run**
   - User implements structured outputs
   - PA suggests deployment
   - Validates deployment guidance

6. **Deployment**
   - User deploys to production
   - PA confirms deployment status
   - Validates PA mentions:
     - Successful deployment
     - Environment name
     - Model name

### Demo Test Suite (`workflowai_eval_demo_test.py`)

Demonstrates framework usage with a meeting summarization agent using `workflowai_eval()`.

#### Shows Two Approaches:
1. **Proxy Testing** - Using OpenAI client with WorkflowAI proxy
2. **SDK Testing** - Using WorkflowAI Python SDK

## Configuration

- Judge model: `chat-answer-judge-agent/gemini-2.0-flash-001`
- Fuzzy match threshold: 0.8 (configurable)
- Required environment variables in `consts.py`:
  - `TENANT`
  - `WORKFLOWAI_API_KEY`
  - `WORKFLOWAI_API_URL`
  - `WORKFLOWAI_USER_TOKEN`

# Possible Next Steps

Next steps mainly depend on two questions:
- A) How far do we want to push the evaluation of the playground agent?
- B) Do we want to invest more in `workflowai_eval()` to possibly integrate the function into the WorkflowAI product? If yes, how will this function integrate with the existing platform?

## A: Test additional use cases for the playground agent
- Debug failing runs (structured gen, etc.)
- Suggest models based on user's goals (correctness, price, etc.)
- Enhance version messages
- Enhance schema
- etc.

## B: Enhance `workflowai_eval()`

### Start with docs
Document how to evaluate these agents, step by step:
- A chat agent
- A categorization agent (which the user possibly has a 'training set' for)

### Add deterministic check capabilities in the assertions of the `workflowai_eval()`:
- answer must contain 'x'
- answer must not contain 'x'
- field 'x' (array) must have 6 elements
- regex patterns
- etc.

Note that any deterministic assertions can be handled by an LLM too, even if less safe and more costly.

### Add evaluated agent input as context for the LLM as judge

- Add the ability to include input messages/prompts in the evaluation context
- Allow the judge to consider the original query when evaluating responses

Not super critical since in the context of E2E tests, we write assertions manually, so any relevant info from the input can be added manually.

### Pytest Plugin Development
Create a pytest plugin to better integrate `workflowai_eval()` with the testing framework.

### Synchronous API Support
In case we want `workflowai_eval()` to become an SDK function, we'll need to support synchronous calling, since many developers do not use asynchronous processing in Python.

### Directly fetch output from run id
Instead of having to pass the run output into the `workflowai_eval()` function, allow fetching outputs directly by run ID.

### Integration with existing eval / benchmarking features
Design how the `workflowai_eval()` function integrates with current eval 2.0 and benchmarking features of WorkflowAI Cloud.

We could build upon the current experimental feature that adds an AI eval to the run when `workflowai_eval()` is run.

By using MCP (Model Context Protocol), Cursor could use a possible WorkflowAI MCP server to trigger various actions (benchmark agent, deploy new models, fetch failures from run DB, etc.).


These improvements would make the framework more robust, user-friendly, and suitable for production-grade agent evaluation at scale.

## Humanloop-Inspired Enhancements

Based on industry best practices from [Humanloop's LLM evaluation platform](https://humanloop.com/), here are additional features that could significantly enhance our evaluation framework:
