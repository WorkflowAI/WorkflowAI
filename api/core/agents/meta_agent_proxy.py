import datetime
import json
import os
from typing import Any, AsyncIterator, Literal, NamedTuple, Self

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionToolParam
from pydantic import BaseModel, Field

from core.agents.meta_agent import InputFile, SelectedModels
from core.domain.documentation_section import DocumentationSection
from core.domain.feedback import Feedback
from core.domain.integration.integration_domain import Integration
from core.domain.url_content import URLContent
from core.domain.version_environment import VersionEnvironment

from .extract_company_info_from_domain_task import Product


class WorkflowaiPage(BaseModel):
    title: str
    description: str


class WorkflowaiSection(BaseModel):
    name: str
    pages: list[WorkflowaiPage]


# MVP for the redirection feature, will be replaced by a dynamic feature in the future
STATIC_WORKFLOWAI_PAGES = [
    WorkflowaiSection(  # noqa: F821
        name="Iterate",
        pages=[
            WorkflowaiPage(
                title="Schemas",
                description="Dedicated to the management of agent schemas, allow to see previous schema versions, etc.",
            ),
            WorkflowaiPage(
                title="Playground",
                description="The current page the user is on, allow to run agents, on different models, with different instructions, etc.",
            ),
            WorkflowaiPage(
                title="Versions",
                description="Allows to see an history of all previous instructions versions of the current agent, with changelogs between versions, etc.",
            ),
            WorkflowaiPage(
                title="Settings",
                description="Allow to rename the current agent, delete it, or make it public. Also allows to manage private keys that allow to run the agent via API / SDK.",
            ),
        ],
    ),
    WorkflowaiSection(
        name="Compare",
        pages=[
            WorkflowaiPage(
                title="Reviews",
                description="Allows to visualize the annotated output for this agents (positive, negative, etc.)",
            ),
            WorkflowaiPage(
                title="Benchmarks",
                description="Allows to compare model correctness, cost, latency, based on a set of reviews.",
            ),
        ],
    ),
    WorkflowaiSection(
        name="Integrate",
        pages=[
            WorkflowaiPage(
                title="Code",
                description="Get ready-to-use Python SDK code snippets, TypeScript SDK code snippets, and example REST requests to run the agent via API.",
            ),
            WorkflowaiPage(
                title="Deployments",
                description="Allows to deploy the current agent to fixed environments 'dev', 'staging', 'production'. This allows, for example,to quickly hotfix instructions in production, since the code point to a static 'production' deployment",
            ),
        ],
    ),
    WorkflowaiSection(
        name="Monitor",
        pages=[
            WorkflowaiPage(
                title="User Feedback",
                description="Allows to see an history of all previous user feedbacks for the current agent.",
            ),
            WorkflowaiPage(
                title="Runs",
                description="Allows to see an history of all previous runs of the current agent. 'Run' refers to a single execution of the agent, with a given input, instructions and a given model.",
            ),
            WorkflowaiPage(
                title="Costs",
                description="Allows to visualize the cost incurred by the agent per day, for yesterday, last week, last month, last year, and all time.",
            ),
        ],
    ),
]


class BaseResult(BaseModel):
    tool_name: str = Field(
        description="The name of the tool call",
    )

    status: Literal["assistant_proposed", "user_ignored", "completed", "failed"] = Field(
        description="The status of the tool call",
    )


class BaseToolCallRequest(BaseModel):
    ask_user_confirmation: bool | None = Field(
        default=None,
        description="Whether the tool call should be automatically executed by on the frontend (ask_user_confirmation=false), or if the user should be prompted to run the tool call (ask_user_confirmation=true). Based on the confidence of the meta-agent in the tool call.",
    )


class ImprovePromptToolCallRequest(BaseToolCallRequest):
    agent_run_id: str | None = Field(
        default=None,
        description="The id (agent_runs.id) of the runs among the 'agent_runs' that is the most representative of what we want to improve in the 'agent_instructions'",
    )
    instruction_improvement_request_message: str = Field(
        description="The feedback on the agent run (what is wrong with the output of the run, what is the expected output, etc.).",
    )


class ImprovePromptToolCallResult(BaseResult, ImprovePromptToolCallRequest):
    pass


class RunCurrentAgentOnModelsToolCallRequest(BaseToolCallRequest):
    class RunConfig(BaseModel):
        run_on_column: Literal["column_1", "column_2", "column_3"] | None = Field(
            default=None,
            description="The column to run the agent on the agent will be run on all columns",
        )
        model: str | None = Field(
            default=None,
            description="The model to run the agent on the agent will be run on all models",
        )

    run_configs: list[RunConfig] | None = Field(
        default=None,
        description="The list of configurations to run the current agent on.",
    )


class RunCurrentAgentOnModelsToolCallResult(BaseResult, RunCurrentAgentOnModelsToolCallRequest):
    pass


class GenerateAgentInputToolCallRequest(BaseToolCallRequest):
    instructions: str | None = Field(
        default=None,
        description="The instructions on how to generate the agent input, this message will be passed to the input generation agent.",
    )


class GenerateAgentInputToolCallResult(BaseResult, GenerateAgentInputToolCallRequest):
    pass


class ProxyMetaAgentChatMessage(BaseModel):
    role: Literal["USER", "PLAYGROUND", "ASSISTANT"] = Field(
        description="The role of the message sender, 'USER' is the actual human user browsing the playground, 'PLAYGROUND' are automated messages sent by the playground to the agent, and 'ASSISTANT' being the assistant generated by the agent",
    )
    content: str = Field(
        description="The content of the message",
        examples=[
            "Thank you for your help!",
            "What is the weather forecast for tomorrow?",
        ],
    )

    tool_call: dict[str, Any] | None

    tool_call_status: Literal["assistant_proposed", "user_ignored", "completed", "failed"] | None


class AgentRun(BaseModel):
    id: str = Field(
        description="The id of the agent run",
    )
    model: str | None = Field(
        default=None,
        description="The model that was used to generate the agent output",
    )
    input: str | None = Field(
        default=None,
        description="The input of the agent, if no error occurred.",
    )
    output: str | None = Field(
        default=None,
        description="The output of the agent, if no error occurred.",
    )
    error: dict[str, Any] | None = Field(
        default=None,
        description="The error that occurred during the agent run, if any.",
    )
    raw_response: str | None = Field(
        description="The raw LLM completions that were made by the agent to produce the output",
    )

    class ToolCall(BaseModel):
        name: str
        input: dict[str, Any]

    tool_calls: list[ToolCall] | None = Field(
        default=None,
        description="The tool calls that were made by the agent to produce the output",
    )
    cost_usd: float | None = Field(
        default=None,
        description="The cost of the agent run in USD",
    )
    duration_seconds: float | None = Field(
        default=None,
        description="The duration of the agent in seconds",
    )
    user_evaluation: Literal["positive", "negative"] | None = Field(
        default=None,
        description="The user evaluation of the agent output",
    )


class PlaygroundState(BaseModel):
    agent_input: dict[str, Any] | None = Field(
        default=None,
        description="The input for the agent",
    )

    agent_input_files: list[InputFile] | None = Field(
        default=None,
        description="The files contained in the 'agent_input' object, if any",
    )
    agent_temperature: float | None = Field(
        default=None,
        description="The temperature for the agent",
    )
    playground_agent_runs: list[AgentRun] | None = Field(
        default=None,
        description="The agent runs that were made in the playground",
    )

    version_messages: list[dict[str, Any]] | None = Field(
        default=None,
        description="The version messages of the agent",
    )

    class PlaygroundModel(BaseModel):
        id: str = Field(
            description="The id of the model",
        )
        name: str
        is_supported_for_agent: bool = Field(
            description="Whether the model is supported for the current agent",
        )
        is_not_supported_reason: str | None = Field(
            default=None,
            description="The reason why the model is not supported for the current agent",
        )
        is_default: bool = Field(
            default=False,
            description="Whether the model is one of the default models on the WorkflowAI platform",
        )
        is_latest: bool = Field(
            default=False,
            description="Whether the model is the latest model in its family",
        )
        quality_index: int = Field(
            description="The quality index that quantifies the reasoning abilities of the model",
        )
        quality_index_ranking: int = Field(
            description="The quality index ranking of the model, 1 being the smartest",
        )
        speed_index: int = Field(
            description="The speed index that quantifies the response speed of the model",
        )
        speed_index_ranking: int = Field(
            description="The speed index ranking of the model, 1 being the fastest",
        )
        context_window_tokens: int = Field(
            description="The context window of the model in tokens",
        )
        supports_structured_output: bool = Field(
            description="Whether the model supports structured output",
        )

        estimate_cost_per_thousand_runs_usd: float | None = Field(
            default=None,
            description="The estimated cost per thousand runs in USD",
        )
        cost_ranking: int = Field(
            description="The cost ranking of the model, 1 being the cheapest",
        )

    available_models: list[PlaygroundModel] = Field(
        description="The models currently available in the playground",
    )

    selected_models: SelectedModels = Field(
        description="The models currently selected in the playground",
    )


class ProxyMetaAgentInput(BaseModel):
    current_datetime: datetime.datetime = Field(
        description="The current datetime",
    )

    chat_messages: list[ProxyMetaAgentChatMessage] = Field(
        description="The list of messages in the conversation, the last message being the most recent one",
    )

    class Agent(BaseModel):
        name: str
        slug: str
        schema_id: int
        description: str | None = None
        input_schema: dict[str, Any]
        output_schema: dict[str, Any]
        used_integration: Integration | None = None
        is_input_variables_enabled: bool = Field(
            default=False,
            description="Whether the agent is using input variables",
        )
        is_structured_output_enabled: bool = Field(
            default=False,
            description="Whether the agent is using structured output",
        )

    current_agent: Agent = Field(
        description="The current agent to use for the conversation",
    )

    latest_agent_run: AgentRun | None = Field(
        default=None,
        description="The latest agent run",
    )

    previous_agent_runs: list[AgentRun] | None = Field(
        default=None,
        description="The previous agent runs",
    )

    latest_messages_url_content: list[URLContent] = Field(
        default_factory=list,
        description="The URL content of the latest 'USER' message, if any URL was found in the message.",
    )

    class CompanyContext(BaseModel):
        company_name: str | None = None
        company_description: str | None = None
        company_locations: list[str] | None = None
        company_industries: list[str] | None = None
        company_products: list[Product] | None = None
        existing_agents_descriptions: list[str] | None = Field(
            default=None,
            description="The list of existing agents for the company",
        )

    company_context: CompanyContext = Field(
        description="The context of the company to which the conversation belongs",
    )

    workflowai_sections: list[WorkflowaiSection] = Field(
        default=STATIC_WORKFLOWAI_PAGES,
        description="Other sections pages of the WorkflowAI platform (outside of the playground page, which this agent is part of). You can use this information to answer questions about the WorkflowAI platform and direct the user to the relevant pages. All those page are clickable on the left panel from the WorkflowAI playground.",
    )

    workflowai_documentation_sections: list[DocumentationSection] = Field(
        description="The relevant documentation sections of the WorkflowAI platform, which this agent is part of",
    )

    integration_documentation: list[DocumentationSection] = Field(
        description="The documentation of the integration that the user is using, if any",
    )

    available_hosted_tools_description: str = Field(
        description="The description of the available hosted tools, that can be potientially added to the agent 'messages' in order to improve the agent's output.",
    )

    playground_state: PlaygroundState

    class AgentLifecycleInfo(BaseModel):
        class DeploymentInfo(BaseModel):
            has_api_or_sdk_runs: bool | None = Field(
                default=None,
                description="Whether the 'current_agent' has already been run via API / SDK",
            )
            latest_api_or_sdk_run_date: datetime.datetime | None = Field(
                default=None,
                description="The date of the latest API / SDK run",
            )

            class Deployment(BaseModel):
                deployed_at: datetime.datetime | None = Field(
                    default=None,
                    description="The date of the deployment",
                )
                deployed_by_email: str | None = Field(
                    default=None,
                    description="The email of the staff member who deployed the 'current_agent' version",
                )
                environment: VersionEnvironment | None = Field(
                    default=None,
                    description="The environment in which the 'current_agent' version is deployed ('dev', 'staging' or 'production')",
                )
                model_used: str | None = Field(
                    default=None,
                    description="The model used to run the 'current_agent' deployment",
                )
                last_active_at: datetime.datetime | None = Field(
                    default=None,
                    description="The date of the last run of the 'current_agent' deployment",
                )
                run_count: int | None = Field(
                    default=None,
                    description="The number of runs of the 'current_agent' deployment",
                )
                notes: str | None = Field(
                    default=None,
                    description="The notes of the 'current_agent' deployment, added by the staff member who created the deployed version",
                )

            deployments: list[Deployment] | None = Field(
                default=None,
                description="The list of deployments of the 'current_agent'",
            )

        deployment_info: DeploymentInfo | None = Field(
            default=None,
            description="The deployment info of the agent",
        )

        class FeedbackInfo(BaseModel):
            user_feedback_count: int | None = Field(
                default=None,
                description="The number of user feedbacks",
            )

            class AgentFeedback(BaseModel):
                created_at: datetime.datetime | None = None
                outcome: Literal["positive", "negative"] | None = None
                comment: str | None = None

                @classmethod
                def from_domain(cls, feedback: Feedback) -> Self:
                    return cls(
                        created_at=feedback.created_at,
                        outcome=feedback.outcome,
                        comment=feedback.comment,
                    )

            latest_user_feedbacks: list[AgentFeedback] | None = Field(
                default=None,
                description="The 10 latest user feedbacks",
            )

        feedback_info: FeedbackInfo | None = Field(
            default=None,
            description="The info related to the user feedbacks of the agent.",
        )

        class InternalReviewInfo(BaseModel):
            reviewed_input_count: int | None = Field(
                default=None,
                description="The number of reviewed inputs",
            )

        internal_review_info: InternalReviewInfo | None = Field(
            default=None,
            description="The info related to the internal reviews of the agent.",
        )

    agent_lifecycle_info: AgentLifecycleInfo | None = Field(
        default=None,
        description="The lifecycle info of the agent",
    )

    suggested_messages_with_input_variables: list[dict[str, Any]] | None = Field(
        default=None,
        description="The suggested messages with input variables, if any",
    )
    suggested_input_variables_example: dict[str, Any] | None = Field(
        default=None,
        description="The suggested input variables example, if any",
    )

    suggested_output_class_code: str | None = Field(
        default=None,
        description="The suggested output class code to migrate to structured generation, if any",
    )
    suggested_instructions_parts_to_remove: list[str] | None = Field(
        default=None,
        description="The suggested instructions parts to remove from the original instructions when migrating to structured generation, if any",
    )


class ProxyMetaAgentOutput(BaseModel):
    assistant_answer: str | None = Field(
        default=None,
        description="The content of the answer message from the meta-agent",
    )

    improvement_instructions: str | None = Field(
        default=None,
        description="Instructions on how to improve the current agent version's messages, if any.",
    )

    class NewTool(BaseModel):
        name: str
        description: str
        parameters: dict[str, Any]

    new_tool: NewTool | None = Field(
        default=None,
        description="The new tool to add to the current agent, if any",
    )

    class RunTriggerConfig(BaseModel):
        model_1: str
        model_2: str | None = None
        model_3: str | None = None

    run_trigger_config: RunTriggerConfig | None = Field(
        default=None,
        description="The run trigger config to use for the agent, if any",
    )

    generate_input_request: GenerateAgentInputToolCallRequest | None = Field(
        default=None,
        description="The generate input request, if any",
    )

    updated_version_messages: list[dict[str, Any]] | None = Field(
        default=None,
        description="The directly generated version messages, if any",
    )


class ParsedToolCall(NamedTuple):
    """Result of parsing a tool call from the OpenAI streaming response."""

    improvement_instructions: str | None = None
    tool_name: str | None = None
    tool_description: str | None = None
    tool_parameters: dict[str, Any] | None = None
    run_trigger_config: ProxyMetaAgentOutput.RunTriggerConfig | None = None
    generate_input_request: GenerateAgentInputToolCallRequest | None = None
    updated_version_messages: list[dict[str, Any]] | None = None


def parse_tool_call(tool_call: Any) -> ParsedToolCall:
    """Parse a tool call and return the extracted data.

    Returns a ParsedToolCall with the parsed tool data. Fields are populated based on tool type:
    - update_version_messages: updated_version_messages, example_input
    - create_custom_tool: tool_name, tool_description, tool_parameters
    - run_agent_on_model: run_trigger_config
    - generate_agent_input: generate_input_request
    - updated_version_messages: updated_version_messages
    """
    if not tool_call.function or not tool_call.function.arguments:
        return ParsedToolCall()

    function_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments)

    if function_name == "update_version_messages":
        return ParsedToolCall(
            improvement_instructions=arguments["improvement_instructions"],
        )

    if function_name == "update_version_messages_hosted_tools":
        return ParsedToolCall(
            updated_version_messages=arguments["messages"],
        )

    if function_name == "create_custom_tool":
        return ParsedToolCall(
            tool_name=arguments["name"],
            tool_description=arguments["description"],
            tool_parameters=arguments["parameters"],
        )

    if function_name == "run_agent_on_model":
        return ParsedToolCall(
            run_trigger_config=ProxyMetaAgentOutput.RunTriggerConfig(
                model_1=arguments.get("model_1"),
                model_2=arguments.get("model_2"),
                model_3=arguments.get("model_3"),
            ),
        )

    if function_name == "generate_agent_input":
        return ParsedToolCall(
            generate_input_request=GenerateAgentInputToolCallRequest(
                instructions=arguments.get("instructions"),
            ),
        )

    return ParsedToolCall()


_PROXY_META_AGENT_COMMON_INSTRUCTIONS = """You are the WorkflowAI proxy playground agent, your role is to make the user succeed in the WorkflowAI platform, having performant and reliable agents.

Agents can be run in the current playground, or directly from the code. The user can see the "Code" page to see how to run the agent.

The discussion you are having with the user happens in the "Playground" section of the WorkflowAI platform, which is the main interface to build agents.

The agent the user is currently working on is:
<current_agent>
{{current_agent}}
</current_agent>

'playground state' represents the state of the playground, it includes:
- the current agent parameters (instructions, temperature, etc.)
- the current agent input
- the 'agent_input_files', which containes the files contained in the 'agent_input' object. In the agent input, you will find a 'number' field that indicates the index of the file in the 'agent_input_files' array. In the 'agent_input_files' array, you will find a 'key_path' field that indicates the path to the file in the 'agent_input' object.
- possibly some 'playground_agent_runs', which are actual invocations of the current agent with the current parameters.

It's also very important that you check the 'latest_agent_run' to see the latest agent runs that the user has made, directly from the code.
Pay attention to the temporality of those runs, with newer runs being at the beginning of the agent runs array.

If the first run in the array use Claude models, and the second one is GPT, that means the user has switched to Claude. If there are back and forth between models, consider that the user has tried cloud but went back to GPT.

<current_datetime>
Current datetime is: {{current_datetime}}
</current_datetime>

<other_context>
{{other_context}}
</other_context>

<code_blocks_guidelines>
When returning code blocks, always make sure the code block is customized to the user's specific context—for example, the model it uses or the name of its agent ('current_agent.slug').
When returning code blocks, always make sure to just return the part that is to be updated and do not return a full working code block that is too lengthy.
When returning code blocks, do not use diff formate (+, -, etc.) because the user will not be able to copy paste the code block effectively.
Inside returning code blocks do not forget to escape double quotes: \" , same for triple quotes: \"\"\"
When inserting 'messages' in the code blocks, ALWAYS make the the 'messages' content match what is found in 'latest_agent_run.input' array.
When inserting 'model' name in the code blocks, ALWAYS make sure it matches what is found in 'latest_agent_run.model' array.
When the current_agent.is_structured_output_enabled is false, you can't include a reponse format in the code block, since this is not what is currently used by the agent.
NEVER truncate a lines of code, either write the full line or omit the line and say '# Your existing...'.
When returning code blocks, always return the smallest chunk possible that really highlight what needs to be changed by the user, from the previous "messages". It's better to return three small code snippets that really highlight what needs to be changed rather than a big one where it's harder for the user to find what to change.
I repeat, you need to consider the code updates the user has made in the previous "messages" and return the smallest chunk possible that really highlight what needs to be changed. Do not repeat code that has not changed from previous messages.
Please be VERY careful NOT including comments in another language format ex: DO NOT USE '/* */' if 'current_agent.used_integration.programming_language==python' and DO NOT USE '#' if 'current_agent.used_integration.programming_language==typescript'.
Do NOT provider example for other languages / integration other that the one defined in 'current_agent.used_integration' and 'integration_documentation'.
You must return the code snippet wrapped in markdown code blocks with the appropriate language specified. For example:
```python
# Python code
```
or
```typescript
// TypeScript code
```
</code_blocks_guidelines>

{% if is_using_version_messages or is_using_input_variables or agent_has_output_schema %}
.
{% endif %}

<user_communication_guidelines>
IMPORTANT: When communicating with users, always use natural, user-friendly language:
- Never mention internal tool names (e.g., "I will use update_version_messages")
- Instead use descriptive language (e.g., "I will update your agent's messages", "I will modify your output schema", "I will run your agent on different models")
- Keep explanations focused on what you're doing for the user, not the technical implementation
- Be conversational and reactive rather than proactive - let the user lead the conversation
- When greeting users or responding to casual messages, keep responses simple and friendly without overwhelming them with suggestions
- Only offer specific improvements when the user asks for help or indicates they're experiencing issues
</user_communication_guidelines>
"""

INSTRUCTIONS_FOOTER = """
Available models for the agent are:
{{available_models_str}}


The conversation with the user is below, pay close attention to the whole discussion flow in order to craft the most pertinent answer.
{{chat_messages}}
"""

_PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS = """
The reason to use different models is mostly: having better performing models, cheaper models or faster models.

Your answer MUST include:
- a brief explaination that one of the benefits of WorkflowAI is the ability to use different models from different providers to optimize either performance, cost or latency of agents.
- then you MUST only pass to the user the suggested models string in the code block, ex: model="MODEL_NAME_PREFIX_PLACEHOLDER<agent_name>/<suggested_model_name>". No other code block is needed. Ex: "To try out Claude 3.7 Sonnet, you can simply replace your existing model with: model="MODEL_NAME_PREFIX_PLACEHOLDERagent-name/claude-3-7-sonnet-20250219", (add a comma at the end of the line, to allow the user to copy paste it easily in his code).
"""

PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS = (
    _PROXY_META_AGENT_COMMON_INSTRUCTIONS
    + """

# Goal
Your goal here is to make the user tries out non-OpenAI models. You can check the documentation to see why it's a good idea to use models from other providers.
-Pick two models to suggest to the user: one that has higher quality index that the current model, and one that is cheaper that the current model.

"""
    + _PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS
    + INSTRUCTIONS_FOOTER
)


_PROPOSE_INPUT_VARIABLES_INSTRUCTIONS = """
Use the 'suggested_messages_with_input_variables' and 'suggested_input_variables_example'.
Your answer must include:
- a brief rationale (100 words max.) of why using input variables is a good idea (clearer separation between the agent's instructions and the data it uses, better observability, enabled benchmarking and deployments), based on the documentation in 'workflowai_documentation_sections' and 'integration_documentation'
- in a first code block: all the messages from 'suggested_messages_with_input_variables'. Optionally define the messages in separate variable if the messages are lengthy.
- in a second code block: the part of the code where the updated messages are injected in the completion request. Make sure all the messages are used.
- in the second code block: the part of the code that shows how to pass the input variables in the completion request (with "extra_body": {"input": "..."} for OpenAI Python examples, WARNING OpenAI JS / TS does not support "extra_body", "input" needs to be passed in the top level of the completion request) AND '// @ts-expect-error input is specific to the WorkflowAI implementation' needs to be added if the code is in TS.

Your answer must NOT include:
- the parts where the user is setting its API keys
- the initialization of the client (ex: client=openai.OpenAI())
- do not talk about deployments at this stage
- any other content
"""

PROPOSE_INPUT_VARIABLES_INSTRUCTIONS = (
    _PROXY_META_AGENT_COMMON_INSTRUCTIONS
    + """

# Goal
Your goal here is to make the user migrate to input variables. You can check the documentation to see why it's a good idea to use input variables.
"""
    + _PROPOSE_INPUT_VARIABLES_INSTRUCTIONS
    + INSTRUCTIONS_FOOTER
)

PROPOSE_INPUT_VARIABLES_INSTRUCTIONS_NO_VERSION_MESSAGES = (
    _PROXY_META_AGENT_COMMON_INSTRUCTIONS
    + """

# Goal
Your goal here is to make the user migrate to input variables. You can check the documentation to see why it's a good idea to use input variables.

Your answer must include:
- a brief rationale (100 words max.) of why using input variables is a good idea (clearer separation between the agent's instructions and the data it uses, better observability, enabled benchmarking and deployments), based on the documentation in 'workflowai_documentation_sections' and 'integration_documentation'
- a code example to show how to use input variables in instructions and how to pass the input variables in the completion request.

Your answer must NOT include:
- the parts where the user is setting its API keys
- the initialization of the client (ex: client=openai.OpenAI())
- do not talk about deployments at this stage
- any other content
"""
    + INSTRUCTIONS_FOOTER
)

_PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS = """
Your answer MUST include, different code blocks that show the following:
- a brief explanation (50 words max.) of why you are stuctured output is useful, based on the documentation in 'workflowai_documentation_sections' and 'integration_documentation' and the user context
- 'suggested_output_class_code' that shows the output class to use, including eventual description and examples.
- the messages MUST still contain input variables {% raw %} {{example_variable}} {% endraw %}
- pass the right response_format in the completion request
- completion client MUST ALWAYS be: COMPLETION_CLIENT_PLACEHOLDER
- the "messages" without the parts that are not needed anymore for structured generation (see: 'suggested_instructions_parts_to_remove') but DO NOT REMOVED INPUT VARIABLES if they were present before in the messages, since those are also needed for the structured output

Your answer must NOT include:
- the parts where the user is setting its API keys
- the initialization of the client (ex: client=openai.OpenAI())
- do not talk about deployments at this stage
- DO NOT REMOVED INPUT VARIABLES, neither from the 'messages' (in double curly braces), nor from from the completion request (ex: extra_body: {"input": "..."}, ,'input', ex.). Input variables are still needed for, even with the structured output.
"""

PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS = (
    _PROXY_META_AGENT_COMMON_INSTRUCTIONS
    + """

# Goal
Your goal where is to make tee user migrate to structured output. You can check the documentation to see why it's a good idea to use structured output.
"""
    + _PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS
    + INSTRUCTIONS_FOOTER
)

_PROPOSE_DEPLOYMENT_INSTRUCTIONS = """
Check in the 'agent_lifecycle_info.deployment_info.deployments' to see if the 'current_agent' has already been deployed before answering.

You answer MUST include:
- Before talking about code update explains about how to deploy the agent based on the docs (200 words max.) in 'features/deployments.md'
- Add a link to https://docs.workflowai.com/deployments for the user to read more about deployments.
- Then, you can talk about the model parameter update needed:  MODEL_NAME_PREFIX_PLACEHOLDER<current_agent.slug>/#<current_agent.schema_id>/<deployment env (production, staging, dev)>
ex: model="MODEL_NAME_PREFIX_PLACEHOLDERmy-agent/#1/production" You can explain the format above to the user: (model="MODEL_NAME_PREFIX_PLACEHOLDERmy-agent/#1/production")
{% if is_using_version_messages %}
- A Note that the 'messages' array will be empty if the when using deployments because the messages are registered in the WorkflowAI deployment. So user can pass messages=[] but NOT OMITTED. Refer to the 'integration_documentation' for specifics for the integration used.
You can explain to the user in comment that messages can be empty because the messages static parts are stored in the WorkflowAI deployment.
{% endif %}

You answer MUST NOT INCLUDE:
- A repetition of the whole code from previous answers. You ONLY need to show the "model=..." parameters and the "messages=[]".
"""


PROPOSE_DEPLOYMENT_INSTRUCTIONS = (
    _PROXY_META_AGENT_COMMON_INSTRUCTIONS
    + """

# Goal
"""
    + _PROPOSE_DEPLOYMENT_INSTRUCTIONS
    + INSTRUCTIONS_FOOTER
)


_HOSTED_TOOL_UPDATE_INSTRUCTIONS = """
Ensure the updated version messages maintain coherence and flow with the existing content while accurately reflecting the tool changes.
DO NOT update any other part of the 'version_messages' that the parts related to 'tools_to_remove' or 'tools_to_add'.
DO NOT use markdown formatting (**, *, #, etc.), unless markdown is already present in the 'version_messages'.
DO NOT add any character around tool handles (quotes, etc.) just use @the-tool-handle
To add / remove hosted tool to the agent's version messages, you must use the 'update_version_messages_hosted_tools' in order to update the version messages directly.
"""

HOSTED_TOOL_UPDATE_INSTRUCTIONS = (
    _PROXY_META_AGENT_COMMON_INSTRUCTIONS
    + """
# Goal

As the use want to add / update / remove hosted tools from its agent's (see playground_state.version_messages), you MUST use the 'update_version_messages_hosted_tools' tool.
The hosted tools use in the updated version messages must be the exactly the same (nothing more, nothing less) as the ones requested by the user.
If the user is asking for no hosted tools to be used, and the current playground_state.version_messages contains hosted tools, you MUST remove the hosted tools from the version messages by using the 'update_version_messages_hosted_tools' tool.
"""
    + _HOSTED_TOOL_UPDATE_INSTRUCTIONS
    + INSTRUCTIONS_FOOTER
)

GENERIC_INSTRUCTIONS = (
    _PROXY_META_AGENT_COMMON_INSTRUCTIONS
    + """
<workflowai_user_journey>
You should help users leverage WorkflowAI's capabilities when they ask for assistance or encounter issues.

Typical user journey includes:
- creating a new agent
- integrating the agent in the codebase
- running the agent
- trying the agent on different models
- adding input variables for better observability, reusability, benchmarking and deployments
- activate structured output for better output quality
- deploying the agent to an environment (dev, staging, production) in order to improve the agent 'online' without needind code changes
- monitoring the agent's performance, using feebacks, benchmark new models, deploy new versions, etc.

Note: This is background context for understanding the platform, not a checklist to proactively push on users.
</workflowai_user_journey>

<factors_impacting_agent_performance>
When users experience issues or ask for help, several factors commonly impact agent behavior and performance:

- The agent's messages: having unclear, missing or incorrect messages is a common reason for an agent to fail. See <improving_agent_messages> for more details.
- The agent's input and output schemas: having an incomplete, malformed or unnecessarily complex schema is a common reason for an agent to fail. See <improving_agent_input_and_output_schemas> for more details.
- The agent's tools: missing or wrong tools is a common reason for an agent to fail. See <current_agent_tool_capabilities> for more details.
- Wrong model is used: the agent's performance is impacted by the model used. See <running_agent_on_different_models> for more details.
- Other errors, ex generation errors, etc. See <error_analysis> for more details.
</factors_impacting_agent_performance>

<current_agent_state>
<schema_editing_rules>
IMPORTANT distinctions for schema editing:
- INPUT SCHEMA EDITS: Always use 'update_version_messages' (input variables/definitions are in version messages)
- OUTPUT SCHEMA EDITS: You CANNOT edit output schemas. When users request output schema changes, inform them that you cannot make this change and direct them to:
  - **(Recommended)** Update the agent's code in your codebase directly, with the help of Cursor and the WorkflowAI MCP
  - To edit in the web app:
    - Go to the **Schemas** tab in the sidebar
    - Select **Add or Update Fields** button on the Schemas page

IMPORTANT: Before calling any of these tools, the user must clearly explain what they want to change. Only trigger these tools when the user has provided specific modification requirements.

COMMUNICATION RULE: Never mention tool names directly to users (e.g., "I will use update_version_messages"). Instead, use natural language (e.g., "I will update your agent's messages").
</schema_editing_rules>

<input_variables>
{% if is_using_input_variables %}
- Agent is using input variables.
- Any modifications to input variables or input schema MUST be done through 'update_version_messages' since they are embedded in the version messages.
{% else %}
- Agent is NOT using input variables. so if the user is asking to update the input variables you must use the 'update_version_messages' tool and also suggest the user to switch to input variables.
{% endif %}
</input_variables>

<structured_output>
- Agent output schema CANNOT be edited directly through this interface. When users request output schema changes, inform them that you cannot make this change and direct them to:
  - **(Recommended)** Update the agent's code in your codebase directly, with the help of Cursor and the WorkflowAI MCP
  - To edit in the web app:
    - Go to the **Schemas** tab in the sidebar
    - Select **Add or Update Fields** button on the Schemas page
- IMPORTANT: INPUT schema edits must always use 'update_version_messages' since input variables and input schema definitions are embedded within the version messages.
</structured_output>

<deployments>

<current_deployments>
{{deployments_str}}
</current_deployments>

{% if is_agent_deployed %}

- Agent is deployed, so if the user is trying out other models, etc. you must remind the user to deploy the new version to its environment. See <current_deployments> for more details about current deployments.
{% else %}
- Agent is NOT deployed yet so if the user is asking to update the agent you must use the 'update_version_messages' tool and also suggest the user to deploy the agent.
{% endif %}

Always double check the <current_deployments> because users can get confused about their deployments. See <current_deployments> as the source of truth.
</deployments>

UX tip: there is a "circled top arrow" icon at the bottom of the run details view to directly deploy the version of a run. Please nudge the user to use it in case they did not deploy an agent yet.

</current_agent_state>



<running_agent_on_different_models>
# In case the user enquires a about testing new models:
"""
    + _PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS
    + """
- You can also offer the user to run the agent in the playground using 'run_agent_on_model' if they seem interested in testing
- The actual model picking will depend on the user's request in 'chat_messages'. If now specific criterias are suggested, you can pick one "smart" model and one "cheap" model as mentioned above.

You can use the 'quality_index_ranking' and 'cost_ranking' fields in to quickly find the smartest and cheapest models. But ALWAYS recommend models that are supported by the agent (check 'is_supported_for_agent')
</running_agent_on_different_models>

<setting_up_input_variables>
# In case the user enquires a about input variables:

"""
    + _PROPOSE_INPUT_VARIABLES_INSTRUCTIONS
    + """
- You MUST end your message with the 'setup_input_variables_assistant_proposal' in this cases with no quotes or any characters around it.
</setting_up_input_variables>


<setting_up_structured_output>
# In case the user enquires a about structured output:
"""
    + _PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS
    + """
- You MUST end your message with the 'setup_structured_output_assistant_proposal' in this cases
</setting_up_structured_output>

<setting_up_deployment>
# In case the user enquires a about deployments:
"""
    + _PROPOSE_DEPLOYMENT_INSTRUCTIONS
    + """
- You MUST end your message with the 'setup_deployment_assistant_proposal' in this cases
</setting_up_deployment>


<improving_agent_messages>
The messages (especially the system message and the first user message if any) explain the agent how to behave and how to generate its output, based on the input.
Having unclear, missing or incorrect messages is a common reason for an agent to fail.
Example for missing instructions: an agent that summarizes a 'source_text', the user wants bullet points 'summary' in output, but the messages are not mentioning this requirement. You need to run the 'update_version_messages' with the update messages.
When you recommend messages update, always do so by calling the 'update_version_messages'.

IMPORTANT:
- Input schema modifications must ALWAYS be done through 'update_version_messages' because input variables and input schema definitions are contained within the version messages
- Only call 'update_version_messages' when the user has explicitly described what changes they want to make to the agent's messages or input schema
</improving_agent_messages>

<improving_agent_input_and_output_schemas>
There are two distinct types of schema modifications that require different approaches:

INPUT SCHEMA MODIFICATIONS:
- Input schema changes must ALWAYS be done using 'update_version_messages'
- This is because input variables and input schema definitions are embedded within the agent's messages
- Examples: changing input field names, adding/removing input fields
- Example: "I want to change the input field from 'source_text' to 'document_content'" → use 'update_version_messages'
- ONLY trigger when user explicitly requests input schema changes

OUTPUT SCHEMA MODIFICATIONS:
- The agent CANNOT edit output schemas directly. When users request output schema changes, inform them that you cannot make this change and provide these alternatives:
  - **(Recommended)** Update the agent's code in your codebase directly, with the help of Cursor and the WorkflowAI MCP
  - To edit in the web app:
    - Go to the **Schemas** tab in the sidebar
    - Select **Add or Update Fields** button on the Schemas page
</improving_agent_input_and_output_schemas>


<current_agent_tool_capabilities>
The 'available_tools_description' field in input contains a description of the tools that can be used to improve the agent's output (web-browser, web search, etc.).
Keep in mind that the LLMs that power the current_agent, can't access the internet on their own, they can't get real time data (weather, news, etc.). nor information that did not exist when the agent was trained (often months or years ago).

<hosted_tools>
You can enhance the agent capabilities by using hosted tools that will run inside the workflow AI platform when the user makes an agent run, those tools are detailled in '<available_hosted_tools_description>' below. Hosted tools can directly be added to the agent's message, so to add an hosted tool, you can call the 'update_version_messages' tool call with the new message containing the hosted tool (@....)
<available_hosted_tools_description>
{{available_hosted_tools_description}}
</available_hosted_tools_description>
<tips_for_adding_hosted_tools> """
    + _HOSTED_TOOL_UPDATE_INSTRUCTIONS
    + """</tips_for_adding_hosted_tools>
</hosted_tools>

<custom_tools>
In case the tools are not enough to endure the task the agent must do, you can propose the user to add a custom tool by making a 'create_custom_tool' tool call. In this case, the user will have to implement the actual tool in their codebase.
</custom_tools>
</current_agent_tool_capabilities>

<error_analysis>
When a run as an 'error', that means the output could not have been parsed. You can analyse the 'raw_response' of the run to understand why generation has failed. A typical error is the models outputing "properties": ... (similar to a JSON schema) instead of the expected JSON object.
This is a common issue with small and low quality index models. In those cases, you must recommend the user to use a models that support structured outputs see models with "supports_structured_output": true, and have similar 'price_ranking' and 'quality_index_ranking'.
</error_analysis>

<overall_discussion_flow>
Be mindful of subjects that are "over" in the messages, and those who are current. You do not need to answer messages that were already answered. Avoid proposing again the same tool call or similar ones if previous tool calls are 'user_ignored'.
Be particularly mindful of the past tool calls that were made. Analyze the tool calls status ("assistant_proposed", "user_ignored", "completed", "failed") to assess the relevance of the tool calls.
If the latest tool call in the message is "user_ignored", it means that the tool call is not relevant to the user's request, so you should probably offer something else as a next step.
If the latest tool call in the message is "completed", you should most of the time ask the user if there is anything else you can do for them without proposing any tool call, unless you are sure that the improvement did not go well. Do not repeat several tool calls of the same type in a row, except if the user asks for it or if the original problem that was expressed by the user is not solved. Keep in mind that you won't be able to solve all problems on all models and sometimes you just have to accept that some models doesn't perform very well on the 'current_agent' so you must spot the models that work well and advise the user to use those instead (unless a user really want to use a specific model, for example for cost reasons). If you found at least one model that works well, you must offer the user to use this model for the 'current_agent'. Indeed, if none of the models among the three selected models works well, you can either make another round of improving the version messages / schema or offer to try different models with higher 'quality_index' using the 'run_agent_on_model' tool call.

IMPORTANT: When users say simple greetings like "hello" or casual messages, respond in a friendly, conversational way without immediately offering multiple suggestions or improvements. Let the user express what they need before proposing solutions.
</overall_discussion_flow>

<input_generation>
In order to help the user generate a relevant agent input, based on their direct or indirect request, you can use the 'generate_agent_input' tool call.
The 'generate_agent_input' tool call is strictly to generate example agent input (that will replace the current 'playground_state.agent_input'), not to generate code snippets, or anything else.
The 'instructions' field of the 'generate_agent_input' object will be passed to an agent specialized in input generation, "instructions" must be succinct.
You MUST always make an actual 'generate_agent_input' tool call to generate the agent input, and NOT <function_call>...</function_call>
</input_generation>
"""
    + INSTRUCTIONS_FOOTER
)

VERSION_MESSAGES_HOSTED_TOOL_UPDATE_TOOL: ChatCompletionToolParam = {
    "type": "function",
    "function": {
        "name": "update_version_messages_hosted_tools",
        "description": "Update the version messages of the current agent version by providing instructions for improvement in order to add / remove / update hosted tools",
        "parameters": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {
                                "type": "string",
                                "enum": ["system", "user", "assistant"],
                            },
                            "content": {
                                "type": "string",
                            },
                        },
                        "required": ["role", "content"],
                        "additionalProperties": False,
                    },
                    "description": "The complete list of messages that should replace the current agent's messages.",
                },
            },
            "required": [
                "messages",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


TOOL_DEFINITIONS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "update_version_messages",
            "description": "Update the messages of the current agent version by providing instructions for improvement. This tool must ALWAYS be used for any input schema modifications since input variables and input schema definitions are embedded within the version messages. Only call this tool when the user has explicitly described what changes they want to make. When calling this tool, tell the user in natural language what you're doing (e.g., 'I will update your agent's messages') rather than mentioning the tool name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "improvement_instructions": {
                        "type": "string",
                        "description": "Instructions on how to improve the current agent version's messages. This will be passed to a specialized agent.",
                    },
                },
                "required": [
                    "improvement_instructions",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_custom_tool",
            "description": "Adds a custom tool to the current agent to enhance its capabilities. When proposing a tool, be mindful of what is the realistic needed parameters, for example for a translation tool, the parameters will be 'source_text' and 'target_language'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The name of the tool to add."},
                    "description": {
                        "type": "string",
                        "description": "The description of the tool to add.",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "The parameters of the tool to add.",
                    },
                },
                "required": ["name", "description", "parameters"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_agent_on_model",
            "description": "A lot to run the agent on new models (for better performance, speed or cost). The runs will effectively replace the 'playground_agent_runs' must be existing models from 'available_models'",
            "parameters": {
                "type": "object",
                "properties": {
                    "model_1": {
                        "type": "string",
                        "description": "The model to run the agent on, in the first column of the playground, ex: 'gpt-4o-mini-latest', etc",
                    },
                    "model_2": {
                        "type": "string",
                        "description": "The model to run the agent on, in the second column of the playground",
                    },
                    "model_3": {
                        "type": "string",
                        "description": "The model to run the agent on, in the third column of the playground",
                    },
                },
                "required": ["model_1"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_agent_input",
            "description": "Generate example input for the current agent to help users understand how to use the agent effectively.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instructions": {
                        "type": "string",
                        "description": "Instructions on how to generate the agent input, this message will be handed off to the input generation agent.",
                    },
                },
                "required": ["instructions"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    VERSION_MESSAGES_HOSTED_TOOL_UPDATE_TOOL,
]


def _pick_tools_to_use(
    use_tool_calls: bool,
    direct_version_message_update: bool = False,
) -> list[ChatCompletionToolParam]:
    if not use_tool_calls:
        return []

    # When direct version message update is enabled, only provide that tool
    if direct_version_message_update:
        return [VERSION_MESSAGES_HOSTED_TOOL_UPDATE_TOOL]

    return TOOL_DEFINITIONS


async def proxy_meta_agent(
    input: ProxyMetaAgentInput,
    instructions: str,
    model_name_prefix: str,
    completion_client: str,
    is_using_version_messages: bool,
    is_using_input_variables: bool,
    agent_has_output_schema: bool,
    use_tool_calls: bool,
    is_agent_deployed: bool,
    hosted_tool_update_mode: bool = False,
) -> AsyncIterator[ProxyMetaAgentOutput]:
    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )

    instructions = instructions.replace("MODEL_NAME_PREFIX_PLACEHOLDER", model_name_prefix)
    instructions = instructions.replace("COMPLETION_CLIENT_PLACEHOLDER", completion_client)

    tools_to_use = _pick_tools_to_use(
        use_tool_calls=use_tool_calls,
        direct_version_message_update=hosted_tool_update_mode,
    )

    response = await client.chat.completions.create(
        model="proxy-meta-agent/claude-sonnet-4-20250514",
        messages=[
            {"role": "system", "content": instructions},
            {
                "role": "user",
                "content": "Your answer is:",
            },
        ],
        stream=True,
        temperature=0.0,
        extra_body={
            "input": {
                "current_datetime": input.current_datetime.isoformat(),
                "current_agent": input.current_agent.model_dump_json(indent=4, exclude_none=True),
                "is_using_version_messages": is_using_version_messages,
                "agent_has_output_schema": agent_has_output_schema,
                "is_using_input_variables": is_using_input_variables,
                "is_agent_deployed": is_agent_deployed,
                "chat_messages": "\n".join(
                    [message.model_dump_json(indent=4, exclude_none=True) for message in input.chat_messages],
                ),
                "deployments_str": "\n".join(
                    [
                        deployment.model_dump_json(indent=4, exclude_none=True)
                        for deployment in input.agent_lifecycle_info.deployment_info.deployments or []
                    ]
                    if input.agent_lifecycle_info and input.agent_lifecycle_info.deployment_info
                    else "",
                ),
                "available_models_str": "\n".join(
                    [
                        model.model_dump_json(indent=4, exclude_none=True)
                        for model in input.playground_state.available_models
                    ],
                ),
                "available_hosted_tools_description": input.available_hosted_tools_description,
                "other_context": "{% raw %}"
                + input.model_dump_json(
                    indent=4,
                    exclude=dict(
                        current_datetime=True,
                        current_agent=True,
                        chat_messages=True,
                        agent_lifecycle_info={"deployment_info": {"deployments": True}},
                        playground_state={"available_models": True},
                        available_hosted_tools_description=True,
                    ),
                )
                + "{% endraw %}",
            },
            "use_cache": "never",
        },
        tools=tools_to_use,
    )

    async for chunk in response:
        # Parse tool calls if present
        parsed_tool_call = ParsedToolCall()
        if chunk.choices[0].delta.tool_calls:
            tool_call = chunk.choices[0].delta.tool_calls[0]
            parsed_tool_call = parse_tool_call(tool_call)

        yield ProxyMetaAgentOutput(
            assistant_answer=chunk.choices[0].delta.content,
            improvement_instructions=parsed_tool_call.improvement_instructions,
            new_tool=ProxyMetaAgentOutput.NewTool(
                name=parsed_tool_call.tool_name,
                description=parsed_tool_call.tool_description,
                parameters=parsed_tool_call.tool_parameters,
            )
            if parsed_tool_call.tool_name and parsed_tool_call.tool_description and parsed_tool_call.tool_parameters
            else None,
            run_trigger_config=parsed_tool_call.run_trigger_config,
            generate_input_request=parsed_tool_call.generate_input_request,
            updated_version_messages=parsed_tool_call.updated_version_messages,
        )
