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
    api_key=os.environ.get("WORKFLOWAI_API_KEY"),  # workflowai.com/keys
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
    response_format={{ response_format }},  # pass the structured output format to enforce
{%- endif %}
{%- if has_tools %}
    {{ tools_parameter }},
{%- endif %}
{%- if has_input_variables %}
    extra_body={
        "input": {{ extra_body }}
    },
{%- endif %}
)

"""

OPENAI_PYTHON_STREAMING_RESPONSE_CALL_TEMPLATE = """
{%- if is_structured %}
response = client.beta.chat.completions.stream(
{%- else %}
response = client.{{ method }}(
{%- endif %}
    model="{{ model }}",
{%- if messages %}
    messages={{ messages }},
{%- else %}
    messages=[],  # Your messages are already registered in the WorkflowAI platform, you don't need to pass those here.
{%- endif %}
{%- if response_format %}
    response_format={{ response_format }},  # pass the structured output format to enforce
{%- endif %}
{%- if has_tools %}
    {{ tools_parameter }},
{%- endif %}
{%- if has_input_variables %}
    extra_body={
        "input": {{ extra_body }}
    },
{%- endif %}
{%- if not is_structured %}
    stream=True,
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

OPENAI_PYTHON_STREAMING_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
# Handle streaming structured output
with response as stream:
    for event in stream:
        if parsed := event.model_dump().get("parsed"):
            print(parsed)
{%- else %}
{%- if has_tools %}
# Handle streaming with potential tool calls
for chunk in response:
    if chunk.choices[0].delta.tool_calls:
        # Tool calls in streaming mode
        for tool_call in chunk.choices[0].delta.tool_calls:
            if tool_call.function.name:
                print(f"Tool called: {tool_call.function.name}")
            if tool_call.function.arguments:
                print(f"Arguments: {tool_call.function.arguments}")
    elif chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
{%- else %}
# Handle streaming text output
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add newline at the end
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
  apiKey: process.env.WORKFLOWAI_API_KEY // workflowai.com/keys
  baseURL: '{{ base_url }}',
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
  response_format: zodResponseFormat({{ response_format }}, "{{ response_format_name }}"), // pass the structured output format to enforce
{%- endif %}
{%- if has_tools %}
  {{ tools_parameter }},
{%- endif %}
{%- if has_input_variables %}
  // @ts-expect-error input is specific to the WorkflowAI implementation
  input: {{ extra_body }},
{%- endif %}
});

"""

OPENAI_TS_STREAMING_RESPONSE_CALL_TEMPLATE = """
const response = await client.{{ method }}({
  model: "{{ model }}",
{%- if messages %}
  messages: {{ messages }},
{%- else %}
  messages: [], // Your messages are already registered in the WorkflowAI platform
{%- endif %}
{%- if response_format %}
  response_format: zodResponseFormat({{ response_format }}, "{{ response_format_name }}"), // pass the structured output format to enforce
{%- endif %}
{%- if has_tools %}
  {{ tools_parameter }},
{%- endif %}
{%- if has_input_variables %}
  // @ts-expect-error input is specific to the WorkflowAI implementation
  input: {{ extra_body }},
{%- endif %}
  stream: true,
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

OPENAI_TS_STREAMING_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
// Handle streaming structured output
for await (const chunk of response) {
  if (chunk.choices[0]?.delta?.parsed) {
    // Partial structured output - you can accumulate or process incrementally
    console.log("Partial result:", chunk.choices[0].delta.parsed);
  } else if (chunk.choices[0]?.finish_reason === "stop") {
    // Final structured output
    if (chunk.choices[0]?.message?.parsed) {
      const finalResult: z.infer<typeof {{ schema_name }}Schema> = chunk.choices[0].message.parsed;
      console.log("Final result:", finalResult);
    }
  }
}
{%- else %}
{%- if has_tools %}
// Handle streaming with potential tool calls
for await (const chunk of response) {
  if (chunk.choices[0]?.delta?.tool_calls) {
    // Tool calls in streaming mode
    for (const toolCall of chunk.choices[0].delta.tool_calls) {
      if (toolCall.function?.name) {
        console.log(`Tool called: ${toolCall.function.name}`);
      }
      if (toolCall.function?.arguments) {
        console.log(`Arguments: ${toolCall.function.arguments}`);
      }
    }
  } else if (chunk.choices[0]?.delta?.content) {
    process.stdout.write(chunk.choices[0].delta.content);
  }
}
console.log(); // Add newline at the end
{%- else %}
// Handle streaming text output
for await (const chunk of response) {
  if (chunk.choices[0]?.delta?.content) {
    process.stdout.write(chunk.choices[0].delta.content);
  }
}
console.log(); // Add newline at the end
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
        base_url="{{ base_url }}",
        api_key=os.environ["WORKFLOWAI_API_KEY"],  # workflowai.com/keys
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
    response_model={{ response_model }},  # pass the structured output format to enforce
{%- endif %}
{%- if has_input_variables %}
    extra_body={"input": {{ extra_body }}},
{%- endif %}
)

"""

INSTRUCTOR_STREAMING_RESPONSE_CALL_TEMPLATE = """
response = client.chat.completions.create(
    model="{{ model }}",
{%- if messages %}
    messages={{ messages }},
{%- else %}
    messages=[],  # Your messages are already registered in the WorkflowAI platform
{%- endif %}
{%- if response_model %}
    response_model={{ response_model }},  # pass the structured output format to enforce
{%- endif %}
{%- if has_input_variables %}
    extra_body={"input": {{ extra_body }}},
{%- endif %}
    stream=True,
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

INSTRUCTOR_STREAMING_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
# Handle streaming structured output with Instructor
for partial_response in response:
    # Instructor provides partial objects during streaming
    print(f"Partial result: {partial_response}")
{%- else %}
# Handle streaming text output
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add newline at the end
{%- endif %}

"""

# =============================================================================
# CURL TEMPLATES
# =============================================================================

CURL_REQUEST_TEMPLATE = """curl -X POST {{ base_url }}/chat/completions \\
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d @- << 'EOF'
{{ json_body }}
EOF"""

CURL_STREAMING_REQUEST_TEMPLATE = """curl -X POST {{ base_url }}/chat/completions \\
  -H "Authorization: Bearer $WORKFLOWAI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -N \\
  -d @- << 'EOF'
{{ json_body }}
EOF"""

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
            "streaming_response_call": OPENAI_PYTHON_STREAMING_RESPONSE_CALL_TEMPLATE,
            "output_handling": OPENAI_PYTHON_OUTPUT_HANDLING_TEMPLATE,
            "streaming_output_handling": OPENAI_PYTHON_STREAMING_OUTPUT_HANDLING_TEMPLATE,
            "structured_class": STRUCTURED_OUTPUT_CLASS_TEMPLATE,
        },
        "openai-sdk-ts": {
            "imports": OPENAI_TS_IMPORTS_TEMPLATE,
            "client_setup": OPENAI_TS_CLIENT_SETUP_TEMPLATE,
            "tools_definitions": OPENAI_TS_TOOLS_DEFINITIONS_TEMPLATE,
            "response_call": OPENAI_TS_RESPONSE_CALL_TEMPLATE,
            "streaming_response_call": OPENAI_TS_STREAMING_RESPONSE_CALL_TEMPLATE,
            "output_handling": OPENAI_TS_OUTPUT_HANDLING_TEMPLATE,
            "streaming_output_handling": OPENAI_TS_STREAMING_OUTPUT_HANDLING_TEMPLATE,
            "structured_schema": OPENAI_TS_SCHEMA_TEMPLATE,
        },
        "instructor-python": {
            "imports": INSTRUCTOR_IMPORTS_TEMPLATE,
            "client_setup": INSTRUCTOR_CLIENT_SETUP_TEMPLATE,
            "response_call": INSTRUCTOR_RESPONSE_CALL_TEMPLATE,
            "streaming_response_call": INSTRUCTOR_STREAMING_RESPONSE_CALL_TEMPLATE,
            "output_handling": INSTRUCTOR_OUTPUT_HANDLING_TEMPLATE,
            "streaming_output_handling": INSTRUCTOR_STREAMING_OUTPUT_HANDLING_TEMPLATE,
            "structured_class": STRUCTURED_OUTPUT_CLASS_TEMPLATE,
        },
        "dspy-python": {
            "imports": DSPY_IMPORTS_TEMPLATE,
            "client_setup": DSPY_CLIENT_SETUP_TEMPLATE,
            "tools_definitions": DSPY_TOOLS_DEFINITIONS_TEMPLATE,
            "response_call": DSPY_RESPONSE_CALL_TEMPLATE,
            "streaming_response_call": DSPY_STREAMING_RESPONSE_CALL_TEMPLATE,
            "output_handling": DSPY_OUTPUT_HANDLING_TEMPLATE,
            "streaming_output_handling": DSPY_STREAMING_OUTPUT_HANDLING_TEMPLATE,
            "structured_signature": DSPY_SIGNATURE_TEMPLATE,
        },
        "langchain-python": {
            "imports": LANGCHAIN_IMPORTS_TEMPLATE,
            "client_setup": LANGCHAIN_CLIENT_SETUP_TEMPLATE,
            "tools_definitions": LANGCHAIN_TOOLS_DEFINITIONS_TEMPLATE,
            "response_call": LANGCHAIN_RESPONSE_CALL_TEMPLATE,
            "streaming_response_call": LANGCHAIN_STREAMING_RESPONSE_CALL_TEMPLATE,
            "output_handling": LANGCHAIN_OUTPUT_HANDLING_TEMPLATE,
            "streaming_output_handling": LANGCHAIN_STREAMING_OUTPUT_HANDLING_TEMPLATE,
            "structured_class": STRUCTURED_OUTPUT_CLASS_TEMPLATE,
        },
        "litellm-python": {
            "imports": LITELLM_IMPORTS_TEMPLATE,
            "client_setup": LITELLM_CLIENT_SETUP_TEMPLATE,
            "tools_definitions": LITELLM_TOOLS_DEFINITIONS_TEMPLATE,
            "response_call": LITELLM_RESPONSE_CALL_TEMPLATE,
            "streaming_response_call": LITELLM_STREAMING_RESPONSE_CALL_TEMPLATE,
            "output_handling": LITELLM_OUTPUT_HANDLING_TEMPLATE,
            "streaming_output_handling": LITELLM_STREAMING_OUTPUT_HANDLING_TEMPLATE,
            "structured_class": STRUCTURED_OUTPUT_CLASS_TEMPLATE,
        },
        "curl": {
            "request": CURL_REQUEST_TEMPLATE,
            "streaming_request": CURL_STREAMING_REQUEST_TEMPLATE,
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
lm = dspy.LM(
    "openai/{{ model }}",
    api_key=os.environ.get("WORKFLOWAI_API_KEY"), # workflowai.com/keys
    api_base="{{ base_url }}"{% if response_format %},
    response_format={{ response_format }}  # pass the structured output format to enforce{% endif %}
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

DSPY_STREAMING_RESPONSE_CALL_TEMPLATE = """
# DSPy doesn't have native streaming support, but we can configure the underlying LM for streaming
# Note: This may not work with all DSPy signatures, consider using OpenAI SDK directly for streaming
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

DSPY_STREAMING_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
# DSPy doesn't natively support streaming for structured output
# The result is returned once complete
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
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import SecretStr

"""

LANGCHAIN_CLIENT_SETUP_TEMPLATE = """
# Configure LangChain to use WorkflowAI
llm = ChatOpenAI(
    base_url="{{ base_url }}",
    api_key=SecretStr(os.environ.get("WORKFLOWAI_API_KEY")),
    model="{{ model }}",
){% if is_structured %}.with_structured_output({{ class_name }}, method="json_schema")  # pass the structured output format to enforce{% endif %}

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
    messages{% if has_input_variables %},
    extra_body={"input": {{ extra_body }}}{% endif %}
)
{%- else %}
{%- if has_input_variables %}
result = llm.invoke(
    messages,
    extra_body={"input": {{ extra_body }}},
)
{%- else %}
result = llm.invoke(messages)
{%- endif %}
{%- endif %}

"""

LANGCHAIN_STREAMING_RESPONSE_CALL_TEMPLATE = """
{%- if messages %}
messages = {{ messages }}
{%- else %}
messages = []  # Messages are managed server-side in the deployment
{%- endif %}

{%- if has_tools %}
# Bind tools to the LLM
llm_with_tools = llm.bind_tools(tools)
result = llm_with_tools.stream(
    messages{% if has_input_variables %},
    extra_body={"input": {{ extra_body }}}{% endif %}
)
{%- else %}
{%- if has_input_variables %}
result = llm.stream(
    messages,
    extra_body={"input": {{ extra_body }}},
)
{%- else %}
result = llm.stream(messages)
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

LANGCHAIN_STREAMING_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
# Handle streaming structured output with LangChain
for chunk in result:
    # LangChain provides incremental chunks for structured output
    print(f"Chunk: {chunk}")
{%- else %}
{%- if has_tools %}
# Handle streaming with potential tool calls
for chunk in result:
    if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
        for tool_call in chunk.tool_calls:
            print(f"Tool called: {tool_call['name']}")
            print(f"Arguments: {tool_call['args']}")
    elif hasattr(chunk, 'content') and chunk.content:
        print(chunk.content, end="", flush=True)
print()  # Add newline at the end
{%- else %}
# Handle streaming text output
for chunk in result:
    if hasattr(chunk, 'content') and chunk.content:
        print(chunk.content, end="", flush=True)
print()  # Add newline at the end
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
litellm.api_base = "{{ base_url }}"
litellm.api_key = os.environ.get("WORKFLOWAI_API_KEY")  # workflowai.com/keys
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
    response_format={{ response_format }},  # pass the structured output format to enforce
{%- endif %}
{%- if has_tools %}
    {{ tools_parameter }},
{%- endif %}
{%- if has_input_variables %}
    extra_body={"input": {{ extra_body }}},
{%- endif %}
)

"""

LITELLM_STREAMING_RESPONSE_CALL_TEMPLATE = """
response = litellm.completion(  # type: ignore
    model="openai/{{ model }}",
{%- if messages %}
    messages={{ messages }},
{%- else %}
    messages=[],  # Messages are managed server-side in the deployment
{%- endif %}
{%- if response_format %}
    response_format={{ response_format }},  # pass the structured output format to enforce
{%- endif %}
{%- if has_tools %}
    {{ tools_parameter }},
{%- endif %}
{%- if has_input_variables %}
    extra_body={"input": {{ extra_body }}},
{%- endif %}
    stream=True,
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

LITELLM_STREAMING_OUTPUT_HANDLING_TEMPLATE = """
{%- if is_structured %}
{%- if has_tools %}
# Handle streaming with potential tool calls and structured output
accumulated_content = ""
for chunk in response:
    if chunk.choices[0].delta.tool_calls:
        for tool_call in chunk.choices[0].delta.tool_calls:
            if hasattr(tool_call, 'function') and tool_call.function.name:
                print(f"Tool called: {tool_call.function.name}")
            if hasattr(tool_call, 'function') and tool_call.function.arguments:
                print(f"Arguments: {tool_call.function.arguments}")
    elif chunk.choices[0].delta.content:
        accumulated_content += chunk.choices[0].delta.content
        print(chunk.choices[0].delta.content, end="", flush=True)

# Try to parse accumulated content as structured output
if accumulated_content:
    try:
        result = {{ class_name }}.model_validate_json(accumulated_content)
        print(f"Parsed result: {result}")
    except Exception as e:
        print(f"Could not parse as structured output: {e}")
{%- else %}
# Handle streaming structured output
accumulated_content = ""
for chunk in response:
    if chunk.choices[0].delta.content:
        accumulated_content += chunk.choices[0].delta.content
        print(chunk.choices[0].delta.content, end="", flush=True)

# Try to parse accumulated content as structured output
if accumulated_content:
    try:
        result = {{ class_name }}.model_validate_json(accumulated_content)
        print(f"Parsed result: {result}")
    except Exception as e:
        print(f"Could not parse as structured output: {e}")
{%- endif %}
{%- else %}
{%- if has_tools %}
# Handle streaming with potential tool calls
for chunk in response:
    if chunk.choices[0].delta.tool_calls:
        for tool_call in chunk.choices[0].delta.tool_calls:
            if hasattr(tool_call, 'function') and tool_call.function.name:
                print(f"Tool called: {tool_call.function.name}")
            if hasattr(tool_call, 'function') and tool_call.function.arguments:
                print(f"Arguments: {tool_call.function.arguments}")
    elif chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add newline at the end
{%- else %}
# Handle streaming text output
for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()  # Add newline at the end
{%- endif %}
{%- endif %}

"""

# Define DISCLAIMER_TEMPLATE to fix linter error
DISCLAIMER_TEMPLATE = ""
