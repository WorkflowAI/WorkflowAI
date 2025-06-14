# WorkflowAI MCP Server

A Model Context Protocol (MCP) server that exposes WorkflowAI agents and tools to MCP-compatible clients like Claude, Cursor, and other AI assistants.

## Overview

This MCP server provides programmatic access to WorkflowAI's functionality, allowing AI assistants to:
- Create and manage WorkflowAI agents
- Get help from WorkflowAI's AI engineer
- List available AI models
- Inspect agent runs and debug issues
- View agent and statistics
- View agent versions
- create_completion(messages, ...) tool


## Connecting from Cursor

To access the WorkflowAI MCP server directly from Cursor you only need to declare the server in your `mcp.json` file:

For local / dev:
```json
{
  "mcpServers": {
    "workflowai": {
      "url": "http://localhost:8000/mcp/sse",
      "headers": {
        "Authorization": "Bearer <your-api-key>"
      }
    }
    // your other mcp servers here
  }
}
```

For staging:
```json
{
  "mcpServers": {
    "workflowai": {
      "url": "https://api.workflowai.dev/mcp/sse",
      "headers": {
        "Authorization": "Bearer <your-api-key>"
      }
    }
    // your other mcp servers here
  }
}
```

For prod preview:
```json
{
  "mcpServers": {
    "workflowai": {
      "url": "https://workflowai-api-preview.bravewave-364a85ed.eastus.azurecontainerapps.io/mcp/sse",
      "headers": {
        "Authorization": "Bearer <your-api-key>"
      }
    }
    // your other mcp servers here
  }
}
```


For production:
```json
{
  "mcpServers": {
    "workflowai": {
      "url": "https://api.workflowai.com/mcp/sse",
      "headers": {
        "Authorization": "Bearer <your-api-key>"
      }
    }
    // your other mcp servers here
  }
}
```

1. Create (or edit) `~/.cursor/mcp.json` and paste the snippet above (replace the token if necessary).
2. Restart Cursor or run **MCP: Reload Servers**.
3. WorkflowAI tools will now appear in the command palette just like any other MCP server.

> You no longer need to clone, install or run the MCP server locally—Cursor will proxy all calls to the URL provided.

## Available Tools

The MCP server exposes 5 tools for working with WorkflowAI agents:

1. **`ask_ai_engineer`** - Get help from WorkflowAI's AI engineer
2. **`list_available_models`** - List all available AI models
3. **`fetch_run_details`** - Get detailed information about a specific agent run
4. **`list_agents_with_stats`** - List all agents with performance statistics
5. **`get_agent_versions`** - Retrieve version information for a specific agent

For detailed parameters, descriptions, and usage examples, see:
- **Router definitions**: [`api/api/routers/mcp/mcp_router.py`](api/api/routers/mcp/mcp_router.py)
- **Service implementations**: [`api/api/services/mcp_service.py`](api/api/services/mcp_service.py)



# What's next?

- See https://linear.app/workflowai/issue/WOR-4911/workflowai-mcp-v01

Notes from Yann: I wonder if I should not simply manage my subtasque in this README instead of linear.


# Use cases from [docs](https://github.com/WorkflowAI/fumadocs-demo/blob/main/demo/my-app/content/docs/use-cases/mcp.mdx#ax-agent-experience)

## Use cases implementation summary

### Supported use cases:
- [x] Scenario 1: Build Text Summarization Agent from Scratch
- [x] Scenario 2: Optimize Agent Performance with Faster Models
- [x] Scenario 3: Migrate Agent from OpenAI to WorkflowAI
- [X] Scenario 4: Debug Agent Incorrect Output
- [X] Scenario 7: Fix User Bug When Agent Lacks Metadata Tracking
*Notes from Yann: This is essentially solved by documenting the run metadata feature in the docs. We would need a little more details on how to fetch runs for a specific metadata, and to add potentially an MCP tool to fetch runs for a specific metadata.*
- [X] Scenario 10: Ask WorkflowAI for Agent Improvement Recommendations
  [X] Scenario 11: Setup Deployments on Existing Agent
- [X] Scenario 12: Deploy Specific Agent Version

### WIP use cases:
- [ ] Scenario 5: Edit Agent in Playground and Sync to IDE

*Notes from Yann: Should the goal be instead to make the user switch to deployments? I personally find this use case a little bit cumbersome.*

*The user would update a version in the playground, then you would probably need to copy the version ID, pass it to Cursor. Cursor will need to fetch a version. Then Cursor will need to exactly copy the version message. If there is anything not exactly copied, like a line break or anything, a new version will be created when the agent will run*

*I think this use case is better served by switching the user to deployment.*

- [ ] Scenario 6: Investigate User's Bad Agent Experience
*Notes from Yann: WIP*

- [ ] Scenario 8: Evaluate New OpenAI Model Performance

*Notes from Yann: should benchmarking be the realm of WorkflowAI cloud ? Having an UI for those things is very useful for the user*

- [ ] Scenario 9: Get Latest Updates from WorkflowAI Platform

*Notes from Yann: Doable, we'll just need to expose our release notes to the AI Engineer. Should release notes be included in the docs then ? Another options is to put the date at whic we release features in the feature's docs so the AI engineer can figure out what's old and what's new.*

### Proposition for next use cases:
- [ ] Very large PDF payload that break agent, the MCP should be able to investigate https://workflowaihq.slack.com/archives/C075WQE2Y6M/p1749826343497299
- [ ] Add a new input variables (including with deployed agent)
- [ ] Add a new output variable (including with deployed agent)
- [ ] Migrate agent to stuctured output
- [ ] Add a hosted tool capability
- [ ] Add custom tool capability
- [ ] Creating a workflow with multiple agents
- [ ] Checking the last 10-100 runs and "vibe check" how the agent is doing.

# TODOs
- fill the ./use_cases/
- Plug Slack to Cursor and ask to test #new-models on our agents
- Try a model on a dataset (use case from Florian, talk to Anya)
- migrate agent from SDK to proxy
- mcp.tool to create an API key
- return TODO list for the Cursor agent
- create_completion(messages, ...) tool


## Scenario 1: Build Text Summarization Agent from Scratch

### intial state:
```python
(empty repo)
```

### goal: (as the end-user would write in Codex, Cursor, etc.)
```
- write a AI agent that can summarize a text. if there is a URL in the text, extract the text from the URL to be able to write an accurate summary.
- find a model that works well for this task
- and is cheap.

give me 3 options (models) from choose from with pros and cons.
```

### what is required:
- a way to get the code of the agent
- API keys
- a way to run the code for a given input to test it (either via the code, via the API directly)
- evaluate the output of the agent
- access the price
- access the tools available on the platform.
- ...

## Scenario 2: Optimize Agent Performance with Faster Models

### intial state:

```
- agent is running on OpenAI.
```
```python
import openai

client = openai.OpenAI(api_key="sk-proj-1234567890")

prompt = """
<instructions> Analyze the provided conversation transcript to determine if it indicates a potential scam. Follow these steps:
Carefully examine the transcript.
Identify common scam indicators such as:
Requests for personal or financial information.
Promises of unrealistic rewards or gains.
Pressure to act quickly or threats of negative consequences.
Unusual or unsolicited payment requests.
Inconsistencies or vague details in the story.
Offers to help with financial issues without a valid reason.
Presence of unsolicited messages, especially those containing links or attachments.
Use of shortened URLs or suspicious links.
Determine the role of each participant to accurately identify the user exhibiting scam behavior.
Determine if the conversation is a scam:
If clear scam indicators are present, set is_scam to 'YES'.
Else if some suspicious elements are present, the transcript is long enough and you have enough context but not enough to confirm, set is_scam to 'UNSURE'.
Else if no scam indicators are found or more context is needed to determine if this is a scam or the transcript is too short to make a definitive determination if this is a scam, set is_scam to 'NO'.
Provide a concise reason explaining your determination, highlighting specific elements from the transcript that support your conclusion.
If you determine the conversation is a scam or potentially a scam, include the author_id of the user identified as the scammer in the scamer_id field.
Format the output with 'is_scam', 'reason', and 'scamer_id' fields. If the conversation is definitely not a scam, set 'scamer_id' to an empty string.
Ensure that the 'scamer_id' accurately corresponds to the "speakerId" field of the user exhibiting scam characteristics based on the transcript.
Example:
{
  "is_scam": "YES",
  "reason": "The message is unsolicited, contains a shortened link, and mentions a rewards credit with an urgent expiration date, which are common phishing tactics.",
  "scamer_id": "usr_1M3TB5BZ7D12X8KKBXT08HWEB4"
}
</instructions>
Input will be provided in the user message using a JSON following the schema:
{
  "type": "object",
  "properties": {
    "transcript": {
      "description": "The transcript of the conversation to be checked for scams",
      "type": "string"
    }
  }
}
Return a single JSON object enforcing the following schema:
{
  "type": "object",
  "properties": {
    "is_scam": {
      "description": "Indicates whether the conversation is a scam. Set to 'YES' if clear scam indicators are present and participants do not have a known relationship, 'NO' if no scam indicators are found, the transcript is too short, or participants have a known relationship, and 'UNSURE' if there are multiple suspicious elements but not enough to confirm.",
      "enum": [
        "YES",
        "NO",
        "UNSURE"
      ],
      "type": "string"
    },
    "reason": {
      "description": "The explanation for why the conversation is identified as a scam or not, highlighting specific elements from the transcript that support the conclusion, including the relationship between participants.",
      "type": "string",
      "examples": [
        "The transcript shows an unsolicited invitation to a webinar masterclass from a participant who does not have a prior relationship with the other party.",
        "Participants are known to each other and there are no clear scam indicators present.",
        "Multiple suspicious elements are present, but the relationship between participants makes it inconclusive."
      ]
    },
    "scamer_id": {
      "description": "The `author_id` of the user identified as the scammer. If `is_scam` is `'UNSURE'`, still include the `scammer_id`.",
      "examples": [
        "usr_QQTA93SZAH6XXFYK0E8190KA6M"
      ],
      "type": "string"
    }
  }
}
"""

user_input = """
{
  "transcript": "[{\"speakerId\":\"usr_WG87GX2W5H54N3E3KBQ32E9FPG\",\"text\":\"About:\\nDesoto Door is a local, family-owned company specializing in residential and commercial garage door services, including repair, installation, and maintenance. Established in 2009, the company is dedicated to providing high-quality, customizable garage door solutions.\\n\\nServices:\\n- Garage Door Installation: Professional installation of new garage doors tailored to customer preferences and architectural styles.\\n- Garage Door Repair: Expert repair services for garage doors, addressing issues such as jammed doors, spring, roller, and track repairs.\\n- Garage Door Opener Repair: Specialized repair services for garage door openers, ensuring smooth and reliable operation.\\n- Emergency Garage Door Services: 24/7 emergency repair services for urgent garage door issues.\\n- Gate Opener Installation and Repair: Installation and maintenance of automated gate openers with advanced access control technology.\\n\\nProducts:\\n- Residential Garage Doors: Offering a variety of styles including carriage-house, raised-panel, and modern designs with overhead operation. Available in multiple colors, finishes, and materials to enhance home aesthetics.\\n- Commercial Overhead Doors: Providing energy-efficient and durable overhead doors for commercial spaces, including sectional and rolling steel doors designed for safety and efficiency.\\n\\nPolicies:\\n- Repairs: Repair services are provided by certified technicians with a focus on quality and customer satisfaction.\\n\\nBusiness Hours:\\n- Mon - Friday 8-4\"}]"
}
"""

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": prompt
        },
        {
            "role": "user",
            "content": user_input
        }
    ]
)

print(response.choices[0].message.content)
```

### goal:
```
- this AI agent is too slow, i want to use a faster model.
- make sure the faster model give similar results than the current model.
- compare the faster models with the current model.
```

### what is required:
- create API keys

## Scenario 3: Migrate Agent from OpenAI to WorkflowAI

### intial state:

```
- agent is running on OpenAI.
```

### goal:
```
- i want to setup this agent on WorkflowAI.
- make no changes to the agent, model, keep everything the same.
- test that the agent is running fine on WorkflowAI.
- ...
```

### what is required:
- create API keys
- ...


## Scenario 4: Debug Agent Incorrect Output

### intial state:

```
- agent is running on WorkflowAI.
this agent: https://workflowai.com/hearthands/agents/scam-detection/runs/01974351-2a58-7337-cabe-a4c8e1510b97
```

### goal:
```
- for this run https://workflowai.com/hearthands/agents/scam-detection/runs/01974351-2a58-7337-cabe-a4c8e1510b97, the correct answer was "YES".
- i want to know why the agent gave the wrong answer. and what would you do to improve the agent.
```

### what is required:
- ...

## Scenario 5: Edit Agent in Playground and Sync to IDE

### initial state:
```
- agent is running on WorkflowAI
- user has the agent code in their IDE (VSCode, Cursor, etc.)
```

### goal:
```
- open the WorkflowAI playground to edit the agent
- experiment with different prompts and configurations in the playground
- find a new version that works better
- get the updated agent code back into my IDE
```

### what is required:
- ability to open/launch WorkflowAI playground from IDE
- download/export agent code from WorkflowAI platform

## Scenario 6: Investigate User's Bad Agent Experience

<Callout type="info">
  This scenario is the one we are getting internally with issues being reported to Yann's with the playground agent.
  Demo a specific and real issue.
</Callout>

### initial state:
```
- agent is deployed on WorkflowAI in production
- agent logs all runs with metadata including "user_id"
```

### goal:
```
- user_id "usr_12345" just got a bad experience with agent "agent_abc123"
- find out what happened in that specific interaction
- analyze the agent's behavior for that user
- identify potential issues or failure points
- understand if this is a recurring problem for this user or others
```

### what is required:
- ability to query runs by user_id and agent_id
- retrieve specific run details and execution traces
- ...

## Scenario 7: Fix User Bug When Agent Lacks Metadata Tracking

### initial state:
```
- agent is deployed on WorkflowAI in production
- agent is NOT collecting user_id or other metadata for runs
```

### goal:
```
- user_id "usr_67890" reports a bug with agent "agent_xyz789"
- fix this bug for this specific user
- but first need to implement proper metadata collection
- then investigate and resolve the user's issue
```

### what is required:
- modify agent code to collect user_id metadata for all runs
- deploy updated agent with metadata tracking

## Scenario 8: Evaluate New OpenAI Model Performance

### initial state:
```
- agent is running on WorkflowAI with current model (e.g., gpt-4o)
- agent has historical performance data
- new OpenAI model is available (e.g., gpt-4o-2024-11-20)
```

### goal:
```
- try how the new model from OpenAI performs on this agent
- compare quality, speed, and cost between current and new model
- decide whether to upgrade the agent to use the new model
```

### what is required: (AI generated)
- ability to duplicate/clone existing agent with new model configuration
- access to run the same prompts/inputs on both model versions
- quality comparison tools to evaluate output differences
- A/B testing capabilities to run parallel experiments
- access to latency metrics for both models
- cost analysis and reporting for token usage comparison
- performance benchmarking tools
- ability to run test suites against both model versions
- statistical analysis to determine significance of differences
- rollback capabilities if new model underperforms
- gradual rollout tools to test with subset of users first

## Scenario 9: Get Latest Updates from WorkflowAI Platform

### initial state:
```
(do not matter)
```

### goal:
```
- get the latest updates from WorkflowAI platform and update the code to benefit
```

### what is required: (AI generated)
- access to WorkflowAI platform changelog or release notes
- ability to fetch latest platform updates and new features
- understand which updates are relevant to current agent implementation
- modify agent code to leverage new platform capabilities
- test updated agent with new features
- migrate existing configurations to utilize new improvements
- access to platform API documentation for new endpoints or parameters

## Scenario 10: Ask WorkflowAI for Agent Improvement Recommendations

### initial state:
```
- any agent file
```

### goal:
```
- can you ask WorkflowAI how to improve this agent?
```

### what is required:
- ...

## Scenario 11: Setup Deployments on Existing Agent

### initial state:
```
- agent code is available in IDE
```

### goal:
```
- setup deployments on this agent
ALT:
- I want to be able to update this agent without changing any code using WorkflowAI.
```

### what is required:
- ...

## Scenario 12: Deploy Specific Agent Version

### initial state:
```
(does not matter)
```

### goal:
```
- deploy this version to production on WorkflowAI.
```

### what is required:
- ...

# References

## Neon MCP

https://neon.com/docs/ai/neon-mcp-server#supported-actions-tools lists the tools from the Neon MCP server.
