# Costs

While most standard LLM APIs return usage metrics (like input and output token counts), they typically don't provide the actual monetary cost of the request. Developers are often left to calculate this themselves, requiring them to maintain and apply up-to-date pricing information for each model.

WorkflowAI simplifies cost tracking by automatically calculating the estimated cost for each LLM request based on the specific model used and WorkflowAI's current pricing data.

## How to track costs

### Using the Playground

...

### Using the Monitor section

On WorkflowAI, you can track costs in the Cost page from the Monitor section:

![Under MONITOR: Cost](/docs/assets/images/monitoring.png)

### Programmatically

TODO:
- adjust the code for this section, the cost and latency are inside the array choices[]
- add WorkflowAI SDK and REST API examples

{% tabs %}

{% tab title="curl" %}
```
....
```
{% endtab %}

{% tab title="OpenAI SDK (Python)" %}
```python
class Answer(BaseModel):
    sentiment: str
    score: float

completion = client.chat.completions.create(
    model="sentiment-analysis-agent/gpt-4o-mini",
    response_model=Answer,
    messages=[{"role": "user", "content": "I love Workflow AI!"}],
)

cost = completion.choices[0].cost_usd
latency = completion.choices[0].duration_seconds
print(f"Latency (s): {latency:.2f}")
print(f"Cost   ($): ${cost:.6f}")
```
{% endtab %}

{% tab title="OpenAI SDK (Ruby)" %}
```ruby
# Ruby implementation here
...
```
{% endtab %}

{% tab title="Instructor (Python)" %}
```python
# Instructor implementation here
...
```
{% endtab %}

{% endtabs %}

#### ...
