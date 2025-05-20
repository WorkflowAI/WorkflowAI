import datetime
import os
from typing import Any, AsyncIterator, Literal, Self

from openai import AsyncOpenAI
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


class EditSchemaStructureToolCallRequest(BaseToolCallRequest):
    edition_request_message: str | None = Field(
        default=None,
        description="The message to edit the agent schema with.",
    )


class EditSchemaDescriptionAndExamplesToolCallRequest(BaseToolCallRequest):
    description_and_examples_edition_request_message: str | None = Field(
        default=None,
        description="The message to edit the agent schema's fields description and examples with.",
    )


class EditSchemaToolCallResult(BaseResult, EditSchemaStructureToolCallRequest):
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

    agent_instructions: str | None = Field(
        default=None,
        description="The instructions for the agent",
    )
    agent_temperature: float | None = Field(
        default=None,
        description="The temperature for the agent",
    )

    class PlaygroundModel(BaseModel):
        id: str = Field(
            description="The id of the model",
        )
        name: str
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
        context_window_tokens: int = Field(
            description="The context window of the model in tokens",
        )
        is_not_supported_reason: str | None = Field(
            default=None,
            description="The reason why the model is not supported for the current agent",
        )
        estimate_cost_per_thousand_runs_usd: float | None = Field(
            default=None,
            description="The estimated cost per thousand runs in USD",
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

    messages: list[ProxyMetaAgentChatMessage] = Field(
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

    available_tools_description: str = Field(
        description="The description of the available tools, that can be potientially added to the 'agent_instructions' in order to improve the agent's output",
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


_PROXY_META_AGENT_COMMON_INSTRUCTIONS = """Your WorkflowAI proxy playground agent's role is to make the user succeed in the WorkflowAI platform, having performant and reliable agents.


The discussion you are having with the user happens in the "Playground" section of the WorkflowAI platform, which is the main interface to build agents.

It's very important that you check the 'latest_agent_run' to see the latest agent runs that the user has made.
Pay attention to the temporality of those runs, with newer runs being at the beginning of the agent runs array.

If the first run in the array use Claude models, and the second one is GPT, that means the user has switched to Claude. If there are back and forth between models, consider that the user has tried cloud but went back to GPT.

# Code blocks guidelines
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
"""

_PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS = """
Your goal here is to make the user tries out non-OpenAI models. You can check the documentation to see why it's a good idea to use models from other providers.
The reason to use different models is mostly: having better performing models, cheaper models or faster models.

Your answer MUST include:
- a brief explaination that one of the benefits of WorkflowAI is the ability to use different models from different providers to optimize either performance, cost or latency of agents.
- Pick two models to suggest to the user: one that has higher quality index that the current model, and one that is cheaper that the current model.
- then you MUST only pass to the user the suggested models string in the code block, ex: model="<agent_name>/<suggested_model_name>". No other code block is needed. Ex: "To try out Claude 3.7 Sonnet, you can simply replace your existing model with: model="agent-name/claude-3-7-sonnet-20250219", (add a comma at the end of the line, to allow the user to copy paste it easily in his code).
"""

PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS = f"""
{_PROXY_META_AGENT_COMMON_INSTRUCTIONS}

# Goal
{_PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS}
"""

_PROPOSE_INPUT_VARIABLES_INSTRUCTIONS = """Your goal here is to make the user migrate to input variables. You can check the documentation to see why it's a good idea to use input variables.

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

PROPOSE_INPUT_VARIABLES_INSTRUCTIONS = f"""
{_PROXY_META_AGENT_COMMON_INSTRUCTIONS}

# Goal
{_PROPOSE_INPUT_VARIABLES_INSTRUCTIONS}
"""

_PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS = """
Your goal here is to make the user migrate to structured output. You can check the documentation to see why it's a good idea to use structured output.

Your answer MUST include, different code blocks that show the following:
- a brief explanation (50 words max.) of why you are stuctured output is useful, based on the documentation in 'workflowai_documentation_sections' and 'integration_documentation' and the user context
- 'suggested_output_class_code' that shows the output class to use, including eventual description and examples.
- when needed, update the 'client.chat.completions.create' to 'client.beta.chat.completions.parse' WARNING: for OpenAI SDK, the method to use for structured output is 'client.beta.chat.completions.parse' NOT 'client.chat.completions.create' NOR 'client.chat.completions.parse'.
- pass the right response_format in the completion request
- the "messages" without the parts that are not needed anymore for structured generation (see: 'suggested_instructions_parts_to_remove') but DO NOT REMOVED INPUT VARIABLES if they were present before in the messages, since those are also needed for the structured output

Your answer must NOT include:
- the parts where the user is setting its API keys
- the initialization of the client (ex: client=openai.OpenAI())
- do not talk about deployments at this stage
- DO NOT REMOVED INPUT VARIABLES, neither from the 'messages' (in double curly braces), nor from from the completion request (ex: extra_body: {"input": "..."}, ,'input', ex.). Input variables are still needed for, even with the structured output.
"""

PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS = f"""
{_PROXY_META_AGENT_COMMON_INSTRUCTIONS}

# Goal
{_PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS}
"""

_PROPOSE_DEPLOYMENT_INSTRUCTIONS = """
Check in the 'agent_lifecycle_info.deployment_info.deployments' to see if the 'current_agent' has already been deployed before answering.

You answer MUST include:
- Before talking about code update explains about how to deploy the agent based on the docs (200 words max.) in 'features/deployments.md'
- Add a link to https://docs.workflowai.com/features/deployments for the user to read more about deployments.
- Then, you can talk about the model parameter update needed:  <current_agent.slug>/#<current_agent.schema_id>/<deployment env (production, staging, dev)>
ex: model="my-agent/#1/production" You can explain the format above to the user: (model="my-agent/#1/production")
- A Note that the 'messages' array will be empty if the when using deployments because the messages are registered in the WorkflowAI deployment. So user can pass messages=[] but NOT OMITTED. Refer to the 'integration_documentation' for specifics for the integration used.
You can explain to the user in comment that messages can be empty because the messages static parts are stored in the WorkflowAI deployment.

You answer MUST NOT INCLUDE:
- A repetition of the whole code from previous answers. You ONLY need to show the "model=..." parameters and the "messages=[]".
"""

PROPOSE_DEPLOYMENT_INSTRUCTIONS = f"""
{_PROXY_META_AGENT_COMMON_INSTRUCTIONS}

# Goal
{_PROPOSE_DEPLOYMENT_INSTRUCTIONS}
"""

GENERIC_INSTRUCTIONS = f"""
{_PROXY_META_AGENT_COMMON_INSTRUCTIONS}

<test_new_models>
# In case the user enquires a about testing new models:
{_PROPOSE_NON_OPENAI_MODELS_INSTRUCTIONS}
You MUST end your message with the 'try_other_models_assistant_proposal' in this cases with no quotes or any characters around it.
</test_new_models>

<setup_input_variables>
# In case the user enquires a about input variables:
{_PROPOSE_INPUT_VARIABLES_INSTRUCTIONS}
You MUST end your message with the 'setup_input_variables_assistant_proposal' in this cases with no quotes or any characters around it.
</setup_input_variables>


<setup_structured_output>
# In case the user enquires a about structured output:
{_PROPOSE_STRUCTURED_OUTPUT_INSTRUCTIONS}
You MUST end your message with the 'setup_structured_output_assistant_proposal' in this cases
</setup_structured_output>

<setup_deployment>
# In case the user enquires a about deployments:
{_PROPOSE_DEPLOYMENT_INSTRUCTIONS}
You MUST end your message with the 'setup_deployment_assistant_proposal' in this cases
</setup_deployment>


# All other cases:
You must answer users' questions, but what you know from all the documentation in 'workflowai_documentation_sections' and 'integration_documentation' is not enough to answer the question.
"""


async def proxy_meta_agent(input: ProxyMetaAgentInput, instructions: str) -> AsyncIterator[ProxyMetaAgentOutput]:
    client = AsyncOpenAI(
        api_key=os.environ["WORKFLOWAI_API_KEY"],
        base_url=f"{os.environ['WORKFLOWAI_API_URL']}/v1",
    )
    response = await client.chat.completions.create(
        model="proxy-meta-agent/claude-3-7-sonnet-20250219",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": "{% raw %}" + input.model_dump_json() + "{% endraw %}"},
        ],
        stream=True,
        temperature=0.0,
    )

    async for chunk in response:
        yield ProxyMetaAgentOutput(assistant_answer=chunk.choices[0].delta.content)
