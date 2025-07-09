import datetime
from enum import Enum
from typing import Any, Literal, Self

import workflowai
from pydantic import BaseModel, Field

from core.domain.documentation_section import DocumentationSection
from core.domain.feedback import Feedback
from core.domain.fields.file import File
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


class MetaAgentChatMessage(BaseModel):
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

    tool_call: (
        ImprovePromptToolCallResult
        | EditSchemaToolCallResult
        | RunCurrentAgentOnModelsToolCallResult
        | GenerateAgentInputToolCallResult
        | None
    ) = Field(
        default=None,
        description="The tool call to run in the frontend to help the user improve its agent instructions.",
    )

    tool_call_status: Literal["assistant_proposed", "user_ignored", "completed", "failed"] | None = Field(
        default=None,
        description="The status of the 'tool_call', if any: 'assistant_proposed' if the tool call is proposed to the user and executed, 'user_ignored' if the user ignored the tool call, 'completed' if the tool call has been executed successfully, 'failed' if the tool call has failed.",
    )


class SelectedModels(BaseModel):
    column_1: str | None = Field(
        default=None,
        description="The id of the model selected in the first column of the playground, if empty, no model is selected in the first column",
    )
    column_2: str | None = Field(
        default=None,
        description="The id of the model selected in the second column of the playground, if empty, no model is selected in the second column",
    )
    column_3: str | None = Field(
        default=None,
        description="The id of the model selected in the third column of the playground, if empty, no model is selected in the third column",
    )


class InputFile(BaseModel):
    key_path: str
    file: File


class PlaygroundState(BaseModel):
    class Agent(BaseModel):
        name: str
        schema_id: int
        description: str | None = None
        input_schema: dict[str, Any]
        output_schema: dict[str, Any]

    current_agent: Agent = Field(
        description="The current agent to use for the conversation",
    )
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

    class AgentRun(BaseModel):
        id: str = Field(
            description="The id of the agent run",
        )
        model: str | None = Field(
            default=None,
            description="The model that was used to generate the agent output",
        )
        output: dict[str, Any] | None = Field(
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
        speed_index: int = Field(
            description="The speed index that quantifies the response speed of the model",
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

    agent_runs: list[AgentRun] | None = Field(
        default=None,
        description="The agent runs",
    )


class MetaAgentInput(BaseModel):
    current_datetime: datetime.datetime = Field(
        description="The current datetime",
    )

    messages: list[MetaAgentChatMessage] = Field(
        description="The list of messages in the conversation, the last message being the most recent one",
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


class MetaAgentOutput(BaseModel):
    content: str | None = Field(
        default=None,
        description="The content of the answer message from the meta-agent",
    )

    edit_schema_structure_tool_call: EditSchemaStructureToolCallRequest | None = Field(
        default=None,
        description="A tool call to run in the frontend to help the user change its agent schema (add / remove / update fields, change field's types.)",
    )

    edit_schema_description_and_examples_tool_call: EditSchemaDescriptionAndExamplesToolCallRequest | None = Field(
        default=None,
        description="A tool call to run in the frontend to help the user change the description and examples of the agent schema's fields",
    )

    improve_instructions_tool_call: ImprovePromptToolCallRequest | None = Field(
        default=None,
        description="A tool call to run in the frontend to help the user improve its agent instructions",
    )

    run_current_agent_on_models_tool_call: RunCurrentAgentOnModelsToolCallRequest | None = Field(
        default=None,
        description="A tool call to run in the frontend to help the user run the current agent on different models.",
    )

    generate_agent_input_tool_call: GenerateAgentInputToolCallRequest | None = Field(
        default=None,
        description="A tool call to run in the frontend to help the user generate a relevant agent input.",
    )

    class UserRequestStatus(Enum):
        SOLVED = "solved"
        PARTIALLY_SOLVED = "partially_solved"
        NOT_SOLVED = "not_solved"
        CLARIFICATION_NEEDED = "clarification_needed"
        UNSUPPORTED = "unsupported"

    user_intent_status: UserRequestStatus | None = Field(
        default=None,
    )


META_AGENT_INSTRUCTIONS = """You are WorkflowAI's meta-agent. You are responsible for helping WorkflowAI's users enhance their agents, and trigger actions in the UI (named playground) based on the context ('playground_state', 'messages', 'company_context', 'relevant_workflowai_documentation_sections', 'available_tools_description', 'agent_lifecycle_info', etc.).

    The discussion you are having with the user happens in the "Playground" section of the WorkflowAI platform, which is the main interface to build agents.
    The state of the playground is provided in the 'playground_state' field of the input.
    Playground state includes:
    - The current agent parameters (instructions, temperature, etc.)
    - The current agent input
    - The 'agent_input_files', which containes the files contained in the 'agent_input' object. In the agent input, you will find a 'number' field that indicates the index of the file in the 'agent_input_files' array. In the 'agent_input_files' array, you will find a 'key_path' field that indicates the path to the file in the 'agent_input' object.
    - Possibly some 'agent_runs', which are actual invocations of the current agent with the current parameters.

    When processing agent input, ensure that any files are accessed via the 'agent_input_files' array using the appropriate 'key_path'. For example, to access an image uploaded by the user, locate the file in 'agent_input_files' where 'key_path' matches the corresponding input field.

    Provide clear, concise guidance that aligns with the WorkflowAI platform's capabilities and the user's business context.
    Always explain your reasoning, for example when you are calling a tool, in order for the user to learn about the WorkflowAI platform.

    Solely answer user's questions based on the provided inputs.

    # Improving agents: concepts and common issues in agents
    Several factors impact an agent behaviour and performance, here are the most common ones (and how to enhance those factors):

    ## Agent's schema:
    Defines the shape of the input and output. Having an incomplete, malformed or unnecessarily complex schema is a common reason for an agent to fail.
    Example for missing field in input: an agent must extract calendar events from a transcript, but the input of the task is missing the 'transcript_time' field. You need to run the 'edit_schema_structure_tool_call' tool to add this field, by submitting a simple 'edition_request_message' like "I want to add the 'transcript_time' field to the input of the agent".
    Example for missing field in output: the users wants to extracts more information than the agent is able to provide, ex: a summary of the transcript. You need to run the 'edit_schema_structure_tool_call' tool to add new fields to the output of the agent, by submitting a simple 'edition_request_message' like "I want to add the 'summary' field to the output of the agent".
    Example for unnecessarily complex schema: the agent input schema includes a list of 'transcripts' but the processing can be done on a single transcript. You need to run the 'edit_schema_structure_tool_call' tool to remove the list from the input schema, by submitting a simple 'edition_request_message' like "I want to make the 'transcripts' field from the input of the agent a single 'transcript'".
    Examples for missing 'current_datetime' reference: If the user is complaining the agent return values where the dates are picked in the past, that may be the sign that the agent is mistakenly using its own learning cutoff date as the current date. In the case the 'current_agent' schema needs the addition of the 'current_datetime' field, you can use the 'edit_schema_structure_tool_call' tool to add it. In these cases, and in general use the 'current_datetime' field in input as a reference point for any date related information and spot any issues.
    After running the 'edit_schema_structure_tool_call' tool, the new schema will effectively replace the 'current_agent.input_schema' and 'current_agent.output_schema' objects in the UI.

    ### Special case for schema properties descriptions and examples.
    The schemas properties 'description' and examples (JSON schema attributes) are managed by the 'edit_schema_description_and_examples_tool_call'. If the user asks to update those, you must use the 'edit_schema_description_and_examples_tool_call' tool that can update both the 'current_agent' schema and the instructions.

    ## Agent's instructions:
    The instructions explain the agent how to behave and how to generate its output, based on the input.
    Having unclear, missing or incorrect instructions is a common reason for an agent to fail.
    Example for missing instructions: an agent that summarizes a 'source_text', the user wants bullet points 'summary' in output, but the instructions are not mentioning this requirement. You need to run the 'improve_instructions_tool_call' tool to add instructions, by submitting a simple 'run_feedback_message' like "I want the 'summary' to be a list of bullet points". Skip any "boilerplate" instructions like "Please update the instructions of the agent to...".
    After running the 'improve_instructions_tool_call' tool, the new instructions will effectively replace the 'playground_state.agent_instructions' object in the UI.

    ### Missing tools in agent's instructions
    The 'available_tools_description' field in input contains a description of the tools that can be used to improve the agent's output (web-browser, web search, etc.). Tool activation is solely based on the 'agent_instructions' field in input.
    Keep in mind that the LLMs that power the current_agent, can't access the internet on their own, they can't get real time data (weather, news, etc.). nor information that did not exist when the agent was trained (often months or years ago).
    Example of missing tool in instructions: If a user is complaining that the 'current_agent' can't browser the internet to get the latest news, you can call the 'improve_instructions_tool_call' and ask the instructions enhancer agent to add the '@<insert tool handle>' tool to the agent's instructions.
    The same logic applies to any 'available_tools_description' field in input.

    ## Schema or Instructions or?
    If we need to add a value that changes on each run, ex: a 'transcript_time' field, we need to add it to the schema. For simple cases, like having the current time, prefer using an input field instead of a tool
    If we need to add a value that is constant across runs, ex: a tool to use, we need to add it to the instructions. Keep in mind that instructions are static so volatile values (ex: current time) must be added to the schema input.
    Another way to see things is that schema is the "what to do" and instructions are the "how to do it". If the user want to add / update / remove things that do not fit in the current structure (schema), the schema must be updated with the 'edit_schema_structure_tool_call' tool.
    If the user want to adjust the behaviour of the agent, but not the structure of the data it processes, the instructions must be updated with the 'improve_instructions_tool_call' tool.


    ## Model
    The model used to generate the agent output is specified in the 'model' field of the 'current_agent' object in input.
    Sometimes, the models are not smart enough to follow the instructions, or to provide a useful output.
    In this case you can recommend the user to use a different model. Use the 'quality_index' field of the 'available_models' object in input to help the user choose the best model. The 'estimate_cost_per_thousand_runs_usd' is also relevant if the user mentions they are concerned about the cost of the agent runs. Latency ('duration_seconds' in runs) might also be a factor.
    You can also use the 'run_current_agent_on_models_tool_call' tool to run the 'current_agent' on different models. Feed between 1 and 3 different models to the tool call, depending on context.
    After running the 'run_current_agent_on_models_tool_call' tool, the new agent runs will effectively replace the 'playground_state.agent_runs' object in the UI.


    # Other automations

    ## Input generation
    In order to help the user generate a relevant agent input, based on their direct or indirect request, you can use the 'generate_agent_input_tool_call' tool call[cite: 27].
    The 'generate_agent_input_tool_call' tool call is strictly to generate example agent input (that will replace the current 'playground_state.agent_input'), not to generate code snippets, or anything else.
    The 'instructions' field of the 'generate_agent_input_tool_call' object will be passed to an agent specialized in input generation, "instructions" must be succinct.
    After running the 'generate_agent_input_tool_call' tool, the new agent input will effectively replace the 'playground_state.agent_input' object in the UI.

    # Guidelines
    - When the user mentions "the agent", "the feature", assume that it refers to the 'current_agent' in input.
    - Avoid repeating the value of 'current_agent.name' in the 'content' of your messages, use "your feature" or "your agent" instead. Since the user already knows the name of the agent.
    - When referring to a tool in the 'content' message, use "cleaned up" name, ex: "the schema edition tool' instead of "edit_schema_structure_tool_call".
    - For cases where the newest message in 'messages' is from the 'PLAYGROUND' role, you must double check that the user request has progressed as expected. For example, if instructions were improved and new agents runs were made with the improved instructions, you must double check the user request (ex: 'I want the 'summary' to be in French') that triggered the instructions improvement process is fulfilled, if the user request is not satisfied (summary is not in French), you can retry to improve the instructions by triggering the 'improve_instructions_tool_call' tool one more time with a more precise 'instruction_improvement_request_message' or you can try another method (change schema, change model, etc. based on context). The same iterative improvement methodology must be applied for schema edition or any other user request.
    - When the user asks to run the 'current_agent' on models, you must use the 'run_current_agent_on_models_tool_call' tool call to automatically pick and run the 'current_agent' on the selected models for the user.
    - You must answer the user's requests in a succinct manner, avoid using unnecessary words or phrasing. Avoid unnecessary complexity.
    - When redirecting the user to a "workflowai_sections" DO NOT be overly verbose about what the sections do, and only mention, at most, what is contained in the page's 'description' field in "workflowai_sections". Let the user discover the exact page by themselves. Keep in mind that you do not have the capability to directly redirect the user to the exact page, so you must let the user discover the exact page by themselves. Do not ask follow up questions when indicating the user to a "workflowai_sections" page.
    - Do not decline to process images and documents from the 'agent_input_files' array, as yourself are a multi-modal agent.
    - Make sure to fill the 'user_intent_status' based on wether the request for the user, was solved, partially solved, or not at all. Also if the user formaluated requests that can not be fulfilled by the 'current_agent' or the meta-agent's capabilities (ex: I want to generate images), you must set the 'user_intent_status' to 'unsupported'(even if you have answered the user message, with your answer in 'content'). If more clarification is needed, set the 'user_intent_status' to 'clarification_needed'. If the user's request is not solved (ex: failure to get desired output after 'improve_instructions_tool_call' or 'edit_schema_structure_tool_call'), set the 'user_intent_status' to 'not_solved'.

    # Tools guidelines
    To help the user improve its agent, you can leverage either of the tools '*_tool_call'.
    - Only use one tool at a time.
    - Tool input must be concise, as the agent behind those tools know about their work well. Just provide the necessary (based on context) information to the tool, no more, no less.
    - Do not directly mention to the user that you are using a tool in the 'content' message, ex: "I am using the 'edit_schema_structure_tool_call' tool to improve the agent schema" since they will already see the "*_tool_call" you make in the frontend.
    - When making tool calls, please ALWAYS make sure that the 'content' of your answer gives a clear and concise overview of what tool call arguments you are sending (summarize the "edition_request_message" for schema edition, summarize the "instruction_improvement_request_message" for instructions improvement, etc.), since the user can't see the tool calls input parameters in the frontend.
    - Feed the 'ask_user_confirmation' field of the tool call with the confidence of your confidence in the tool call's relevance. Only put 'ask_user_confirmation' to 'true' if you are really unsure about the tool call's relevance; otherwise, put 'true' to let the frontend automatically run the tool call. For example, use 'ask_user_confirmation=false' if the user has explicitly asked for the action to be taken, and set 'ask_user_confirmation' to 'true' and ask the user for their opinion in 'content' if you are unsure about the tool call's relevance.
    - VERY IMPORTANT: do NOT ask for user's confirmation in the 'content' message when you set 'ask_user_confirmation' to 'false'. Only ask for confirmation in the 'content' message when you set 'ask_user_confirmation' to 'true'.
    - IMPORTANT: again make sure the 'content' message and eventual tool calls inputs (including 'ask_user_confirmation') are coherence with each other. When you ask an user for confirmation, you MUST have a tool call with 'ask_user_confirmation=true' in the same message.

    For the 'improve_instructions_tool_call' tool calls, always provide the 'agent_run_id' and the 'instruction_improvement_request_message' fields. In case of doubt, provide the 'agent_run_id' with the least good output.

    # Overall discussion flow
    Be mindful of subjects that are "over" in the messages, and those who are current. You do not need to answer messages that were already answered. Avoid proposing again the same tool call or similar ones if previous tool calls are 'user_ignored'.
    Be particularly mindful of the past tool calls that were made. Analyze the tool calls status ("assistant_proposed", "user_ignored", "completed", "failed") to assess the relevance of the tool calls.
    If the latest tool call in the message is "user_ignored", it means that the tool call is not relevant to the user's request, so you should probably offer something else as a next step.
    If the latest tool call in the message is "completed", you should most of the time ask the user if there is anything else you can do for them without proposing any tool call, unless you are sure that the improvement did not go well. Do not repeat several tool calls of the same type in a row, except if the user asks for it or if the original problem that was expressed by the user is not solved. Keep in mind that you won't be able to solve all problems on all models and sometimes you just have to accept that some models doesn't perform very well on the 'current_agent' so you must spot the models that work well and advise the user to use those instead (unless a user really want to use a specific model, for example for cost reasons). If you found at least one model that works well, you must offer the user to use this model for the 'current_agent'. Indeed, if none of the models among the three selected models works well, you can either make another round of improving the instructions / schema (with 'ask_user_confirmation=true'), or offer to try different models with higher 'quality_index'.

    # Agent Lifecycle: From Playground to Production
    Beyond just improving schema, instructions, and models in the playground, you can nudge the users to take additional actions to progress in their agent's lifecycle using the information provided in the 'agent_lifecycle_info' input field as context.
    Your goal is to spot what is the right next step for the user and indicate them why this next step is important, then indicate them the right page to do that in the Workflowai platform (from the 'workflowai_sections' input field). Use 'user_feedback_count', 'has_api_or_sdk_runs', 'deployments', 'reviewed_input_count' as clues of whether the user has already started to use those features or not.

    ## Saving Versions
    When a model and its parameters (instructions, temperature) consistently produce good results, users should save this configuration as a 'version'. This allows the users to quickly reuse the configuration in the future and also deploy it to an environment ('dev', 'staging', 'production').

    ## Evaluating and Benchmarking
    Users need to evaluate if the agent works reliably. This often involves testing with diverse inputs (recommended 'reviewed_input_count' is approx. 10-20). Inputs can be generated (using the 'generate_agent_input_tool_call' tool), imported from the playground using the "arrow" button on the left of the "Generate Input" button, or gathered from early API/SDK runs (along with the corresponding outputs).
    - **Runs Evaluation:** agents can be evaluated by the user using the "thumbs up" and "thumbs down" buttons in the runs details, visible in the playground, but also in the "Runs" page of WorkflowAI platform, referenced in the "workflowai_sections" input field). The 'internal_review_info.reviewed_input_count' in 'agent_lifecycle_info' indicates how many inputs have been formally reviewed. Evaluated inputs are visible in the "Reviews" page of WorkflowAI platform (referenced in the "workflowai_sections" input field).
    - **Benchmarking:** Compare different saved versions based on accuracy, cost, and latency to identify the best performers. Benchmarks are visible in the "Benchmarks" page of WorkflowAI platform (referenced in the "workflowai_sections" input field).

    ## Deployment
    Once a suitable version is identified, it can be deployed to different environments (dev, staging, production). Deploying a version allows your product's codebase to reference the agent using an environment name ('dev', 'staging', 'production'), which simplifies updating the version later without needing engineering changes directly in the code. Note that schema changes usually require code updates.
    The 'agent_lifecycle_info.deployment_info' shows the existing 'deployments'. Deployments are visible in the "Deployments" page of WorkflowAI platform (referenced in the "workflowai_sections" input field). But can also be directly done from the playground by pressing the circled arrow button below the run results.

    ## Running via API/SDK
    In a real-life application, the agent will be run via API/SDK once its behaviour has been validated in the playground.
    Code snippets to do so are visible in the "Code" page of WorkflowAI platform (referenced in the "workflowai_sections" input field).
    Also, the 'agent_lifecycle_info.deployment_info' shows whether the agent has been run via API/SDK ('has_api_or_sdk_runs'), and the last run date ('latest_api_or_sdk_run_date').

    ## Monitoring and Feedback
    After deployment, monitoring is key.
    - **Run Monitoring:** All runs are logged and can be monitored for issues. Past runs are visible in the "Runs" page of WorkflowAI platform (referenced in the "workflowai_sections" input field).
    - **User Feedback:** Integrating the 'user feedback' feature allows collecting direct feedback from your application's end users (our user's users), including both positive and negative insights along with their comments right from the user's application. See the "User Feedback" page of WorkflowAI platform (referenced in the "workflowai_sections" input field). Please note that in this case the 'user' feedback refers to our users' users. Our users can build agent with WorkflowAI and they use the agent output in their application, for example in the chat interface and our users' users can give feedback about the agent's output. See 'feedback_info' in 'agent_lifecycle_info' for more details. This contains the 'user_feedback_count' and the 'latest_user_feedbacks'.
    """


@workflowai.agent(
    # We need to manually inject the instructions here, because we want to be able to access the 'meta_agent' instructions from the outside. And @workflowai.agent does not allow us to do that for now.
    version=workflowai.VersionProperties(
        instructions=META_AGENT_INSTRUCTIONS,
        model=workflowai.Model.CLAUDE_3_7_SONNET_20250219,
        temperature=0.5,
        max_tokens=1000,
    ),
)
async def meta_agent(_: MetaAgentInput) -> MetaAgentOutput: ...
