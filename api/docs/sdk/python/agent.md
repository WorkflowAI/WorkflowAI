# How `@workflowai.agent` works

{% hint style="info" %}
[Star the repository on Github](https://github.com/WorkflowAI/python-sdk) to get notified when new models are added.
{% endhint %}

## Introduction

WorkflowAI takes a different approach to LLMs that simplifies development while providing more structure and reliability.

### Traditional LLM Approach vs. WorkflowAI

Let's compare approaches with a practical example: extracting positive and negative aspects from customer reviews.

#### Traditional Approach
With traditional LLM frameworks, you might create a prompt like this:

```
Based on the following reviews:
{{ reviews }}

Identify what are the positive and negative aspects.
Make sure you return the output in JSON format:
{
    "positive_aspects": [string],
    "negative_aspects": [string]
}
```

This prompt combines several elements:

| Component | Description |
|-----------|-------------|
| Instructions | "Identify what are the positive and negative aspects." |
| Variables | `{{ reviews }}` - Data to be processed |
| Output format | JSON structure with arrays of positive and negative aspects |

Despite explicitly requesting JSON output, there's no guarantee the model will comply. The LLM might return malformed JSON, skip the format entirely, or include incorrect fields—requiring you to write additional validation code.

#### WorkflowAI Approach
The same task in WorkflowAI becomes more structured and type-safe:

```python
class FeedbackInput(BaseModel):
    reviews: list[str]

class FeedbackOutput(BaseModel):
    positive_aspects: list[str]
    negative_aspects: list[str]

@workflowai.agent(id="feedback")
async def feedback(input: FeedbackInput) -> FeedbackOutput:
    """
    Identify what are the positive and negative aspects.
    """
    ...

run = await feedback.run(
    FeedbackInput(reviews=["..."]),
    model=Model.GPT_4O_LATEST
)
```

WorkflowAI guarantees your output will match the defined schema by validating responses and automatically handling invalid data. No more worrying about malformed JSON or writing extensive error handling code.

WorkflowAI generates optimal prompts by combining your Pydantic models, docstring instructions, and any additional context. Benefits include automatic type validation, cleaner code architecture, and consistently reliable outputs.

Let's explore how this works by breaking down the different parts of an agent:
1. [Schema](#schema-input-output) (input, output)
2. [Instructions](#instructions)
3. [Model](#model)

Optionally, an agent can also have tools, which will be explained in the [Tools](/docs/sdk/python/tools.md) section.

## Schema (input, output)

The schema has two structured parts:

| | |
|------|-------------|
| **Input** | Defines the variables that the agent will receive as input |
| **Output** | Defines the variables that the agent will return as output |

The input and output are defined using [Pydantic](https://docs.pydantic.dev/latest/) models.

A very simple example of a schema is the following, where the agent receives a question as input and returns an answer as output.

```python
from pydantic import BaseModel

class Input(BaseModel):
    question: str

class Output(BaseModel):
    answer: str
```

{% hint style="success" %}
Read more about why schemas are a good idea in the [Schemas](../../concepts/schemas.md#why-are-schemas-a-good-idea) section.
{% endhint %}

{% hint style="info" %}
Find more examples of schemas in the [Schemas](/docs/sdk/python/schemas.md) section.
{% endhint %}

### Descriptions

Adding descriptions to the input and output fields is optional, but it's a good practice to do so, as descriptions will be included in the final prompt sent to the LLM, and will help align the agent's behavior.

```python
class Output(BaseModel):
    answer: str = Field(description="Answer with bullet points.")
```

### Examples

Another effective way to align the agent's behavior is to provide examples for **output** fields.

```python
class Output(BaseModel):
    answer: str = Field(
        description="Answer with bullet points.",
        examples=[
            "- Answer 1",
            "- Answer 2", 
            "- Answer 3"
        ]
    )
```

{% hint style="info" %}
There are very little use cases for descriptions and examples in the **input** fields. The LLM will most of the time infer from the value that is passed.
{% endhint %}

### Required versus optional fields

In short, we recommend using default values for most output fields.

Pydantic is by default rather strict on model validation. If there is no default value, the field must be provided.
Although the fact that a field is required is passed to the model, the generation can sometimes omit null or empty values.

## Instructions

Instructions are helpful for the agent to understand the task it needs to perform. Use docstring to add instructions to the agent.

```python
@workflowai.agent(id="answer-question")
async def answer_question(input: Input) -> Output:
    """
    You are an expert in history.
    Answer the question with attention to detail and historical accuracy.
    """
    ...
```

Instructions are automatically passed to the LLM via the system prompt.

```
system_prompt = """<instructions>You are an expert in history. Answer the question with attention to detail and historical accuracy.</instructions>"""
```

### Variables in instructions

You can customize your agent's instructions using [Jinja2](https://jinja.palletsprojects.com/) template variables in the docstring. These variables are automatically filled with values from your input model's fields, giving you precise control over the final prompt.

```python
class Input(BaseModel):
    question: str
    word_count: int

class Output(BaseModel):
    answer: str

@workflowai.agent(id="answer-question-with-word-count", model=Model.CLAUDE_3_5_HAIKU_LATEST)
async def answer_question(input: Input) -> Output:
    """
    The answer should be less than {{ word_count }} words.
    Answer the following question:
    {{ question }}
    """
    ...

# Run the agent
run = await answer_question.run(
    Input(
        question="What is artificial intelligence?",
        word_count=5
    )
)

# View prompt
# https://workflowai.com/docs/agents/answer-question-with-word-count/runs/019509ed-017e-7059-4c25-6137ebdb7dcd
# System prompt:
# <instructions>The answer should be less than 5 words. Answer the following question: What is artificial intelligence?</instructions>
# { "answer": "Smart computer systems learning" }
```

<details>
<summary>Example: Code Review Agent</summary>

{% raw %}
```python
class CodeReviewInput(BaseModel):
    language: str = Field(description="Programming language of the code")
    style_guide: str = Field(description="Style guide to follow")
    is_production: bool = Field(description="Whether this is a production review")
    focus_areas: list[str] = Field(description="Areas to focus on during review", default_factory=list)

class CodeReviewOutput(BaseModel):
    """Output from a code review."""
    issues: list[str] = Field(
        default_factory=list,
        description="List of identified issues or suggestions for improvement"
    )
    compliments: list[str] = Field(
        default_factory=list,
        description="List of positive aspects and good practices found in the code"
    )
    summary: str = Field(
        description="A brief summary of the code review findings"
    )

@workflowai.agent(id="code-review")
async def review_code(review_input: CodeReviewInput) -> CodeReviewOutput:
    """
    You are a code reviewer for {{ language }} code.
    Please review according to the {{ style_guide }} style guide.

    {% if is_production %}
    This is a PRODUCTION review - be extra thorough and strict.
    {% else %}
    This is a development review - focus on maintainability.
    {% endif %}

    {% if focus_areas %}
    Key areas to focus on:
    {% for area in focus_areas %}
    {{ loop.index }}. {{ area }}
    {% endfor %}
    {% endif %}

    Code to review:
    {{ code }}
    """
    ...
```
{% endraw %}

</details>

{% hint style="info" %}
We recommend using CursorAI, Claude or ChatGPT to help generate the Jinja2 template.

The template uses [Jinja2](https://jinja.palletsprojects.com/) syntax and supports common templating features including:

- Variable substitution: {% raw %}`{{ variable }}`{% endraw %}
- Conditionals: {% raw %}`{% if condition %}...{% endif %}`{% endraw %}
- Loops: {% raw %}`{% for item in items %}...{% endfor %}`{% endraw %}
- Loop indices: {% raw %}`{{ loop.index }}`{% endraw %}

See the [Jinja2 documentation](https://jinja.palletsprojects.com/) for the full template syntax and capabilities.
{% endhint %}

### Temperature

The temperature is a parameter that controls the randomness of the output. It is a float between 0 and 1. The default temperature is 0.

```python
run = await answer_question.run(
    Input(question="What is the history of Paris?"),
    temperature=0.5
)
```

## Model

The model is the LLM that will be used to generate the output. WorkflowAI offers a unified interface for all the models it supports from OpenAI, Anthropic, Google, and more. Simply pass the model you want to use to the `model` parameter.

{% hint style="info" %}
The [list of models supported by WorkflowAI is available here](https://github.com/WorkflowAI/python-sdk/blob/main/workflowai/core/domain/model.py), but you can also see the list of models from the playground, for a more user-friendly experience.
{% endhint %}

Set the model in the `@agent` decorator.

```python
import workflowai
from workflowai import Model

@workflowai.agent(id="answer-question", model=Model.GPT_4O_LATEST)
async def answer_question(input: Input) -> Output:
    ...
```

{% hint style="info" %}
When a model is retired or deprecated, WorkflowAI automatically upgrades it to the latest compatible version with equivalent or better pricing. This ensures your agents continue working seamlessly without any code changes needed on your end.
{% endhint %}

### Supported models

When building an agent that uses images, or audio, you need to use a model that supports multimodality. Use the `list_models()` function to get the list of models and check if they support your use case by checking the `is_not_supported_reason` field.

```python
class AudioInput(BaseModel):
    audio: Audio = Field()

class AudioOutput(BaseModel):
    transcription: str = Field()

@agent(id="audio-transcription")
async def audio_transcription(input: AudioInput) -> AudioOutput:
    """
    Transcribe the audio file.
    """
    ...

models = await audio_transcription.list_models()
for model in models:
    if model.is_not_supported_reason is None:
        print(f"{model.id} supports audio transcription")
    else:
        print(f"{model.id} does not support audio transcription: {model.is_not_supported_reason}")

# ...
```

{% hint style="info" %}
The `list_models()` function is a powerful way to programmatically discover which models are compatible with your agent's requirements. This is especially important for multimodal agents that handle images or audio, as not all models support these capabilities. You can use this information to dynamically select the most appropriate model at runtime or to provide fallback options.
{% endhint %}

## Running the agent

{% hint style="warning" %}
Before you run the agent, make sure you have [setup the WorkflowAI client](./get-started.md#api-key).
{% endhint %}

To run the agent, simply call the `run` function with an input.

```python
run = await answer_question.run(Input(question="What is the history of Paris?"))
print(run)

# Output:
# ==================================================
# {
#   "answer": "- Paris, the capital of France, has a history that dates back to ancient times, originally settled by the Parisii, a Celtic tribe, around 250 BC.\n- During the Roman era, it was known as Lutetia and became a significant city in the Roman province of Gaul.\n- In the Middle Ages, Paris grew as a center of learning and culture, with the establishment of the University of Paris in the 12th century.\n- The city played a pivotal role during the French Revolution in the late 18th century, becoming a symbol of revolutionary ideals.\n- In the 19th century, Paris underwent major transformations under Baron Haussmann, who modernized the city's infrastructure and architecture.\n- Paris was occupied during World War II but was liberated in 1944, marking a significant moment in its modern history.\n- Today, Paris is renowned for its cultural heritage, iconic landmarks like the Eiffel Tower and Notre-Dame Cathedral, and its influence in art, fashion, and politics."
# }
# ==================================================
# Cost: $ 0.0027
# Latency: 6.54s
```

When you call `run`, the associated agent will be created on WorkflowAI Cloud (or your self-hosted server) if it does not already exist.

{% hint style="info" %}
The agent id will be a slugified version of the function name unless specified explicitly using the `id` parameter, which is **recommended**.

```python
@workflowai.agent(id="answer-question")
async def answer_question(input: Input) -> Output:
    ...
```
{% endhint %}

### Override the default model

You can also pass a `model` parameter to the agent function itself to specify the model you want to use, and override the default model set in the `@agent` decorator.

```python
run = await answer_question.run(
    Input(question="What is the history of Paris?"),
    model=Model.CLAUDE_3_5_SONNET_LATEST
)
print(run)
```

### Cost, latency

WorkflowAI automatically tracks the cost and latency of each run, and makes it available in the `run` object.

```python
run = await answer_question.run(Input(question="What is the history of Paris?"))
print(f"Cost: $ {run.cost_usd:.5f}")
print(f"Latency: {run.duration_seconds:.2f}s")

# Cost: $ 0.00745
# Latency: 8.99s
```

### Streaming

WorkflowAI also support streaming the output, using the `stream` method. The `stream` method returns an AsyncIterator, so you can use it in an async for loop.

```python
async for chunk in answer_question.stream(Input(question="What is the history of Paris?")):
    print(chunk)

# Output:
# ==================================================
# {
#   "answer": "-"
# }
# ==================================================

# Output:
# ==================================================
# {
#   "answer": "- Founde"
# }
# ==================================================

# Output:
# ==================================================
# {
#   "answer": "- Founded aroun"
# }
# ==================================================

# Output:
# ==================================================
# {
#   "answer": "- Founded around 250"
# }
# ==================================================

# Output:
# ==================================================
# {
#   "answer": "- Founded around 250 BCE"
# }
# ==================================================
# ...
```

{% hint style="info" %}
Even when using streaming, partial outputs are returned as valid output schemas.
{% endhint %}

### View the prompt

To access the exact prompt sent by WorkflowAI to any AI provider, and the raw response as well, you can use `fetch_completions` on a run object. For example:

```python
# Fetch the raw completion from the LLM
run = await answer_question.run(Input(question="What is the history of Paris?"))

# Get completion details
completions = await run.fetch_completions()

for completion in completions:
    completion_json = completion.model_dump_json(indent=2)
    print(completion_json)

# Output:
# {
#   "messages": [
#     {
#       "role": "system",
#       "content": "<instructions>\nYou are an expert in history.\nAnswer the question with attention to detail and historical accuracy.\n</instructions>\n\nInput will be provided in the user message using a JSON following the schema:\n```json\n{\n  \"properties\": {\n    \"question\": {\n      \"type\": \"string\"\n    }\n  },\n  \"required\": [\n    \"question\"\n  ],\n  \"type\": \"object\"\n}\n```"
#     },
#     {
#       "role": "user",
#       "content": "Input is:\n```json\n{\n  \"question\": \"What is the history of Paris?\"\n}\n```"
#     }
#   ],
#   "response": "{\"answer\":\"- Paris, the capital of France, has a history that dates back to ancient times, originally settled by the Parisii, a Celtic tribe, around 250 BC...\"}",
#   "usage": {
#     "completion_token_count": 177,
#     "completion_cost_usd": 0.00177,
#     "reasoning_token_count": 0,
#     "prompt_token_count": 210,
#     "prompt_token_count_cached": 0,
#     "prompt_cost_usd": 0.0005250000000000001,
#     "prompt_audio_token_count": 0,
#     "prompt_audio_duration_seconds": 0.0,
#     "prompt_image_count": 0,
#     "model_context_window_size": 128000
#   }
# }
```

{% hint style="info" %}
The `fetch_completions` method is particularly useful for debugging, understanding token usage, and auditing the exact interactions with the underlying AI models. This can help you optimize prompts, analyze costs, and ensure the model is receiving the expected instructions.
{% endhint %}

### Error handling

Read more about error handling in the [Errors](./errors.md) section.

### Cache

To save money and improve latency, WorkflowAI supports caching.

By default, the cache settings is `auto`, meaning that agent runs are cached when the temperature is 0
(the default temperature value) and no tools are used. Which means that, when running the same agent (without tools) twice with the **exact** same input, the exact same output is returned and the underlying model is not called a second time.

The cache usage string literal is defined in [cache_usage.py](https://github.com/WorkflowAI/workflowai-py/blob/main/workflowai/core/domain/cache_usage.py) file. There are 3 possible values:

- `auto`: (default) Use cached results only when temperature is 0, and no tools are used
- `always`: Always use cached results if available, regardless of model temperature
- `never`: Never use cached results, always execute a new run

```python
# Never use cache
run = agent.run(input, use_cache='never')

# Always use cache
run = agent.run(input, use_cache='always')

# Auto (default): use cache when temperature is 0 and no tools are used
run = agent.run(input)
```

## Reply to a run

For some use-cases (for example, chatbots), you want to reply to a previously created run to maintain conversation history. Use the `reply` method from the `Run` object.

For example, a simple travel chatbot agent can be created as follows:

```python
class ChatbotInput(BaseModel):
    user_message: str

class Recommendation(BaseModel):
    name: str
    address: str

class ChatbotOutput(BaseModel):
    assistant_message: str
    # You can add structured output to the assistant reply
    recommendations: list[Recommendation]

@workflowai.agent(id="travel-assistant", model=Model.GPT_4O_LATEST)
async def chat(input: ChatbotInput) -> ChatbotOutput:
    """
    A helpful travel assistant that can provide recommendations and answer questions about destinations.
    """
    ...

# Initial question from user
run = await chat.run(ChatbotInput(user_message="I'm planning a trip to Paris. What are the must-see attractions?"))

# Output:
# ==================================================
# {
#   "assistant_message": "Paris is a city rich in history, culture, and beauty. Here are some must-see attractions to include in your itinerary.",
#   "recommendations": [
#     {
#       "name": "Eiffel Tower",
#       "address": "Champ de Mars, 5 Avenue Anatole France, 75007 Paris, France"
#     },
#     ...
#   ]
# }
```

When using `run.reply`, WorkflowAI will automatically keep the conversation history.

{% hint style="warning" %}
Note that the output schema of the reply will use the same output schema as the original run.
{% endhint %}

```python
# Note that the follow-up question does not mention Paris because the conversation history is automatically kept.
reply_run = await run.reply(user_message="When is the best time of year to visit?")
print(reply_run)

# Output:
# Note that the output schema include a `recommendations` field, because the output schema of the original run includes a `recommendations` field.
# ==================================================
# {
#   "assistant_message": "The best time to visit Paris is during the spring (April to June) and fall (September to November) seasons. During these months, the weather is generally mild and pleasant, and the city is less crowded compared to the peak summer months. Spring offers blooming flowers and vibrant parks, while fall provides a charming atmosphere with colorful foliage. Additionally, these periods often feature cultural events and festivals, enhancing the overall experience of your visit.",
#   "recommendations": [] 
# }
# ==================================================
# Cost: $ 0.00206
# Latency: 2.08s
```

You can continue to reply to the run as many times as you want.

Another use-case for `run.reply` is to ask a follow-up question, or ask the LLM to double-check its previous answer.

```python
# Double-check the answer
confirmation_run = await run.reply(
    user_message="Are you sure?"
)
```

## Using multiple clients

You might want to avoid using the shared client, for example if you are using multiple API keys or accounts.
It is possible to achieve this by manually creating client instances

```python
from workflowai import WorkflowAI

client = WorkflowAI(
    url=...,
    api_key=...,
)

# Use the client to create and run agents
@client.agent()
def my_agent(agent_input: Input) -> Output:
    ...
```

## Field properties

Pydantic allows a variety of other validation criteria for fields: minimum, maximum, pattern, etc.
This additional criteria are included the JSON Schema that is sent to WorkflowAI, and are sent to the model.

```python
class Input(BaseModel):
    name: str = Field(min_length=3, max_length=10)
    age: int = Field(ge=18, le=100)
    email: str = Field(pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
```

These arguments can be used to stir the model in the right direction. The caveat is have a
validation that is too strict can lead to invalid generations. In case of an invalid generation:

- WorkflowAI retries the inference once by providing the model with the invalid output and the validation error
- if the model still fails to generate a valid output, the run will fail with an `InvalidGenerationError`.
  the partial output is available in the `partial_output` attribute of the `InvalidGenerationError`