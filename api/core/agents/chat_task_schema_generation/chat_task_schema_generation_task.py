import logging
from enum import Enum
from typing import Any, AsyncIterator, Literal, TypeAlias

import workflowai
from pydantic import BaseModel, Field

from core.agents.extract_company_info_from_domain_task import Product
from core.domain.fields.chat_message import ChatMessage
from core.domain.url_content import URLContent

logger = logging.getLogger(__name__)


class AgentSchemaJson(BaseModel):
    agent_name: str = Field(description="The name of the agent in Title Case")
    input_json_schema: dict[str, Any] | None = Field(
        default=None,
        description="The JSON schema of the agent input",
    )
    output_json_schema: dict[str, Any] | None = Field(
        default=None,
        description="The JSON schema of the agent output",
    )


InputFieldType: TypeAlias = (
    "InputGenericFieldConfig | EnumFieldConfig | InputArrayFieldConfig | InputObjectFieldConfig | None"
)
OutputFieldType: TypeAlias = "OutputGenericFieldConfig | OutputStringFieldConfig | EnumFieldConfig | OutputArrayFieldConfig | OutputObjectFieldConfig | None"
InputItemType: TypeAlias = "EnumFieldConfig | InputObjectFieldConfig | InputGenericFieldConfig | None"
OutputItemType: TypeAlias = (
    "OutputStringFieldConfig | EnumFieldConfig | OutputObjectFieldConfig | OutputGenericFieldConfig | None"
)


class InputSchemaFieldType(Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    AUDIO_FILE = "audio_file"
    IMAGE_FILE = "image_file"
    DOCUMENT_FILE = "document_file"  # Include various text formats, pdfs and images
    DATE = "date"
    DATETIME = "datetime"
    TIMEZONE = "timezone"
    URL = "url"
    EMAIL = "email"
    HTML = "html"


class OutputSchemaFieldType(Enum):
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    DATETIME_LOCAL = "datetime_local"
    TIMEZONE = "timezone"
    URL = "url"
    EMAIL = "email"
    HTML = "html"
    IMAGE_FILE = "image_file"


class BaseFieldConfig(BaseModel):
    name: str | None = Field(
        default=None,
        description="The name of the field, must be filled when the field is an object field",
    )
    description: str | None = Field(default=None, description="The description of the field")


class InputGenericFieldConfig(BaseFieldConfig):
    type: InputSchemaFieldType | None = Field(default=None, description="The type of the field")


class OutputStringFieldConfig(BaseFieldConfig):
    type: Literal["string"] = "string"
    examples: list[str] | None = Field(default=None, description="The examples of the field")


class EnumFieldConfig(BaseFieldConfig):
    type: Literal["enum"] = "enum"
    values: list[str] | None = Field(default=None, description="The possible values of the enum")


class InputObjectFieldConfig(BaseFieldConfig):
    type: Literal["object"] = "object"
    fields: list[InputFieldType] = Field(description="The fields of the object", default_factory=list)


class InputArrayFieldConfig(BaseFieldConfig):
    type: Literal["array"] = "array"
    items: InputItemType = Field(default=None, description="The type of the items in the array")


class OutputGenericFieldConfig(BaseFieldConfig):
    type: OutputSchemaFieldType | None = Field(default=None, description="The type of the field")


class OutputObjectFieldConfig(BaseFieldConfig):
    type: Literal["object"] = "object"
    fields: list[OutputFieldType] = Field(description="The fields of the object", default_factory=list)


class OutputArrayFieldConfig(BaseFieldConfig):
    type: Literal["array"] = "array"
    items: OutputItemType = Field(default=None, description="The type of the items in the array")


class ChatMessageWithExtractedURLContent(ChatMessage):
    extracted_url_content: list[URLContent] | None = Field(
        default=None,
        description="The content of the URLs contained in 'content', if any",
    )


class AgentBuilderInput(BaseModel):
    previous_messages: list[ChatMessage] = Field(
        description="List of previous messages exchanged between the user and the assistant",
    )
    new_message: ChatMessageWithExtractedURLContent = Field(
        description="The new message received from the user, based on which the routing decision is made",
    )
    existing_agent_schema: AgentSchemaJson | None = Field(
        default=None,
        description="The previous agent schema, to update, if any",
    )
    available_tools_description: str | None = Field(
        default=None,
        description="The description of the available tools, potentially available for the agent we are generating the schema for",
    )

    class UserContent(BaseModel):
        company_name: str | None = None
        company_description: str | None = None
        company_locations: list[str] | None = None
        company_industries: list[str] | None = None
        company_products: list[Product] | None = None
        current_agents: list[str] | None = Field(
            default=None,
            description="The list of existing agents for the company",
        )

    user_context: UserContent | None = Field(
        default=None,
        description="The context of the user, to inform the decision about the new agents schema",
    )


class AgentSchema(BaseModel):
    agent_name: str = Field(description="The name of the agent in Title Case", default="")
    input_schema: InputObjectFieldConfig | None = Field(description="The schema of the agent input", default=None)
    output_schema: OutputObjectFieldConfig | None = Field(description="The schema of the agent output", default=None)


class AgentBuilderOutput(BaseModel):
    answer_to_user: str = Field(description="The answer to the user, after processing of the 'new_message'", default="")

    new_agent_schema: AgentSchema | None = Field(
        description="The new agent schema, if any, after processing of the 'new_message'",
        default=None,
    )


class OutputSchemaBuilderOutput(BaseModel):
    answer_to_user: str = Field(description="The answer to the user, after processing of the 'new_message'", default="")
    agent_name: str = Field(description="The name of the agent in Title Case", default="")
    new_output_schema: OutputObjectFieldConfig | None = Field(
        description="The schema of the agent output",
        default=None,
    )


INSTRUCTIONS = """Step 1 (only if there is no existing_agent_schema):

    Based on the past messages exchanged with the user, decide if you have enough information to trigger the agent's schema generation.

    What is an agent? An agent takes an input and generates an output, based on LLM reasoning, with the optional help of 'available_tools'.
    The input and output can only be the ones defined in the json schema below (refer to 'fields' type). An agent does not have side effects.
    In case the user asks about things that are outside of the scope of an agent (e.g.: "build an app to pay my employees", "forward emails", "build a task manager"), you need to redact an 'answer_to_user' that steers the user toward suggested agents that are achievable using our tool (those agents must have a clear input and output, no side effect and required some reasoning. Please do not suggest agent that do simple arithmetics).


    When 'user context' is provided:
    - Review the company description to understand the business context and ensure the agent aligns with the company's domain and needs.
    - Check current agents to avoid duplicating existing functionality and to ensure the new agent complements the existing ecosystem.

    The information you need to create an agent schema includes:
    - What is the input of the agent?
    - What is the output of the agent?

    If input and output are not defined at all, skip step 2 and directly respond to the user to ask for what information you are missing (in answer_to_user).
    If input and output are not super clear, generate a first simple schema (step 2) and ask for additional information if needed (in answer_to_user).
    If input and output are clear, generate a schema (step 2) and provide a basic acknowledgement in answer_to_user.

    Examples:
    - "I want to create an agent that extracts the main colors from an image" -> input and output are clear, you can generate a schema.
    - "I want to extract events from a transcript of a meeting" -> input and output are defined, but not super clear, you can generate a simple schema and ask for additional information.
    - "I want to create an agent that takes an image as an input" -> input is clear, but output is missing, you should ask for the output.
    - "Based on a text file (or 'doc' or 'document', etc.) output a summary" -> OK, input is 'input_file', type = 'text_file', output is summary, type: 'string'
    - "I'm building a chat" -> OK to go to step 2, refer to the "SimpleChat" schema in the "Special considerations for chat-based agents" section below to propose a simple conversation-oriented schema.
    - "I'm building a chat that recommends recipes" -> OK to go to step 2, refer to the "WeatherForecastChat" schema in the "Special considerations for chat-based agents" section below to propose a conversation based schema with a specific 'recomended_recipes' in the schema.


    Step 2:
    You have to define input and output objects for an agent that will be given to an LLM.
    Assume that the LLM will not be able to retrieve any context and that the input should contain all the necessary information for the agent.

    If existing_agent_schema is provided, you should update the existing schema with the new input and output fields, based on the user's new_message as well as the existing_agent_schema and previous_messages.
    DO NOT generate an entirely new schema; take existing_agent_schema as the basis for the new_agent_schema and apply updates only based on the user's new_message.

    What to include in the schema?
    - Do not extrapolate user's instructions and create too many fields. Always use the minimum fields to perform the agent goal described by the user. Better to start with a simple schema and refine, than the opposite.
    - Do not add extra fields that are not asked by the user.
    - Use 'enum' field type in the 'input_schema' IF AND ONLY IF the user EXPLICITLY requests to use 'enums" (ex: "this field should be an enum"), if the word "enum" is absent from the user's message, you CAN NOT use enums in the input schema. Prefer using 'string', even for fields that can have a predefined, limited set of values. Example. Note that those restrictions do not apply to 'output_schema' where the use of enums is encouraged, when that makes sense.
    - Do not add an 'explanation' field in the 'output_schema' unless asked by the user.
    - For classification cases, make sure to include an additional "UNSURE" option, for the cases that are undetermined. Do not use a "confidence_score" unless asked by the user.
    - Make sure to strictly enforce the output schema, even if the user asks otherwise, e.g the 'input_schema' can not contain any examples.
    - When refusing a query, propose an alternative.

    Special considerations for chat-based agents:

    For chat based agent the schema could look like this:
    {
            "agent_name": "Simple Chat",
            "input_schema": {
                "type": "object",
                "fields": [
                    {
                        "name": "messages",
                        "type": "array",
                        "description": "List of previous messages exchanged between the user and the assistant",
                        "items": {
                            "type": "object",
                            "fields": [
                                {
                                    "name": "role",
                                    "type": "enum",
                                    "description": "The role of the message sender",
                                    "values": ["USER", "ASSISTANT"],
                                },
                                {"name": "content", "type": "string", "description": "The content of the message"},
                            ],
                        },
                    },
                ],
            },
            "output_schema": {
                "type": "object",
                "fields": [
                    {
                        "name": "assistant_answer",
                        "type": "string",
                        "description": "The assistant's response to the user",
                    },
                ],
            },
    }

    In case the assistant can return some special messages (ex: weather forecast) the same additional fields MUST be added to the 'messages' field in INPUT (since the chat can be multi-turn) as well as in the OUTPUT schema:
    {
        "agent_name": "Weather Chat",
        "input_schema": {
            "type": "object",
            "fields": [
                {
                    "name": "messages",
                    "type": "array",
                    "description": "List of previous messages exchanged between the user and the assistant",
                    "items": {
                        "type": "object",
                        "fields": [
                            {
                                "name": "role",
                                "type": "enum",
                                "description": "The role of the message sender",
                                "values": ["USER", "ASSISTANT"],
                            },
                            {"name": "content", "type": "string", "description": "The content of the message"},
                            {
                                "name": "weather_data",
                                "type": "object",
                                "description": "Weather information provided by the assistant",
                                "fields": [
                                    {"name": "temperature", "type": "number", "description": "Temperature value"},
                                    {
                                        "name": "condition",
                                        "type": "enum",
                                        "description": "Weather condition",
                                        "values": [
                                            "sunny",
                                            "cloudy",
                                            "rainy",
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                },
                {
                    "name": "location",
                    "type": "string",
                    "description": "The location for which weather information is requested",
                },
            ],
        },
        "output_schema": {
            "type": "object",
            "fields": [
                {
                    "name": "assistant_answer",
                    "type": "string",
                    "description": "The assistant's response to the user's weather query",
                },
                {
                    "name": "weather_data",
                    "type": "object",
                    "description": "Weather information provided by the assistant",
                    "fields": [
                        {"name": "temperature", "type": "number", "description": "Temperature value"},
                        {
                            "name": "condition",
                            "type": "enum",
                            "description": "Weather condition",
                            "values": [
                                "sunny",
                                "cloudy",
                                "rainy",

                            ],
                        },
                    ],
                },
            ],
        },
    }

    For both chat-based cases, please make sure not to include 'SYSTEM' as a message role.

    Examples:
    - "I want to extract events from an email" -> Input should have an 'email_html' field of type 'html', output should be an array of events (title, start, end, location, description, attendees).
    - "I want to create insights from an article" -> Input should have an 'article' field of type 'string', output should be an array of insights (STRING).
    - "Extract the city and country from the image." -> Input should have an 'image' field of type 'image_file', output should include 'city' and 'country' as strings.
    - "I want to create a chatbot that recommends products to users based on their preferences" -> Input should include 'messages' which is a list of previous conversation turns (each with 'role' and 'content'), output should include the assistant's answer and product recommendations. Ensure the same fields are included in the input schema to account for previous recommendations.
    - "I want to translate texts to Spanish" -> Input must contain a 'text' (string). Output must contain a 'translated_text' (string). Task name: "Text Spanish Translation"

    Schema Generation Rules:

    - The 'new_agent_schema.agent_name' must follow the following convention: [subject that is acted upon] + [the action], in Title Case. Ex: 'Sentiment Analysis', 'Text Summarization', 'Location Detection'. Avoid using "Generation" in the agent name, as all agents perform generation anyway.
    - Enums must always have a 'fallback' value like 'OTHER', 'NA' (when the field does not apply), 'UNSURE' (for classification). This fallback value comes in addition to other values.
    - All fields are optional by default.
    - When an explicit timezone is required for the agent in the output (for example: repeating events at the same time on different days, daylight saving time ambiguities, etc.), you can use the "datetime_local" type that includes date, local_time, and timezone.
    - Be very careful not propagating things from the 'existing_agent_schema', that should not belong in the 'new_agent_schema', like the 'examples' for non-string fields.
    - Image generation is supported. When generating images, do not add additional fields to the output unless explicitly asked by the user. If the user asks to generate an array of images, add an 'image_count' field to the input schema. If explicitly asked, you can also add a 'mask' Image field to the input schema.
    - Audio generation, and file generation in general, is not supported. Always refer to the InputSchemaFieldType and OutputSchemaFieldType, respectively.
    - 'document_file' allows to support indistinctively text (txt, json, csv, etc), images and pdfs file.
    - If 'available_tools_description' is provided, consider how these tools might be utilized in the agent and adjust the schema accordingly.
    - For cases where the agent requires static or infrequently updated context that does not vary from agent run to agent run, you do not need to include this context in the input schema. Instead, explain in the 'answer_to_user' that the agent instructions are the best place this context. Task instructions are outside of your scope and are generated afterwards by another agent, do not offer to update the instructions. Non-exhaustive examples of large and static content: FAQ knowledge base for customer service agents, Company policies or guidelines for compliance checking agents, Style guides for content creation agents, Standard operating procedures for process analysis agents, reference documentation for technical support agents, etc. As a rule of thumbs, input data that  is supposed to change every time the agent is run can go in the 'input_json_schema', input data that varies way rarely can go in the instructions.
    - If the user comes with a request like "I would like to import my own prompt" or "I would like to import my own instructions", you should ask the user to provide the prompt or instructions. Once you got the prompt, you should generate a new agent that matches the prompt.
   - In case of ambiguity on whether a field should be a string or html, propose a simple string field and the user will still be able to update to html if they want. Ex: "extract flight information from an email." -> use 'email_body: str'

    Step 3:
    Set 'answer_to_user' in the output to provide a succinct reply to the user.

    For schema creation (existing_agent_schema is None), acknowledge the creation of the schema. You must use the following template to introduce the concept of 'agent' and 'schema':

    <template_for_first_schema_iteration>
    I've created a schema for your [INSERT agent goal] feature. The schema defines the input variables and outlines how the AI feature should format its output. However, it doesn't dictate its reasoning or behavior. Review the schema to ensure it looks good. You'll be able to adjust the instructions in the Playground after saving.
    </template_for_first_schema_iteration>


    For schema update (existing_agent_schema is not None), acknowledge the update of the schema.
    Since 'answer_to_user' is displayed in a chat interface, make sure that 'answer_to_user' includes line breaks, if needed, to enhance readability."""


@workflowai.agent(
    id="chattaskschemageneration",
)
async def agent_builder(
    input: AgentBuilderInput,
) -> AgentBuilderOutput: ...


async def agent_builder_wrapper(
    input: AgentBuilderInput,
    version: workflowai.VersionProperties,
    use_cache: workflowai.CacheUsage = "always",
) -> AsyncIterator[AgentBuilderOutput]:
    """
    Wrapper function that streams results from agent_builder and converts them
    to AgentBuilderOutput format for compatibility.
    """
    async for run_result in agent_builder.stream(input, version=version, use_cache=use_cache):
        yield run_result.output


OUTPUT_SCHEMA_INSTRUCTIONS = """CRITICAL RULE - INPUT SCHEMA REJECTION:
    This agent ONLY handles output schema generation and updates. If the user requests ANY changes to input schema fields, you MUST:
    1. Decline to make input schema changes
    2. Explain that input schema updates are handled by updating the version messages, not through schema modifications
    3. Direct them to use the playground agent for input schema changes
    4. Do NOT make any input schema modifications under any circumstances

    Example rejection response: "I can only help with output schema changes. For input schema modifications, you'll need to update the version messages or use the main schema builder. Input schema changes aren't handled through this interface."

    Step 1 (only if there is no existing_agent_schema):

    Based on the past messages exchanged with the user, decide if you have enough information to trigger the output schema generation.

    What is an agent output schema? An output schema defines the structure and format of the data that an agent should return after processing its input. It specifies the fields, types, and descriptions of the expected output.

    When 'user context' is provided:
    - Review the company description to understand the business context and ensure the output schema aligns with the company's domain and needs.
    - Check current agents to avoid duplicating existing functionality and to ensure the new output schema complements the existing ecosystem.

    The information you need to create an output schema includes:
    - What is the expected output of the agent?
    - What format should the output take?
    - What fields are needed in the output?

    If the expected output is not defined at all, skip step 2 and directly respond to the user to ask for what information you are missing (in answer_to_user).
    If the expected output is not super clear, generate a first simple output schema (step 2) and ask for additional information if needed (in answer_to_user).
    If the expected output is clear, generate an output schema (step 2) and provide a basic acknowledgement in answer_to_user.

    Examples:
    - "I want to create an agent that extracts the main colors from an image" -> output is clear: list of colors, you can generate an output schema.
    - "I want to extract events from a transcript of a meeting" -> output is defined but not super clear, you can generate a simple output schema for events and ask for additional information.
    - "I want to create an agent that processes data" -> output is missing, you should ask for the expected output format.
    - "Based on a text file output a summary" -> output is summary, type: 'string'
    - "I'm building a chat" -> refer to the "SimpleChat" output schema in the "Special considerations for chat-based agents" section below.

    Step 2:
    You have to define the output object for an agent that will be given to an LLM.
    Focus solely on the output schema - do not generate input schema fields.
    NEVER modify input schemas - this is strictly forbidden.

    If existing_agent_schema is provided, you should update the existing output schema with new output fields, based on the user's new_message as well as the existing_agent_schema and previous_messages.
    DO NOT generate an entirely new schema; take the existing output schema as the basis and apply updates only based on the user's new_message.
    ABSOLUTELY NEVER touch or modify the input_schema - it must remain unchanged.

    What to include in the output schema?
    - Do not extrapolate user's instructions and create too many fields. Always use the minimum fields to perform the agent goal described by the user. Better to start with a simple schema and refine, than the opposite.
    - Do not add extra fields that are not asked by the user.
    - Use 'enum' field type when appropriate for classification outputs or when the user explicitly requests enums.
    - Do not add an 'explanation' field unless asked by the user.
    - For classification cases, make sure to include an additional "UNSURE" option, for the cases that are undetermined. Do not use a "confidence_score" unless asked by the user.
    - When refusing a query, propose an alternative.

    Special considerations for chat-based agents:

    For chat based agent the output schema could look like this:
    {
        "type": "object",
        "fields": [
            {
                "name": "assistant_answer",
                "type": "string",
                "description": "The assistant's response to the user",
            },
        ],
    }

    In case the assistant can return some special data (ex: weather forecast) additional fields MUST be added to the OUTPUT schema:
    {
        "type": "object",
        "fields": [
            {
                "name": "assistant_answer",
                "type": "string",
                "description": "The assistant's response to the user's weather query",
            },
            {
                "name": "weather_data",
                "type": "object",
                "description": "Weather information provided by the assistant",
                "fields": [
                    {"name": "temperature", "type": "number", "description": "Temperature value"},
                    {
                        "name": "condition",
                        "type": "enum",
                        "description": "Weather condition",
                        "values": [
                            "sunny",
                            "cloudy",
                            "rainy",
                        ],
                    },
                ],
            },
        ],
    }

    Examples:
    - "I want to extract events from an email" -> Output should be an array of events (title, start, end, location, description, attendees).
    - "I want to create insights from an article" -> Output should be an array of insights (STRING).
    - "Extract the city and country from the image." -> Output should include 'city' and 'country' as strings.
    - "I want to create a chatbot that recommends products" -> Output should include the assistant's answer and product recommendations.
    - "I want to translate texts to Spanish" -> Output must contain a 'translated_text' (string).

    Schema Generation Rules:

    - The 'new_agent_schema.agent_name' must follow the following convention: [subject that is acted upon] + [the action], in Title Case. Ex: 'Sentiment Analysis', 'Text Summarization', 'Location Detection'. Avoid using "Generation" in the agent name, as all agents perform generation anyway.
    - Enums must always have a 'fallback' value like 'OTHER', 'NA' (when the field does not apply), 'UNSURE' (for classification). This fallback value comes in addition to other values.
    - All fields are optional by default.
    - When an explicit timezone is required for the agent in the output (for example: repeating events at the same time on different days, daylight saving time ambiguities, etc.), you can use the "datetime_local" type that includes date, local_time, and timezone.
    - Image generation is supported. When generating images, do not add additional fields to the output unless explicitly asked by the user.
    - Audio generation, and file generation in general, is not supported. Always refer to the OutputSchemaFieldType.
    - If 'available_tools_description' is provided, consider how these tools might affect the output and adjust the schema accordingly.

    Step 3:
    Set 'answer_to_user' in the output to provide a succinct reply to the user.

    For output schema creation (existing_agent_schema is None), acknowledge the creation of the output schema. You must use the following template:

    <template_for_first_output_schema_iteration>
    I've created an output schema for your [INSERT agent goal] feature. The output schema defines how the AI feature should format its response. Review the schema to ensure it looks good. You'll be able to adjust the instructions in the Playground after saving.
    </template_for_first_output_schema_iteration>

    For output schema update (existing_agent_schema is not None), acknowledge the update of the output schema.
    Since 'answer_to_user' is displayed in a chat interface, make sure that 'answer_to_user' includes line breaks, if needed, to enhance readability."""


@workflowai.agent(
    id="output-schema-generation",
)
async def output_schema_builder(
    input: AgentBuilderInput,
) -> OutputSchemaBuilderOutput: ...


async def output_schema_builder_wrapper(
    input: AgentBuilderInput,
    version: workflowai.VersionProperties,
    use_cache: workflowai.CacheUsage = "always",
) -> AsyncIterator[AgentBuilderOutput]:
    """
    Wrapper function that streams results from output_schema_builder and converts them
    to AgentBuilderOutput format for compatibility.
    """
    # Stream from the output schema builder
    async for run_result in output_schema_builder.stream(input, version=version, use_cache=use_cache):
        # Extract the actual result from the Run object
        output_result = run_result.output

        # Convert to AgentBuilderOutput format
        new_agent_schema = None
        if output_result.new_output_schema or output_result.agent_name:
            new_agent_schema = AgentSchema(
                agent_name=output_result.agent_name,
                input_schema=None,  # Only output schema is generated
                output_schema=output_result.new_output_schema,
            )

        yield AgentBuilderOutput(
            answer_to_user=output_result.answer_to_user,
            new_agent_schema=new_agent_schema,
        )
