from typing import Dict

# =============================================================================
# OPENAI PYTHON SDK TEMPLATES
# =============================================================================

OPENAI_PYTHON_IMPORTS_TEMPLATE = """import openai
import os

"""

OPENAI_PYTHON_CLIENT_SETUP_TEMPLATE = """
# Configure the OpenAI client to use the WorkflowAI endpoint and API key
client = openai.OpenAI(
    api_key=os.environ.get("WORKFLOWAI_API_KEY"),  # Use your WorkflowAI API key
    base_url="{{ base_url }}"
)

"""

OPENAI_PYTHON_TOOLS_DEFINITIONS_TEMPLATE = """
# Define the tools available to the agent
{{ tools_definitions }}

"""

OPENAI_PYTHON_RESPONSE_CALL_TEMPLATE = """
response = client.{{ method }}(
    model="{{ model }}",
{%- if messages %}
    messages={{ messages }},
{%- else %}
    messages=[],  # Your messages are already registered in the WorkflowAI platform, you don't need to pass those here.
{%- endif %}
{%- if response_format %}
    response_format={{ response_format }},
{%- endif %}
{%- if has_tools %}
    {{ tools_parameter }},
{%- endif %}
{%- if extra_body %}
    extra_body={
        "input": {{ extra_body }}
    }
{%- endif %}
)

"""

OPENAI_PYTHON_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
# Access the parsed Pydantic object
parsed_output: {{ class_name }} = response.choices[0].message.parsed
print(parsed_output)
{%- else %}
{%- if has_tools %}
# Check if the model called any tools
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        print(f"Tool called: {tool_call.function.name}")
        print(f"Arguments: {tool_call.function.arguments}")
        # Here you would implement the actual tool execution
        # and provide the result back to the model if needed
else:
    print(response.choices[0].message.content)
{%- else %}
print(response.choices[0].message.content)
{%- endif %}
{%- endif %}

"""

# =============================================================================
# OPENAI TYPESCRIPT SDK TEMPLATES
# =============================================================================

OPENAI_TS_IMPORTS_TEMPLATE = """import OpenAI from 'openai';
{%- if is_structured %}
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from 'zod';
{%- endif %}

"""

OPENAI_TS_CLIENT_SETUP_TEMPLATE = """
// Configure the OpenAI client to use the WorkflowAI endpoint and API key
const client = new OpenAI({
  apiKey: process.env.WORKFLOWAI_API_KEY || 'YOUR_WORKFLOWAI_API_KEY',
  baseURL: 'https://run.workflowai.com/v1',
});

"""

OPENAI_TS_TOOLS_DEFINITIONS_TEMPLATE = """
// Define the tools available to the agent
{{ tools_definitions }}

"""

OPENAI_TS_SCHEMA_TEMPLATE = """
{%- if class_definitions %}
{{ class_definitions }}
{%- else %}
const {{ schema_name }} = z.object({
{%- for field_name, field_info in fields.items() %}
  {{ field_name }}: {{ field_info.type }}{% if field_info.description %}.describe("{{ field_info.description }}"){% endif %},
{%- endfor %}
});
{%- endif %}

"""

OPENAI_TS_RESPONSE_CALL_TEMPLATE = """
const response = await client.{{ method }}({
  model: "{{ model }}",
{%- if messages %}
  messages: {{ messages }},
{%- else %}
  messages: [], // Your messages are already registered in the WorkflowAI platform
{%- endif %}
{%- if response_format %}
  response_format: zodResponseFormat({{ response_format }}, "{{ response_format_name }}"),
{%- endif %}
{%- if has_tools %}
  {{ tools_parameter }},
{%- endif %}
{%- if extra_body %}
  // @ts-expect-error input is specific to the WorkflowAI implementation
  input: {{ extra_body }},
{%- endif %}
});

"""

OPENAI_TS_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
// Access the parsed object
const result: z.infer<typeof {{ schema_name }}Schema> = response.choices[0].message.parsed;
console.log(result);
{%- else %}
{%- if has_tools %}
// Check if the model called any tools
if (response.choices[0].message.tool_calls) {
  for (const toolCall of response.choices[0].message.tool_calls) {
    console.log(`Tool called: ${toolCall.function.name}`);
    console.log(`Arguments: ${toolCall.function.arguments}`);
    // Here you would implement the actual tool execution
    // and provide the result back to the model if needed
  }
} else {
  console.log(response.choices[0].message.content);
}
{%- else %}
console.log(response.choices[0].message.content);
{%- endif %}
{%- endif %}

"""

# =============================================================================
# INSTRUCTOR PYTHON TEMPLATES
# =============================================================================

INSTRUCTOR_IMPORTS_TEMPLATE = """import os
import instructor
from openai import OpenAI

"""

INSTRUCTOR_CLIENT_SETUP_TEMPLATE = """
# Configure the Instructor client with WorkflowAI
client = instructor.from_openai(
    OpenAI(
        base_url=os.environ["WORKFLOWAI_API_URL"],
        api_key=os.environ["WORKFLOWAI_API_KEY"],
    ),
    mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
)

"""

INSTRUCTOR_RESPONSE_CALL_TEMPLATE = """
response = client.chat.completions.create(
    model="{{ model }}",
{%- if messages %}
    messages={{ messages }},
{%- else %}
    messages=[],  # Your messages are already registered in the WorkflowAI platform
{%- endif %}
{%- if response_model %}
    response_model={{ response_model }},
{%- endif %}
{%- if extra_body %}
    extra_body={"input": {{ extra_body }}},
{%- endif %}
)

"""

INSTRUCTOR_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
# The response is already parsed as the Pydantic model
print(response)
{%- else %}
print(response.choices[0].message.content)
{%- endif %}

"""

# =============================================================================
# CURL TEMPLATES
# =============================================================================

CURL_REQUEST_TEMPLATE = """curl -X POST https://run.workflowai.com/v1/chat/completions \\
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{ json_body }}'"""

# =============================================================================
# SHARED TEMPLATES
# =============================================================================

STRUCTURED_OUTPUT_CLASS_TEMPLATE = """
{%- if class_definitions %}
{{ class_definitions }}
{%- else %}
class {{ class_name }}(BaseModel):
{%- for field_name, field_info in fields.items() %}
    {{ field_name }}: {{ field_info.type }}{% if field_info.description %} = Field(description="{{ field_info.description }}"){% endif %}
{%- endfor %}
{%- endif %}

"""


# =============================================================================
# TEMPLATE GETTERS
# =============================================================================


def get_templates_for_integration(integration_kind: str) -> Dict[str, str]:
    """Get all templates for a specific integration"""

    templates = {
        "openai-sdk-python": {
            "imports": OPENAI_PYTHON_IMPORTS_TEMPLATE,
            "client_setup": OPENAI_PYTHON_CLIENT_SETUP_TEMPLATE,
            "tools_definitions": OPENAI_PYTHON_TOOLS_DEFINITIONS_TEMPLATE,
            "response_call": OPENAI_PYTHON_RESPONSE_CALL_TEMPLATE,
            "output_handling": OPENAI_PYTHON_OUTPUT_HANDLING_TEMPLATE,
            "structured_class": STRUCTURED_OUTPUT_CLASS_TEMPLATE,
        },
        "openai-sdk-ts": {
            "imports": OPENAI_TS_IMPORTS_TEMPLATE,
            "client_setup": OPENAI_TS_CLIENT_SETUP_TEMPLATE,
            "tools_definitions": OPENAI_TS_TOOLS_DEFINITIONS_TEMPLATE,
            "response_call": OPENAI_TS_RESPONSE_CALL_TEMPLATE,
            "output_handling": OPENAI_TS_OUTPUT_HANDLING_TEMPLATE,
            "structured_schema": OPENAI_TS_SCHEMA_TEMPLATE,
        },
        "instructor-python": {
            "imports": INSTRUCTOR_IMPORTS_TEMPLATE,
            "client_setup": INSTRUCTOR_CLIENT_SETUP_TEMPLATE,
            "response_call": INSTRUCTOR_RESPONSE_CALL_TEMPLATE,
            "output_handling": INSTRUCTOR_OUTPUT_HANDLING_TEMPLATE,
            "structured_class": STRUCTURED_OUTPUT_CLASS_TEMPLATE,
        },
        "dspy-python": {
            "imports": DSPY_IMPORTS_TEMPLATE,
            "client_setup": DSPY_CLIENT_SETUP_TEMPLATE,
            "tools_definitions": DSPY_TOOLS_DEFINITIONS_TEMPLATE,
            "response_call": DSPY_RESPONSE_CALL_TEMPLATE,
            "output_handling": DSPY_OUTPUT_HANDLING_TEMPLATE,
            "structured_signature": DSPY_SIGNATURE_TEMPLATE,
        },
        "langchain-python": {
            "imports": LANGCHAIN_IMPORTS_TEMPLATE,
            "client_setup": LANGCHAIN_CLIENT_SETUP_TEMPLATE,
            "tools_definitions": LANGCHAIN_TOOLS_DEFINITIONS_TEMPLATE,
            "response_call": LANGCHAIN_RESPONSE_CALL_TEMPLATE,
            "output_handling": LANGCHAIN_OUTPUT_HANDLING_TEMPLATE,
            "structured_class": STRUCTURED_OUTPUT_CLASS_TEMPLATE,
        },
        "litellm-python": {
            "imports": LITELLM_IMPORTS_TEMPLATE,
            "client_setup": LITELLM_CLIENT_SETUP_TEMPLATE,
            "tools_definitions": LITELLM_TOOLS_DEFINITIONS_TEMPLATE,
            "response_call": LITELLM_RESPONSE_CALL_TEMPLATE,
            "output_handling": LITELLM_OUTPUT_HANDLING_TEMPLATE,
            "structured_class": STRUCTURED_OUTPUT_CLASS_TEMPLATE,
        },
        "curl": {
            "request": CURL_REQUEST_TEMPLATE,
        },
    }

    return templates.get(integration_kind, {})


# Legacy functions for backward compatibility
def get_imports_template() -> str:
    return OPENAI_PYTHON_IMPORTS_TEMPLATE


def get_client_setup_template() -> str:
    return OPENAI_PYTHON_CLIENT_SETUP_TEMPLATE


def get_structured_output_class_template() -> str:
    return STRUCTURED_OUTPUT_CLASS_TEMPLATE


def get_response_call_template() -> str:
    return OPENAI_PYTHON_RESPONSE_CALL_TEMPLATE


def get_output_handling_template() -> str:
    return OPENAI_PYTHON_OUTPUT_HANDLING_TEMPLATE


def get_disclaimer_template() -> str:
    return DISCLAIMER_TEMPLATE


# =============================================================================
# DSPY PYTHON TEMPLATES
# =============================================================================

DSPY_IMPORTS_TEMPLATE = """import os
import dspy
{%- if structured_imports %}
from typing import {{ structured_imports }}
{%- endif %}

"""

DSPY_CLIENT_SETUP_TEMPLATE = """
# Configure DSPy to use the WorkflowAI API
WORKFLOWAI_API_URL = os.environ.get("WORKFLOWAI_API_URL", "{{ base_url }}")
WORKFLOWAI_API_KEY = os.environ.get("WORKFLOWAI_API_KEY")

lm = dspy.LM(
    "openai/{{ model }}",
    api_key=WORKFLOWAI_API_KEY,
    api_base=WORKFLOWAI_API_URL{% if response_format %},
    response_format={{ response_format }}{% endif %}
)
dspy.configure(lm=lm)

"""

DSPY_TOOLS_DEFINITIONS_TEMPLATE = """
# Define the tools available to the agent
{{ tools_definitions }}

"""

DSPY_SIGNATURE_TEMPLATE = """
class {{ class_name }}(dspy.Signature):
    \"\"\"{{ signature_description }}\"\"\"
{%- for field_name, field_info in input_fields.items() %}
    {{ field_name }}: {{ field_info.type }} = dspy.InputField()
{%- endfor %}
{%- for field_name, field_info in output_fields.items() %}
    {{ field_name }}: {{ field_info.type }} = dspy.OutputField()
{%- endfor %}

"""

DSPY_RESPONSE_CALL_TEMPLATE = """
predict = dspy.Predict({{ class_name }})
result = predict(
{%- for field_name, value in input_example.items() %}
    {{ field_name }}={{ value }}{% if not loop.last %},{% endif %}
{%- endfor %}
)

"""

DSPY_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
# Access the structured output
{%- for field_name, field_info in output_fields.items() %}
print(f"{{ field_name.title() }}: {result.{{ field_name }}}")
{%- endfor %}
{%- else %}
print(result)
{%- endif %}

"""

# =============================================================================
# LANGCHAIN PYTHON TEMPLATES
# =============================================================================

LANGCHAIN_IMPORTS_TEMPLATE = """import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import SecretStr

"""

LANGCHAIN_CLIENT_SETUP_TEMPLATE = """
# Configure LangChain to use WorkflowAI
WORKFLOWAI_API_URL = os.environ.get("WORKFLOWAI_API_URL", "{{ base_url }}")
WORKFLOWAI_API_KEY = os.environ.get("WORKFLOWAI_API_KEY")

llm = ChatOpenAI(
    base_url=WORKFLOWAI_API_URL,
    api_key=SecretStr(WORKFLOWAI_API_KEY),
    model="{{ model }}",
){% if is_structured %}.with_structured_output({{ class_name }}){% endif %}

"""

LANGCHAIN_TOOLS_DEFINITIONS_TEMPLATE = """
# Define the tools available to the agent
{{ tools_definitions }}

"""

LANGCHAIN_RESPONSE_CALL_TEMPLATE = """
{%- if messages %}
messages = {{ messages }}
{%- else %}
messages = []  # Messages are managed server-side in the deployment
{%- endif %}

{%- if has_tools %}
# Bind tools to the LLM
llm_with_tools = llm.bind_tools(tools)
result = llm_with_tools.invoke(
    messages{% if extra_body %},
    extra_body={"input": {{ extra_body }}}{% endif %}
)
{%- else %}
{%- if extra_body %}
result = llm.invoke(
    messages,
    extra_body={"input": {{ extra_body }}},
)
{%- else %}
result = llm.invoke(messages)
{%- endif %}
{%- endif %}

"""

LANGCHAIN_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
# The result is already parsed as the Pydantic model
print(result)
{%- else %}
{%- if has_tools %}
# Check if the model called any tools
if hasattr(result, 'tool_calls') and result.tool_calls:
    for tool_call in result.tool_calls:
        print(f"Tool called: {tool_call['name']}")
        print(f"Arguments: {tool_call['args']}")
        # Here you would implement the actual tool execution
        # and provide the result back to the model if needed
else:
    print(result.content)
{%- else %}
print(result.content)
{%- endif %}
{%- endif %}

"""

# =============================================================================
# LITELLM PYTHON TEMPLATES
# =============================================================================

LITELLM_IMPORTS_TEMPLATE = """import os
import litellm

"""

LITELLM_CLIENT_SETUP_TEMPLATE = """
# Configure LiteLLM to use WorkflowAI
litellm.api_base = os.environ.get("WORKFLOWAI_API_URL", "{{ base_url }}")
litellm.api_key = os.environ.get("WORKFLOWAI_API_KEY")
{%- if is_structured and not has_tools %}
# Enable automatic JSON schema validation only when tools are not used
litellm.enable_json_schema_validation = True
{%- endif %}

"""

LITELLM_TOOLS_DEFINITIONS_TEMPLATE = """
# Define the tools available to the agent
{{ tools_definitions }}

"""

LITELLM_RESPONSE_CALL_TEMPLATE = """
response = litellm.completion(  # type: ignore
    model="openai/{{ model }}",
{%- if messages %}
    messages={{ messages }},
{%- else %}
    messages=[],  # Messages are managed server-side in the deployment
{%- endif %}
{%- if response_format %}
    response_format={{ response_format }},
{%- endif %}
{%- if has_tools %}
    {{ tools_parameter }},
{%- endif %}
{%- if extra_body %}
    extra_body={"input": {{ extra_body }}},
{%- endif %}
)

"""

LITELLM_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
{%- if has_tools %}
# Check if the model called any tools first
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        print(f"Tool called: {tool_call.function.name}")
        print(f"Arguments: {tool_call.function.arguments}")
        # Here you would implement the actual tool execution
        # and provide the result back to the model if needed
# Parse the structured response if content is available
elif response.choices[0].message.content:
    result = {{ class_name }}.model_validate_json(response.choices[0].message.content)
    print(result)
else:
    print("No content or tool calls in response")
{%- else %}
# Parse the structured response
if response.choices[0].message.content:
    result = {{ class_name }}.model_validate_json(response.choices[0].message.content)
    print(result)
else:
    print("No content in response")
{%- endif %}
{%- else %}
{%- if has_tools %}
# Check if the model called any tools
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        print(f"Tool called: {tool_call.function.name}")
        print(f"Arguments: {tool_call.function.arguments}")
        # Here you would implement the actual tool execution
        # and provide the result back to the model if needed
else:
    print(response.choices[0].message.content)
{%- else %}
print(response.choices[0].message.content)
{%- endif %}
{%- endif %}

"""

# Define DISCLAIMER_TEMPLATE to fix linter error
DISCLAIMER_TEMPLATE = ""
