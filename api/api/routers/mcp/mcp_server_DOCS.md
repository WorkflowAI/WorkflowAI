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
      "url": "http://localhost:8000/mcp/",
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
      "url": "https://api.workflowai.dev/mcp/",
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
      "url": "https://workflowai-api-preview.bravewave-364a85ed.eastus.azurecontainerapps.io/mcp/",
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
      "url": "https://api.workflowai.com/mcp/",
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
- [x] Scenario 4: Debug Agent Incorrect Output
- [x] Scenario 7: Fix User Bug When Agent Lacks Metadata Tracking
      _Notes from Yann: This is essentially solved by documenting the run metadata feature in the docs. We would need a little more details on how to fetch runs for a specific metadata, and to add potentially an MCP tool to fetch runs for a specific metadata._
- [x] Scenario 10: Ask WorkflowAI for Agent Improvement Recommendations
      [X] Scenario 11: Setup Deployments on Existing Agent
- [x] Scenario 12: Deploy Specific Agent Version

### WIP use cases:

- [ ] Scenario 5: Edit Agent in Playground and Sync to IDE

_Notes from Yann: Should the goal be instead to make the user switch to deployments? I personally find this use case a little bit cumbersome._

_The user would update a version in the playground, then you would probably need to copy the version ID, pass it to Cursor. Cursor will need to fetch a version. Then Cursor will need to exactly copy the version message. If there is anything not exactly copied, like a line break or anything, a new version will be created when the agent will run_

_I think this use case is better served by switching the user to deployment._

- [ ] Scenario 6: Investigate User's Bad Agent Experience
      _Notes from Yann: WIP_

- [ ] Scenario 8: Evaluate New OpenAI Model Performance

_Notes from Yann: should benchmarking be the realm of WorkflowAI cloud ? Having an UI for those things is very useful for the user_

- [ ] Scenario 9: Get Latest Updates from WorkflowAI Platform

_Notes from Yann: Doable, we'll just need to expose our release notes to the AI Engineer. Should release notes be included in the docs then ? Another options is to put the date at whic we release features in the feature's docs so the AI engineer can figure out what's old and what's new._

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
