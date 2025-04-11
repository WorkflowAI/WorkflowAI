# Tools

{% hint style="info" %}
First, read our introduction to [tools](../../concepts/tools.md).
{% endhint %}

Tools allow enhancing an agent's capabilities by allowing it to call external functions. Tools enable the creation of agents that can perform actions, retrieve information, and make decisions based on real-time data.

## Defining custom tools

Custom tools are defined as regular python functions, and can be async or sync.

```python
# Sync tool
def get_current_time(timezone: Annotated[str, "The timezone to get the current time in. e-g Europe/Paris"]) -> str:
    """Return the current time in the given timezone in iso format"""
    return datetime.now(ZoneInfo(timezone)).isoformat()

# Tools can also be async
async def get_latest_pip_version(package_name: Annotated[str, "The name of the pip package to check"]) -> str:
    """Fetch the latest version of a pip package from PyPI"""
    url = f"https://pypi.org/pypi/{package_name}/json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return data['info']['version']
```

To use the tool, add the function to the `tools` list in the `@workflowai.agent` decorator.

{% hint style="warning" %}
It must be possible to determine the schema of a tool from the function signature. This means that
the function must have type annotations and use standard types or `BaseModel` only for now.
{% endhint %}


```python
@workflowai.agent(
    id="research-helper",
    tools=[get_current_time, get_latest_pip_version],
    model=Model.GPT_4O_LATEST,
)
async def answer_question(_: AnswerQuestionInput) -> AnswerQuestionOutput:
    ...
```

If an agent has access to `tools`, and the model
deems that tools are needed for a particular run, the agent will:
- call all tools in parallel
- wait for all tools to complete
- reply to the run with the tool outputs
- continue with the next step of the run, and re-execute tools if needed
- ...
- until either no tool calls are requested, the max iteration (10 by default) or the agent has run to completion

```python
run = await answer_question(
    AnswerQuestionInput(question="What is the current time in Phoenix, AZ?")
)
print(run)

# Output:
# ==================================================
# {
#   "answer": "The current time in Phoenix, Arizona is 2:42 PM MST (Mountain Standard Time) on February 14, 2025.",
#   "sources": []
# }
# ==================================================
# Cost: $ 0.006414
# Latency: 2.64s
```

It's important to understand that there are actually two runs created in a single agent `run` call:
- the first run returns an empty output with a tool call request with a timezone
```
# First run
```
- the second run returns the current time in the given timezone
```
# Second run
```

Only the last run is returned to the caller.

Another example:

```python
run = await answer_question(AnswerQuestionInput(question="What is the latest version of workflowai package?"))
print(run)

# Output:
# ==================================================
# {
#   "answer": "The latest version of the 'workflowai' package is 0.5.5.",
#   "sources": [
#     "PyPI"
#   ]
# }
# ==================================================
# Cost: $ 0.0027
# Latency: 1.38s
```

{% hint style="info" %}
You can **not** directly use the web [Playground](../../features/playground.md) to test custom tools, since the tools execution is done through your code.
{% endhint %}

### Hosted tools

{% hint style="warning" %}
This section is not up to date.
{% endhint %}

WorkflowAI hosts a few tools:

- `@browser-text` allows fetching the content of a web page
- `@google-search` allows performing a web search

Hosted tools tend to be faster because there is no back and forth between the client and the WorkflowAI API. Instead,
if a tool call is needed, the WorkflowAI API will call it within a single request.

A single run will be created for all tool iterations.

To use a tool, simply add it's handles to the instructions (the function docstring):

```python
@workflowai.agent(id="web-search-agent", model=Model.CLAUDE_3_5_HAIKU_LATEST)
async def search_web(input: SearchWebInput) -> SearchWebOutput:
    """
    You can use @google-search and @browser-text when relevant.
    """
    ...
```

```python
run = await search_web(
    SearchWebInput(
        query="When was the last iPhone released?"
    )
)
print(run)

# Output:
```
