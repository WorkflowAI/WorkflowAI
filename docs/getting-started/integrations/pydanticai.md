# PydanticAI

## Setup and identify your agent

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

provider = OpenAIProvider(
    base_url='https://run.workflowai.com/v1',
    api_key='wai-***api-key***' # Get your API key with $5 free credits at workflowai.com/developers/python/pydanticai
)

model = OpenAIModel(
    'agent-id/gpt-4o-mini-latest',
    provider=provider,
)
agent = Agent(
    llm=model,
    system_prompt='You are a helpful assistant that can answer questions and help with tasks.',
...
```

## Structured Outputs

https://ai.pydantic.dev/output/

```python
class User(BaseModel):
    first_name: str
    last_name: str

agent = Agent(  
    model=llm,
    system_prompt='You need to extract the first name and last name from the provided text',
    output_type=User
)

result = agent.run_sync('The text is : {{text}}', model_settings=ModelSettings(extra_body={'input': {'text': 'John Doe'}}))  
print(result.output)
```

## Input Variables

Input variables can be passed via the [model settings](https://ai.pydantic.dev/api/settings/?utm_source=chatgpt.com#pydantic_ai.settings.ModelSettings.extra_body).

```python
result = weather_agent.run_sync(
    'What is the weather like in {{location}}?',
    deps=deps,
    model_settings=ModelSettings(extra_body={'input': {'location': 'London'}})
)
```

## Deployments

I'm not sure we can make deployments work with PydanticAI.



## Observability

TODO: requires OTEL.