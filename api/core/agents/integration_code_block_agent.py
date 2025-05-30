import datetime
import os
from typing import Any, AsyncIterator, NamedTuple

import workflowai
from openai import AsyncOpenAI
from pydantic import BaseModel

from core.domain.documentation_section import DocumentationSection
from core.domain.integration.integration_domain import Integration


class IntegrationCodeSnippetAgentInput(BaseModel):
    agent_id: str
    agent_schema_id: int
    model_used: str
    version_messages: str
    integration: Integration
    integration_documentations: list[DocumentationSection]
    version_deployment_environment: str | None = None
    is_using_instruction_variables: bool
    input_schema: dict[str, Any]
    is_using_structured_generation: bool
    output_schema: dict[str, Any]


class IntegrationCodeAgentResponse(NamedTuple):
    code: str
    feedback_token: str | None


async def integration_code_snippet_agent(
    input: IntegrationCodeSnippetAgentInput,
) -> AsyncIterator[IntegrationCodeAgentResponse]:
    system_message = """You are a world class programmer that specializes in generating working code snippets for integrations with WorkflowAI. Use the documentation that will come below as the only source of truth to generate the code block.

You must return the code snippet wrapped in markdown code blocks with the appropriate language specified. For example:
```python
# Python code
```
or
```typescript
// TypeScript code
```

Do not include any text outside of the code block.

The model used is: {{model_used}}
The agent is named: {{agent_id}}
The model schema id is {{agent_schema_id}}
The user is using {{integration_display_name}}

{% if version_deployment_environment %}
and since the agent is deployed, the model parameters for the completion request must be something like {{agent_id}}/#{{agent_schema_id}}/{{version_deployment_environment}}

Ex: 'model="my-agent/#1/staging" # Your model parameter now points to the WorkflowAI deployment'

also note that the messages can be = [] when using deployments as the messages are already register in the WorkflowAI platform (you must add a comment in the code to explain that).

Ex: 'messages = [] # Your message are already registered in the WorkflowAI platform, you don't need to pass those here.'

So in this cases you do not need to actually define the messages variable at all in the code snippet.
{% else %}
and since the agent is not deployed, the model parameters for the completion request must be something like {{agent_id}}/{{model_used}}
{% endif %}


{% if is_using_instruction_variables %}
Since the agent is using instruction variable:
- the 'messages' must be a templated version of the messages with placeholders to inject the variables surrounded by DOUBLE (do NOT use f-string for Python) curly braces in, matching the structure in {{input_schema}}. Ex {"role": "user", "content": "the user name is {% raw %} {{user_name}} {% endraw %}}"}
- the 'input' must be passed to the completion request with the 'extra_body' key (ex: extra_body: {"input": "..."} for OpenAI Python examples, and "input" for OpenAI TS needs to be passed in the top level of the completion request) AND '// @ts-expect-error input is specific to the WorkflowAI implementation' needs to be added if the code is in TS.
{% else %}
Since the agent is not using instruction variable you must not add any variable in the 'messages' or the 'input'
{% endif %}


{% if is_using_structured_generation %}
Since the agent is using structured generation:
- the code snippet must include class definition for the structured output (using {{structured_output_class}}), matching the structure in {{output_schema}}. For 'enum' in the 'output_schema' you can use 'Literal' or 'enum.Enum ' in Python.
- the 'response_format' (or similar parameter) must be set, to specify the structured output class in the completion request
{% else %}
Since the agent is not using structured generation, the code snippet must not include any class definition for the structured output
{% endif %}

The agent's messages to reuse in the code snippet are:
{{version_messages}}

Integration documentation to base your code snippet on is:
{{integration_documentation_content}}

Do not include any that what is needed to run the agents (for example, do not display how to display the price of a run, etc.)
"""

    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )
    response = await client.chat.completions.create(
        model=f"integration-code-block-agent/{workflowai.Model.CLAUDE_3_7_SONNET_LATEST.value}",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": "Output the code block for the integration."},
        ],
        extra_body={
            "input": {
                "model_used": input.model_used,
                "agent_id": input.agent_id,
                "agent_schema_id": input.agent_schema_id,
                "integration_display_name": input.integration.display_name,
                "version_deployment_environment": input.version_deployment_environment or "",
                "is_using_instruction_variables": input.is_using_instruction_variables,
                "is_using_structured_generation": input.is_using_structured_generation,
                "version_messages": input.version_messages or "",
                "input_schema": input.input_schema if input.is_using_instruction_variables else "",
                "integration_documentation_content": "\n".join(
                    [d.model_dump_json() for d in input.integration_documentations],
                ),
                "output_schema": input.output_schema if input.is_using_structured_generation else "",
                "structured_output_class": input.integration.output_class
                if input.is_using_structured_generation
                else "",
                "current_datetime": datetime.datetime.now().isoformat(),
            },
        },
        stream=True,
        temperature=0.0,
    )

    agg = ""
    feedback_token: str | None = None
    async for chunk in response:
        # We use 'gettatr' because 'feedback_token' does not existing in the 'Choice' object from the OpenAI SDK
        feedback_token: str | None = getattr(chunk.choices[0], "feedback_token", None)

        if chunk.choices[0].delta.content:
            agg += chunk.choices[0].delta.content
            yield IntegrationCodeAgentResponse(code=agg, feedback_token=feedback_token)

    yield IntegrationCodeAgentResponse(code=agg, feedback_token=feedback_token)
