import logging
import os
import uuid
from typing import Dict, List, Literal, Optional, TypedDict

from fastmcp import FastMCP
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

mcp = FastMCP("WorkflowAI")

# Setup WorkflowAI client
client = OpenAI(
    base_url="https://run-preview.workflowai.com/v1",
    api_key=os.getenv("WORKFLOWAI_API_KEY", "wai-mcp-demo"),
)


class Message(TypedDict):
    id: str
    role: Literal["user", "assistant"]
    content: str
    parent_id: Optional[str]


# In-memory conversation storage
conversation_storage: Dict[str, Message] = {}


def store_message(
    message_id: str,
    role: Literal["user", "assistant"],
    content: str,
    parent_id: Optional[str] = None,
) -> None:
    """Store a message in the conversation storage."""
    conversation_storage[message_id] = {
        "id": message_id,
        "role": role,
        "content": content,
        "parent_id": parent_id,
    }
    logger.info("Message stored", extra={"message_id": message_id, "role": role, "parent_id": parent_id})


def get_conversation_messages(reply_to_message_id: Optional[str]) -> List[Message]:
    """
    Get conversation history by following the parent chain.
    Returns list of messages in chronological order (oldest to newest).
    """
    if not reply_to_message_id or reply_to_message_id not in conversation_storage:
        return []

    # Build the chain by following parent_id backwards
    chain: List[Message] = []
    current_id = reply_to_message_id

    while current_id and current_id in conversation_storage:
        message = conversation_storage[current_id]
        chain.append(message)
        current_id = message["parent_id"]

    # Reverse to get chronological order (oldest first)
    chain.reverse()

    logger.info(
        "Conversation messages retrieved",
        extra={"message_count": len(chain), "reply_to_id": reply_to_message_id},
    )
    return chain


# https://gofastmcp.com/servers/tools
@mcp.tool
async def send_message(message: str, reply_to_message_id: str | None = None) -> dict[str, str]:
    # Note: Neon formats the MCP tool description using HTML-like tags for sections such as <use_case>, <workflow>, <important_notes>, <example>, <next_steps>, and <error_handling>.

    # <use_case>
    # Describe what this tool does and its supported operations
    # </use_case>
    #
    # <workflow>
    # Outline the step-by-step process the tool follows
    # </workflow>
    #
    # <important_notes>
    # Critical requirements and actions that must be taken after using this tool
    # </important_notes>
    #
    # <example>
    # Provide concrete examples of how to use this tool and expected outputs
    # </example>
    #
    # <next_steps>
    # Define what actions should be taken after tool execution
    # <response_instructions>
    # Guidelines for formatting responses to the client
    # <do_not_include>
    # Specify what technical details to avoid in responses
    # </do_not_include>
    # </response_instructions>
    # </next_steps>
    #
    # <error_handling>
    # Define how errors should be handled, including retry logic and failure responses
    # </error_handling>

    # Preview of actual description:
    # description: `
    # <use_case>
    #   This tool performs database schema migrations by automatically generating and executing DDL statements.
    #   Supported operations include CREATE (add columns, create tables, add constraints), ALTER (modify column types, rename columns, add/modify indexes and foreign keys), and DROP (remove columns/tables/constraints).
    #   The tool parses your request, generates SQL, executes in a temporary branch, and verifies changes before applying to main.
    #   Project ID and database name are auto-extracted; defaults are used if not provided.
    # </use_case>
    #
    # <workflow>
    #   1. Creates a temporary branch
    #   2. Applies the migration SQL in that branch
    #   3. Returns migration details for verification
    # </workflow>
    #
    # <important_notes>
    #   After executing this tool, you MUST:
    #   1. Test the migration in the temporary branch using the `run_sql` tool
    #   2. Ask for confirmation before proceeding
    #   3. Use `complete_database_migration` tool to apply changes to main branch
    # </important_notes>
    #
    # <example>
    #   For a migration like:
    #   ```sql
    #   ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
    #   ```
    #   You should test it with:
    #   ```sql
    #   SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'last_login';
    #   ```
    #   Use `run_sql` to test the migration in the temporary branch.
    # </example>
    #
    # <next_steps>
    #   1. Use `run_sql` to verify changes on temporary branch
    #   2. Respond to the client with confirmation and ask for migration commit approval, including all required fields (Migration ID, Temporary Branch Name, Temporary Branch ID, Migration Result). Use placeholders if any field is missing.
    #   3. If approved, use `complete_database_migration` tool with the `migration_id`
    #   <response_instructions>
    #     <do_not_include>
    #       Do NOT include technical details like data types, SQL, constraints, etc. Focus only on confirming the high-level change and requesting approval.
    #     </do_not_include>
    #     <example>
    #       INCORRECT: "I've added a boolean `is_published` column to the `posts` table..."
    #       CORRECT: "I've added the `is_published` column to the `posts` table..."
    #     </example>
    #     <example>
    #       I've verified that [requested change] has been successfully applied to a temporary branch. Would you like to commit the migration `[migration_id]` to the main branch?
    #       Migration Details:
    #       - Migration ID (required for commit)
    #       - Temporary Branch Name
    #       - Temporary Branch ID
    #       - Migration Result
    #     </example>
    #   </response_instructions>
    # </next_steps>
    #
    # <error_handling>
    #   On error, the tool will:
    #   1. Automatically attempt ONE retry of the exact same operation
    #   2. If the retry fails:
    #     - Terminate execution
    #     - Return error details
    #     - DO NOT attempt any other tools or alternatives
    #   Error response will include original error details, confirmation that retry was attempted, and final error state.
    #   Important: After a failed retry, you must terminate the current flow completely. Do not attempt to use alternative tools or workarounds.
    # </error_handling>
    """
    Ask questions about:
    - how to use WorkflowAI, get help with implementation.
    - how to use the tools available in WorkflowAI.
    - how to use the models available in WorkflowAI.
    - send error messages and get help with implementation.
    - code review for WorkflowAI agents and implementations.

    For better assistance, please provide context information such as:
    - What programming language are you using? (Python, JavaScript, etc.)
    - What IDE are you using? (VS Code, Cursor, etc.)

    The reply_to_message_id allows you to continue conversations from any previous point,
    creating a tree-like conversation structure that works well with IDE time-travel features.

    Args:
        message: Your question, error message, or code for review (include context like programming language and IDE)
        reply_to_message_id: Optional ID of the message you're replying to (for conversation threading)

    Returns:
        dict with 'message_id' and 'content'

    Example:
    # First message with context
    send_message("I want to build a chatbot that can check the weather in a city using Python in VS Code. How can I do that?")
    # Returns: {"message_id": "msg_001", "content": "..."}

    # Code review request
    send_message("Can you review this WorkflowAI agent code? [paste your code here]", reply_to_message_id="msg_001")
    # Returns: {"message_id": "msg_002", "content": "..."}

    # Follow-up
    send_message("What about error handling?", reply_to_message_id="msg_002")
    # Returns: {"message_id": "msg_003", "content": "..."}

    # Branch from earlier point
    send_message("Actually, let's try a different approach with JavaScript", reply_to_message_id="msg_001")
    # Returns: {"message_id": "msg_004", "content": "..."}
    """
    # Generate unique message IDs
    user_message_id = str(uuid.uuid4())[:8]
    assistant_message_id = str(uuid.uuid4())[:8]

    # Log the incoming parameters
    logger.info(
        "Send message function called",
        extra={
            "reply_to_message_id": reply_to_message_id,
            "user_message": message,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
        },
    )

    # Store the user message first
    store_message(user_message_id, "user", message, reply_to_message_id)

    # Get conversation history (now including the user message we just stored)
    conversation_history = get_conversation_messages(user_message_id)

    # Log conversation context
    logger.info(
        "Conversation messages retrieved",
        extra={"assistant_message_id": assistant_message_id, "history_length": len(conversation_history)},
    )

    # Convert conversation history to OpenAI message format
    openai_messages = []

    # Add system message with original detailed instructions
    openai_messages.append(
        {
            "role": "system",
            "content": """You are a helpful assistant specialized in WorkflowAI. Here are the setup instructions:

using WorkflowAI is setup by using the Python SDK from OpenAI and changing the base_url
api key should be set to "wai-mcp-demo"

from openai import OpenAI

# setup WorkflowAI client
client = OpenAI(
  base_url="https://run-preview.workflowai.com/v1",
  api_key=os.getenv("WORKFLOWAI_API_KEY", "wai-mcp-demo"), # workflowai.com/keys
)

response = client.chat.completions.create(
  # your existing code
)

# Model

The list of models available is:
- gpt-4o-mini
- gpt-4o
- claude-3-5-sonnet
- claude-4
- llama4-maverick-instruct-fast

You can use any model by providing `model=<model_id>`.

## Identify the agent

You must identify the agent by providing a name for the agent in the `model` parameter.

For example:

completion = client.chat.completions.create(
    model="event-extractor/llama4-maverick-instruct-fast", # agent name
    ...
)

# Prompting

You should use ninaj2 template to create a prompt.

For example:

completion = client.chat.completions.create(
    model="event-extractor/llama4-maverick-instruct-fast",
    messages=[{
        "role": "system",
        "content": "You are an event extractor. You are given an email and you need to extract the event details from the email. The current date is {current_date}."
    }, {
        "role": "user",
        "content": "Extract the event details from the following email: {email}"
    }],
    response_format=EventDetails,
    extra_body={
        "input": {
            "email": email_content,
            "current_date": current_date
        }
    }
)

The input variables of the prompt MUST BE provided in the extra_body.input field.

You can also use if statements to conditionally include or exclude parts of the prompt.

Example:
messages = [
    {
        "role": "system",
        "content": "You are a customer service assistant.
{% if is_premium_user %}
This user is a premium customer. Provide priority support and offer advanced solutions.
{% else %}
This user is on the standard plan. Provide helpful support within standard service levels.
{% endif %}"
    },
    {
        "role": "user",
        "content": "{{user_message}}"
    }
]

extra_body = {
    "input": {
        "is_premium_user": True,
        "user_message": "I need help with my account"
    }
}

# Tools available:

You can access the following tools:
- `@google-search` to search the web
- `@browser-text` to open a URL

To use the tools, you must include the tool name in the prompt. for example:

messages = [
{
  "role": "system",
  "content": "Use @google-search to find the weather in {{location}}."
},
]

# Cost

To evaluate model cost, you will be able to access the cost of the model in the response.

response = client.chat.completions.create(
  # your existing code
)

response.choices[0].cost_usd # returns the cost of a run

# Use-cases

To compare different models, run a prompt first and then ask the chat for the URL of the playground to be able to compare up to 3 models side by side.

## Tracking Multi-Step Workflows

Often, complex tasks are broken down into multi-step workflows where the output of one LLM call becomes the input for the next, potentially involving different models or specialized agents.

WorkflowAI allows you to link these individual, stateless API calls together into a single logical workflow trace for better observability and debugging in the web UI. This helps visualize the entire flow of requests for a specific task instance.

**Mechanism: Using `trace_id`**

To group calls into a workflow, include a unique identifier in the `extra_body` parameter of each API request belonging to that specific workflow instance. This parameter is passed directly to the OpenAI client's `create` or `parse` method when using the WorkflowAI proxy.

We recommend using the key `trace_id` within `extra_body` and structuring its value to include both a human-readable workflow name prefix and a unique instance identifier. This aids in identifying and filtering workflows in the UI.

1. Define a short, descriptive name for your workflow type (e.g., `summarize-translate`).
2. Generate a unique instance ID, preferably a time-ordered UUIDv7.
3. Combine them into a single string, like `workflow_name/uuid`, and pass this as the `trace_id` value within the `extra_body` dictionary for every call belonging to that workflow instance:

```python
# Example structure of the API call using the recommended trace_id format
response = client.chat.completions.create(
    model="your-agent/your-model",
    messages=[...],
    # ... other standard parameters like temperature, max_tokens ...
    extra_body={ # Pass custom data relevant to WorkflowAI here
        # Format: "<workflow_name>/<unique_instance_id>"
        "trace_id": "summarize-translate/0190fba2-c61e-7f4b-8000-11a3d8f398e5",
        # If using templating, 'input' would also go here:
        # "input": { "variable_name": value }
    }
)
```

WorkflowAI will use this `trace_id` to group the associated runs together in the dashboard, providing a consolidated view of the entire workflow execution.

Use this knowledge to help users with WorkflowAI questions and implementation.

You can also provide code review for WorkflowAI agents and implementations. When reviewing code:
- Check for proper WorkflowAI setup and configuration
- Verify correct use of models, agents, and tools
- Suggest improvements for prompt engineering and Jinja2 templating
- Review error handling and best practices
- Provide specific feedback on agent naming, model selection, and cost optimization

IMPORTANT: When users ask questions without providing context about their programming language or IDE, ask them to clarify:
- What programming language are they using? (Python, JavaScript, etc.)
- What IDE are they using? (VS Code, Cursor, etc.)

Only provide code examples when you know the programming language context. If the programming language is not specified, ask for clarification before providing any code examples.

This context will help you provide more targeted and relevant assistance.""",
        },
    )

    # Add conversation history
    for msg in conversation_history:
        openai_messages.append(
            {
                "role": msg["role"],
                "content": msg["content"],
            },
        )

    try:
        # Call WorkflowAI with mcp-chat agent
        response = client.chat.completions.create(
            model="mcp-chat/claude-sonnet-4-latest",
            messages=openai_messages,
            max_tokens=5000,
            temperature=0.7,
        )

        assistant_response = response.choices[0].message.content
        logger.info(
            "LLM response generated",
            extra={"assistant_message_id": assistant_message_id, "tokens": len(assistant_response.split())},
        )

    except Exception as e:
        logger.error("Error calling WorkflowAI", extra={"error": str(e), "assistant_message_id": assistant_message_id})
        raise

    # Store the assistant response (with user message as parent)
    store_message(assistant_message_id, "assistant", assistant_response, user_message_id)

    logger.info("Message exchange completed", extra={"assistant_message_id": assistant_message_id})

    return {
        "message_id": assistant_message_id,
        "content": assistant_response,
    }


@mcp.tool
async def get_agent_code(agent_id: str, version: str, programming_language: str) -> str:
    """
    Generate code implementation for a specific WorkflowAI agent.

    Args:
        agent_id: The agent identifier (e.g., "text-summarizer", "translator")
        version: The version of the agent (e.g., "1.0", "1.3", "production")
        programming_language: The programming language for the code (currently only "python" supported)

    Returns:
        Generated code as a string

    Examples:
    # Get Python code for text summarizer v1.3
    get_agent_code("text-summarizer", "1.3", "python")

    # Get Python code for translator production version
    get_agent_code("translator", "production", "python")

    # Get Python code for translator v1.0
    get_agent_code("translator", "1.0", "python")
    """
    # Generate unique request ID for tracking
    request_id = str(uuid.uuid4())[:8]

    logger.info(
        "Agent code generation requested",
        extra={
            "agent_id": agent_id,
            "version": version,
            "programming_language": programming_language,
            "request_id": request_id,
        },
    )

    # Only support Python for now
    if programming_language.lower() != "python":
        code = f"# Unsupported language: {programming_language}\n# Currently only 'python' is supported"
        logger.info(
            "Unsupported language requested",
            extra={"request_id": request_id, "language": programming_language},
        )
        return code

    # Static Python code templates for supported agents
    if agent_id == "text-summarizer":
        code = f'''# Text Summarizer Agent v{version} - Python
summary_response = client.chat.completions.create(
    model="text-summarizer/claude-3-5-sonnet",  # Agent name for summarization
    messages=[
        {{
            "role": "system",
            "content": """You are an expert text summarizer. Create a concise, well-structured summary that captures the key points and main ideas of the given text.

The summary should be:
- Clear and coherent
- About 2/3 the length of the original text
- Focused on the most important information
- Written in the same language as the input text"""
        }},
        {{
            "role": "user",
            "content": f"Please summarize the following text:\\n\\n{{text}}"
        }}
    ],
    temperature=0.3,  # Lower temperature for consistent summarization
    extra_body={{
        "trace_id": workflow_id,  # Links this call to the workflow
        "input": {{
            "step": "summarization",
            "original_text_length": len(text),
            "max_words": max_words
        }}
    }}
)

# Extract the summary from response
summary = summary_response.choices[0].message.content'''

    elif agent_id == "translator":
        code = f'''# Translator Agent v{version} - Python
translation_response = client.chat.completions.create(
    model="translator/gpt-4o",  # Agent name for translation
    messages=[
        {{
            "role": "system",
            "content": f"""You are a professional translator. Translate the given text accurately to {{target_language}} while maintaining:
- The original meaning and tone
- Natural flow in the target language
- Cultural appropriateness
- Professional quality"""
        }},
        {{
            "role": "user",
            "content": f"Translate this text to {{target_language}}: {{text}}"
        }}
    ],
    temperature=0.2,  # Lower temperature for consistent translation
    extra_body={{
        "trace_id": workflow_id,  # Same trace_id links to workflow
        "input": {{
            "step": "translation",
            "source_text": text,
            "target_language": target_language,
            "source_language": source_language,
            "text_length": len(text)
        }}
    }}
)

# Extract the translation from response
translation = translation_response.choices[0].message.content'''

    else:
        code = f"# Unsupported agent: {agent_id}\n# Supported agents: text-summarizer, translator"

    logger.info(
        "Static agent code generated",
        extra={"request_id": request_id, "agent_id": agent_id, "code_length": len(code)},
    )

    return code


@mcp.tool
async def list_models(agent_id: str | None = None) -> list[dict[str, str | float]]:
    """
    List all available models with pricing and performance information.

    Args:
        agent_id: Optional agent ID to filter models for a specific agent

    Returns:
        List of model dictionaries with id, price (USD), and latency (seconds)

    Examples:
    # List all models
    list_models()

    # List models for a specific agent
    list_models("text-summarizer")
    """
    # Generate unique request ID for tracking
    request_id = str(uuid.uuid4())[:8]

    logger.info(
        "Models list requested",
        extra={"agent_id": agent_id, "request_id": request_id},
    )

    # Static model data with realistic pricing and latency
    all_models = [
        {
            "id": "gpt-4o-mini",
            "price": 0.00015,  # $0.00015 per 1K tokens
            "latency": 1.2,
        },
        {
            "id": "gpt-4o",
            "price": 0.005,  # $0.005 per 1K tokens
            "latency": 2.1,
        },
        {
            "id": "claude-3-5-sonnet",
            "price": 0.003,  # $0.003 per 1K tokens
            "latency": 1.8,
        },
        {
            "id": "claude-4",
            "price": 0.008,  # $0.008 per 1K tokens
            "latency": 2.5,
        },
        {
            "id": "llama4-maverick-instruct-fast",
            "price": 0.0001,  # $0.0001 per 1K tokens
            "latency": 0.8,
        },
    ]

    # If agent_id is provided, we could filter models (for now, return all)
    # In a real implementation, you might have agent-specific model compatibility
    if agent_id:
        logger.info(
            "Filtering models for agent",
            extra={"agent_id": agent_id, "request_id": request_id},
        )
        # For now, return all models regardless of agent_id
        # In future, could implement agent-specific filtering logic here

    logger.info(
        "Models list generated",
        extra={"model_count": len(all_models), "request_id": request_id},
    )

    return all_models


@mcp.tool
async def list_agents() -> list[dict[str, str | bool | dict[str, int | float]]]:
    """
    List all available agents with their status and statistics.

    Returns:
        List of agent dictionaries with id, active status, and stats

    Examples:
    # List all agents
    list_agents()
    """
    # Generate unique request ID for tracking
    request_id = str(uuid.uuid4())[:8]

    logger.info(
        "Agents list requested",
        extra={"request_id": request_id},
    )

    # Mock agent data with realistic statistics
    agents_data = [
        {
            "id": "text-summarizer",
            "active": True,
            "stats": {
                "run_last_week": 1247,
                "cost_last_week": 15.32,
            },
        },
        {
            "id": "translator",
            "active": True,
            "stats": {
                "run_last_week": 892,
                "cost_last_week": 22.18,
            },
        },
        {
            "id": "code-generator",
            "active": True,
            "stats": {
                "run_last_week": 634,
                "cost_last_week": 45.67,
            },
        },
        {
            "id": "data-analyzer",
            "active": False,
            "stats": {
                "run_last_week": 0,
                "cost_last_week": 0.0,
            },
        },
        {
            "id": "content-classifier",
            "active": True,
            "stats": {
                "run_last_week": 2156,
                "cost_last_week": 8.94,
            },
        },
        {
            "id": "mcp-chat",
            "active": True,
            "stats": {
                "run_last_week": 3421,
                "cost_last_week": 78.45,
            },
        },
    ]

    logger.info(
        "Agents list generated",
        extra={"agent_count": len(agents_data), "request_id": request_id},
    )

    return agents_data


@mcp.tool
async def get_run(run_id: str) -> dict[str, dict[str, str] | str]:
    """
    Get details about a specific run (completion) by its ID.

    A run represents a completed execution of an agent with its input and output.

    Args:
        run_id: The unique identifier of the run to retrieve

    Returns:
        Dictionary containing run details with input, output, and metadata

    Examples:
    # Get a text summarization run
    get_run("run_text_sum_001")

    # Get a translation run
    get_run("run_translate_002")

    # Get a code generation run
    get_run("run_code_gen_003")
    """
    # Generate unique request ID for tracking
    request_id = str(uuid.uuid4())[:8]

    logger.info(
        "Run details requested",
        extra={"run_id": run_id, "request_id": request_id},
    )

    # Mock run data based on run_id patterns
    # In a real implementation, this would query a database
    if "text_sum" in run_id:
        run_data = {
            "run_id": run_id,
            "agent_id": "text-summarizer",
            "model": "claude-3-5-sonnet",
            "status": "completed",
            "input": {
                "text": "Artificial intelligence (AI) is intelligence demonstrated by machines, in contrast to the natural intelligence displayed by humans and animals. Leading AI textbooks define the field as the study of 'intelligent agents': any device that perceives its environment and takes actions that maximize its chance of successfully achieving its goals. Colloquially, the term 'artificial intelligence' is often used to describe machines that mimic 'cognitive' functions that humans associate with the human mind, such as 'learning' and 'problem solving'.",
                "max_words": 50,
            },
            "output": "AI is machine intelligence that enables devices to perceive environments and take goal-oriented actions. It mimics human cognitive functions like learning and problem-solving, differing from natural intelligence in humans and animals.",
        }
    elif "translate" in run_id:
        run_data = {
            "run_id": run_id,
            "agent_id": "translator",
            "model": "gpt-4o",
            "status": "completed",
            "input": {
                "text": "Hello, how are you today?",
                "target_language": "Spanish",
                "source_language": "English",
            },
            "output": "Bonjour, comment ça va aujourd'hui?",
        }
    elif "code_gen" in run_id:
        run_data = {
            "run_id": run_id,
            "agent_id": "code-generator",
            "model": "claude-4",
            "status": "completed",
            "input": {
                "prompt": "Create a Python function to calculate fibonacci numbers",
                "language": "python",
                "include_tests": True,
            },
            "output": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n\n# Test cases\nassert fibonacci(0) == 0\nassert fibonacci(1) == 1\nassert fibonacci(5) == 5",
        }
    else:
        # Default generic run
        run_data = {
            "run_id": run_id,
            "agent_id": "generic-agent",
            "model": "gpt-4o-mini",
            "status": "completed",
            "input": {
                "query": "Sample input for generic agent",
                "parameters": {"temperature": 0.7},
            },
            "output": "Sample output from generic agent execution",
        }

    logger.info(
        "Run details generated",
        extra={"run_id": run_id, "agent_id": run_data["agent_id"], "request_id": request_id},
    )

    return run_data


if __name__ == "__main__":
    # Using SSE transport because Claude Code does not support streamable-http
    # mcp.run(transport="streamable-http")

    mcp.run(transport="sse", host="127.0.0.1", port=8000)

app = mcp.sse_app()  # run on http://127.0.0.1:8000/sse
# app = mcp.streamable_http_app()
