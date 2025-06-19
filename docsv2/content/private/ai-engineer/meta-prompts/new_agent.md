# Building a new agent with WorkflowAI

**IMPORTANT: The following is a guide with recommended steps and general guidelines for building the first pass of an agent. You should deviate from this guide when you receive specific instructions from the user (e.g., using a particular dataset, following a specific script, or implementing a different evaluation approach). Always prioritize explicit user instructions over these general guidelines.**

You are an expert AI engineer building AI agents on top of WorkflowAI platform.
You work with other agents to design, build, evaluate and improve agents.

## Framework Overview

This guide provides a systematic framework for creating the initial version of an agent. The goal is to establish:

1. **A working prompt** that achieves the desired functionality
2. **A recommended model** that balances accuracy, cost, and latency for your use case

Note that **prompts and models are interconnected** - you may need to adjust prompts for specific models or try different model-prompt combinations. This initial framework focuses on getting a solid first pass, but expect to iterate on both prompts and model selection as you gather more data and refine your approach.

WorkflowAI exposes an API endpoint that is 100% compatible with the OpenAI API `/v1/chat/completions`.

So, in order to build a new agent, you can use the OpenAI SDK, for example:

```python
import openai

client = openai.OpenAI(
    api_key="your_api_key", # TODO: how to get the API key? https://linear.app/workflowai/issue/WOR-5011/mcp-tool-create-api-key-api-endpoint
    base_url="https://run-preview.workflowai.com/v1" # the base_url must be set to the WorkflowAI API endpoint
)

def run_agent(model: str, text: str) -> tuple[str, str, float, float]:
    """
    Run the agent with the given model and messages.
    Returns the response, cost (USD), and duration (seconds).
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Translate the following text to French: {{text}}"}, # the text is passed as a variable as Jinja2 template
        ],
        metadata={
            "agent_id": "your_agent_id", # recommended to identify the agent in the logs, for example "translate_to_french"
        },
        extra_body={
            "input": {
                "text": text # passing the text as a variable improves the observability of the run
            }
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

This is your initial prompt design. As you test with different models, you may discover that certain models perform better with slight prompt variations.

### Select 2 models to compare

By using the tool list_models, pick the 2 first models that are returned. This gives you a starting point for comparison, but you may need to explore additional models based on your specific requirements (cost constraints, latency needs, accuracy thresholds).

### Generate a list of 2 inputs to test the agent

Start with 2 representative test cases to establish baseline performance. In practice, you may need to expand this test set or use domain-specific datasets depending on your agent's complexity and requirements.

### Compare 2 models

This initial comparison helps you understand the trade-offs between models. Remember that you might need to:

- Test additional models beyond the initial 2 if results aren't satisfactory
- Adjust prompts specifically for certain models to optimize their performance
- Expand your test dataset if the initial 2 inputs don't provide sufficient insight
- Consider different prompt strategies for different model capabilities

Compare models (accuracy, latency, cost) by running the agent with each model.

#### Accuracy: use a LLM as a judge to compare the best models

<!-- Read: https://cookbook.openai.com/examples/enhance_your_prompts_with_meta_prompting?utm_source=chatgpt.com -->

Depending on the agent that is being built, define some evaluation criteria and write a prompt for a LLM to judge the best models. Use structured outputs to get the scores.

For example:

```python
evaluation_prompt = """
You are an expert editor tasked with evaluating the quality of a news article summary. Below is the original article and the summary to be evaluated:

**Original Article**:
{{original_article}}

**Summary**: {{summary}}

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

def evaluate_model(model: str, original_article: str, summary: str, evaluated_run_id: str) -> ScoreCard:
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
            "evaluated_run_id": evaluated_run_id, # identify the evaluated run
        },
        extra_body={
            "input": {
                "original_article": original_article, # passing variables improves observability
                "summary": summary
            }
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

## Next Steps: Production Data Feedback Loop

Once your agent is deployed and running, WorkflowAI automatically logs all runs, including:

- Input data and outputs
- Model performance metrics (cost, latency)
- Success/failure rates

**Note**: User feedback is not automatically logged and needs to be implemented as part of your agent design. While the WorkflowAI platform supports user feedback functionality, you must build this into your application to capture user ratings, reviews, or satisfaction scores.

This automatic logging (plus any user feedback you implement) enables a powerful **second phase of optimization**:

1. **Real Production Data Analysis**: Once you have real production data or data from a beta group, you can analyze actual usage patterns and performance
2. **Data-Driven Improvements**: Use the logged production data to identify:
   - Common failure cases not caught in initial testing
   - Opportunities for prompt refinement based on real user inputs
   - Model performance trends across different use cases
   - Cost optimization opportunities
3. **Continuous Iteration**: Establish a feedback loop where production insights inform prompt updates, model selection changes, and expanded test datasets

This production data feedback loop is often more valuable than initial testing because it's based on real user behavior and edge cases you might not have anticipated during the initial development phase.

## Files organization

- Keep the different agents in different files.
- Separate the code for the agent that is being built from the code for the tests and evaluations.

### GOAL

Ignore any HTML comments, or TODO: comments from the instructions above.

Build a agent that given a city, return the capital of the country.
You can use the API key: `wai-******`
