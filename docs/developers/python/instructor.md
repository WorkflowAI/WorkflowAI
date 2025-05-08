# Instructor (Python) + WorkflowAI = 🫶

## Why use WorkflowAI with Instructor?

WorkflowAI integrates seamlessly with your existing [Instructor](https://github.com/instructor-ai/instructor) code. Simply replace the OpenAI base URL with `run.workflowai.com/v1` and use your WorkflowAI API key instead of OpenAI API key. With this simple change, you instantly get:

- **Access to over [100+ models](https://workflowai.com/developers/python/instructor) (and counting)** from OpenAI, Google, Anthropic, Llama, Grok, Mistral, etc. New models are usually added to WorkflowAI just a few hours after their public release.
- **High Reliability with Automatic Fallback** thanks to our multi-provider infrastructure. For example, we fall back on Azure OpenAI when OpenAI is down. If using Claude, we fall back on AWS Bedrock when Anthropic is down. Our [uptime](https://status.workflowai.com/) for the last 5 months is 100%, and the overhead of our API is only 100ms! We are working on smart cross model fallback. (e.g. fallback on Claude 3.7 when GPT-4.1 is down)
- **Guaranteed structured outputs** thanks to our native structured generation provider features (for models supporting structured generation) and thanks to our carefully crafted prompt and automatic retry (for models not supporting structured generation)
- **Unlimited, free observability** visualize all your LLMs [runs](https://docs.workflowai.com/concepts/runs), share runs with your team, [evaluate](https://docs.workflowai.com/features/reviews) runs, add runs to [benchmarks](https://docs.workflowai.com/features/benchmarks) *(note that [templating with input variables](#templating-with-input-variables) is required to run benchmarks)*, [re-run input](https://docs.workflowai.com/features/playground) on different models, etc. 
- **Fix your agents in seconds without deploying code** Optionally, you can use our [deployment](#using-deployments-for-server-managed-instructions) features to enhance & deploy your agent's instruction right from our web-app. Ideal for fixing agent corner cases in production. *Note that [templating with input variables](#templating-with-input-variables) is a required to use deployments.*
- **Zero token price markup** because we negotiate bulk deals with major providers, you will pay exactly the same price as if you were going directly to the provider. And you get a unified, detailed view of your LLM spending (per agent, per day, etc.). Also, no need for a separate key for each provider. You get your WorkflowAI API key and you can access all major providers.
- **Cloud-based or self-hosted** thanks to our [open-source](https://github.com/WorkflowAI/WorkflowAI/blob/main/LICENSE) licensing model
- **We value your privacy** and we are SOC-2 Type 1 certified. We do not train models on your data, nor do the LLM providers we use.

Learn more about all WorkflowAI's features in our [docs](https://docs.workflowai.com/).

## 1-minute integration of WorkflowAI in existing Instructor code

### Instructor Setup (optional)

If not done already, install the required packages:
```bash
pip install instructor openai pydantic
```

### WorkflowAI credentials config

You can obtain your WorkflowAI API key with **$5 of free credits** [here](https://workflowai.com/developers/python/instructor/).

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

## Simple User Info Extraction Example

Here is how to extract user info from a message with WorkflowAI and instructor:

```python
import os

import instructor
from openai import OpenAI
from pydantic import BaseModel


class UserInfo(BaseModel):
    name: str
    age: int


def extract_user_info(user_message: str) -> UserInfo:
    client = instructor.from_openai(
        OpenAI(
            base_url=os.environ["WORKFLOWAI_API_URL"], # OpenAI now uses WorkflowAI's URL and API key
            api_key=os.environ["WORKFLOWAI_API_KEY"], # Get your API key with $5 free credits at workflowai.com/developers/python/instructor
        ),
        mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
    )

    return client.chat.completions.create(
        model="user-info-extraction-agent/gpt-4o-mini-latest",  # Recommendation: use '<agent_name>/<model_name>' format, see why in the next section. 
        response_model=UserInfo,
        messages=[{"role": "user", "content": user_message}],
    )


if __name__ == "__main__":
    user_info = extract_user_info("John Doe is 32 years old.")
    print("Basic example result:", user_info)  # UserInfo(name='John Doe', age=32)
```

We recommend using the `mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS` because this mode leverages structured generation, that 100% guarantees the output object will enforce the requested `response_model`. In case the model used does not support structured generation, we'll use JSON-mode and instruct the model with the schema to enforce, in the system message. Even if the model does not support JSON-mode we'll parse a JSON from the model's raw completion and retry if the model generated a malformed JSON or a JSON that does not enforce the requested JSON schema.

Note that if `mode=...` is omitted, the `TOOLS` mode will be used. Other supported modes include `TOOLS_STRICT`, `JSON` and `JSON_SCHEMA` and you should be able to obtain well-formed object with those modes, but once again `OPENROUTER_STRUCTURED_OUTPUTS` is recommended in order to leverage the native structured generation of providers when available.

### Why use `model=<agent_name>/<model_name>` ?

When specifying the `model` parameter of the `client.chat.completions.create` method, we recommend to use the `<agent_name>/<model_name>` format. For example: 
- `"user-info-extraction-agent/gpt-4o-mini-latest"`

Adding an `<agent_name>` will allow your different agents to be properly organized in your WorkflowAI account, as shown below:

![Agent list](</docs/assets/images/agent-list.png>)


## Access over 100+ models, without any setup.

The WorkflowAI chat completion endpoint allows you to run more than 100 models using the same endpoint schema as OpenAI chat completion, making switching model family completely transparent on your side.

To change the model to use, simply update the `model` string, ex: 

```python
import os

import instructor
from openai import OpenAI
from pydantic import BaseModel


class UserInfo(BaseModel):
    name: str
    age: int

def extract_user_info(user_message: str) -> UserInfo:
    client = instructor.from_openai(
        OpenAI(base_url=os.environ["WORKFLOWAI_API_URL"], api_key=os.environ["WORKFLOWAI_API_KEY"]),
        mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
    )

    return client.chat.completions.create(
        model="user-info-extraction-agent/claude-3-7-sonnet-latest", # Agent now runs Claude 3.7 Sonnet
        response_model=UserInfo,
        messages=[{"role": "user", "content": user_message}],
    )

if __name__ == "__main__":
    user_info = extract_user_info("John Black is 33 years old.")
    print("Basic example result:", user_info)  # UserInfo(name='John Black', age=33)
```

In this case, the agent now runs on Claude 3.7 Sonnet.

The complete list of our supported models is available [here](https://workflowai.com/developers/python/instructor).

## Observing your agent's runs in WorkflowAI

WorkflowAI allows you to view all the runs that were made for your agent:

![Run list](</docs/assets/images/runs/list-runs.png>)

You can also inspect a specific run and review the run:

![Run details](</docs/assets/images/runs/run-view.png>)

### Comparing models side-by-side

In the WorkflowAI's 'Playground', you can run models side-by-side on the same input, in order to compare the model's output quality, latency and price, as shown below:

![Playground](</docs/assets/images/playground-fullscreen.png>)

You can either re-run an input from production, manually define an input, import an input, or generate a synthetic input in the 'Playground' *(synthetic input generation requires [templating with Input Variables](#templating-with-input-variables) below)*

## Async Support

You can run generation asynchronously, the same way as with the normal OpenAI implementation:

```python
import os
import asyncio
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel

class UserInfo(BaseModel):
    name: str
    age: int

async def extract_user_info_async(user_message: str) -> UserInfo:
    client = instructor.from_openai(
        AsyncOpenAI(base_url=os.environ["WORKFLOWAI_API_URL"], api_key=os.environ["WORKFLOWAI_API_KEY"]),
        mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
    )

    return await client.chat.completions.create(
        model="user-info-extraction-agent/claude-3-7-sonnet-latest",
        response_model=UserInfo,
        messages=[{"role": "user", "content": user_message}],
    )
    
if __name__ == "__main__":
    user_info = asyncio.run(extract_user_info_async("John Black is 33 years old."))
    print("Basic example result:", user_info)  # UserInfo(name='John Black', age=33)
```

## Templating with Input Variables

Introducing input variables separates static instructions from dynamic content, making your agents easier to observe, since WorkflowAI logs these input variables separately. Using input variables also allows to use [benchmarks](https://docs.workflowai.com/features/benchmarks) and [deployments](https://docs.workflowai.com/features/deployments).

We'll introduce a new use case to showcase this feature: classifying an email address as 'personal', 'work' or 'unsure'.

You can see in the code snippet below that the instructions now contain {{}} characters to inject variables and input variables are passed separately in `extra_body['input']`.

WorkflowAI's instructions templates support all [Jinja2](https://github.com/pallets/jinja/) features.

```python
import os
from typing import Literal

import instructor
from openai import OpenAI
from pydantic import BaseModel


class EmailAddressClassificationOutput(BaseModel):
    kind: Literal["personal", "work", "unsure"]

def classify_email_address(email_address: str) -> EmailAddressClassificationOutput:
    client = instructor.from_openai(
        OpenAI(
            base_url=os.environ["WORKFLOWAI_API_URL"],
            api_key=os.environ["WORKFLOWAI_API_KEY"],
        ),
        mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
    )

    instructions = """You must classify the email address as:
    - 'personal' (gmail, yahoo, etc.),
    - 'work' (company email address)
    - or 'unsure'.
    The email address is:
    {{email_address}}"""

    return client.chat.completions.create(
        model="email-classifier-agent/gpt-4o-mini",
        response_model=EmailAddressClassificationOutput,
        messages=[{"role": "user", "content": instructions}],
        extra_body={"input": {"email_address": email_address}},
    )

if __name__ == "__main__":
    result = classify_email_address("steve@apple.com")
    print(f"Classification: {result.kind}") # 'work'
```

## Using Deployments for Server-Managed Instructions 

*Note that using templated instructions as explained in the previous [Templating with Input Variables](#templating-with-input-variables) section above is needed in order to use deployments.*

WorkflowAI Deployments let you register your templated instructions, model and temperature in the WorkflowAI UI. You reference the registered deployment in your code by setting the `model` parameter to `<agent_name>/#<schema_id>/<deployment_id>`. Deployment allows you to update an agent in production in seconds without needing to deploy code. This also means that anybody at your company, for example a product manager, can maintain an agent. In 'deployment' mode, you don't need to send `messages`, since WorkflowAI uses the stored instructions, and you simply pass the input variables in `extra_body['input']`.



```python
import os
from typing import Literal

import instructor
from openai import OpenAI
from pydantic import BaseModel


class EmailAddressClassificationOutput(BaseModel):
    kind: Literal["personal", "work", "unsure"]

def classify_email_address_deployment(email_address: str) -> EmailAddressClassificationOutput:
    client = instructor.from_openai(
        OpenAI(
            base_url=os.environ["WORKFLOWAI_API_URL"],
            api_key=os.environ["WORKFLOWAI_API_KEY"],
        ),
        mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
    )

    return client.chat.completions.create(
        model="email-classifier-agent/#1/production",
        response_model=EmailAddressClassificationOutput,
        messages=[],  # No messages needed; instructions come from the deployment
        extra_body={"input": {"email_address": email_address}},
    )

if __name__ == "__main__":
    result = classify_email_address_deployment("john.doe@gmail.com")
    print(f"Deployment classification: {result.kind}") # 'personal'
```

## Streaming

We are currently implementing streaming on our OpenAI compatible chat completion endpoint. We'll update this documentation shortly.

## Talk with us 💌

For any question or feedback, please contact team@workflowai.support or join us on [Discord](https://workflowai.com/discord).

Thank you and happy agent building!

