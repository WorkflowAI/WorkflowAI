# Building a new agent with WorkflowAI

The following is a guide with recommended steps. But you can deviate from this guide depending on the requirements, or instructions from the user.

WorkflowAI exposes an API endpoint that is compatible with the OpenAI API.
So, in order to build a new agent, you can use:

```python
import openai

client = openai.OpenAI(api_key="your_api_key", base_url="https://run-preview.workflowai.com/v1")

messages = [
    {"role": "system", "content": "Translate the following text to French: {text}"},
]

def run_agent(model: str, messages: list[dict[str, str]]) -> tuple[str, str, float, float]:
    """
    Run the agent with the given model and messages.
    Returns the response, cost (USD), and duration (seconds).
    """
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        extra_body={
            "agent_id": "your_agent_id", # recommended to identify the agent in the logs
        }
    )

    return (
        response.id, # identify the run in the logs
        response.choices[0].message.content,
        response.choices[0].cost_usd, # calculated by WorkflowAI
        response.choices[0].duration_seconds # calculated by WorkflowAI
    )
```

## Steps

### Define the goal of the agent

### Write a prompt for the agent

### Select 2 models to compare

By using the tool list_models, pick the 2 first models that are returned.

### Generate a list of 2 inputs to test the agent

### Compare 2 models

Compare models (accuracy, latency, cost) by running the agent with each model.

#### Accuracy: use a LLM as a judge to compare the best models

<!-- Read: https://cookbook.openai.com/examples/enhance_your_prompts_with_meta_prompting?utm_source=chatgpt.com -->

Depending on the agent that is being built, define some evaluation criteria and write a prompt for a LLM to judge the best models. Use structured outputs to get the scores.

For example:

```python
evaluation_prompt = """
You are an expert editor tasked with evaluating the quality of a news article summary. Below is the original article and the summary to be evaluated:

**Original Article**:
{original_article}

**Summary**: {summary}

Please evaluate the summary based on the following criteria, using a scale of 1 to 5 (1 being the lowest and 5 being the highest). Be critical in your evaluation and only give high scores for exceptional summaries:

1. **Categorization and Context**: Does the summary clearly identify the type or category of news (e.g., Politics, Technology, Sports) and provide appropriate context?
2. **Keyword and Tag Extraction**: Does the summary include relevant keywords or tags that accurately capture the main topics and themes of the article?
3. **Sentiment Analysis**: Does the summary accurately identify the overall sentiment of the article and provide a clear, well-supported explanation for this sentiment?
4. **Clarity and Structure**: Is the summary clear, well-organized, and structured in a way that makes it easy to understand the main points?
5. **Detail and Completeness**: Does the summary provide a detailed account that includes all necessary components (type of news, tags, sentiment) comprehensively?


Provide your scores and justifications for each criterion, ensuring a rigorous and detailed evaluation.
"""

class ScoreCard(BaseModel):
    justification: str
    categorization: int
    keyword_extraction: int
    sentiment_analysis: int
    clarity_structure: int
    detail_completeness: int

def evaluate_model(model: str, messages: list[dict[str, str]]) -> ScoreCard:
    """
    Evaluate the model's performance using the evaluation prompt.
    """
    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": evaluation_prompt},
        ],
        response_format=ScoreCard,
        metadata={
            "agent_id": "your_agent_id:judge", # recommended to identify the agent in the logs
            "evaluated_run_id": "run_id", # identify the evaluated run
        }
    )

    return response.choices[0].message.parsed
```

The model used in the LLM evaluation should be "gpt-4o-mini-latest". <!-- TODO: update the model used in LLM evals -->

## Generate a report

Based on the results, generate a report comparing the different models and their results on accuracy, latency, and cost.
Identify the cheapest model, the fastest model, and the most accurate model.

Costs should be displayed in USD, per 1000 runs.
Average latency and P90 latency should be displayed in seconds.

When useful for the user reading the report, add a section comparing the different models side-by-side, with one row per input.

Save the report in a markdown file.

## Files organization

- Keep the different agents in different files.
  Separate the code for the agent that is being built from the code for the tests and evaluations.

### GOAL

Ignore any HTML comments from the instructions above.

Build a agent that given a city, return the capital of the country.
You can use the API key: `wai-******`
