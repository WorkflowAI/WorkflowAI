# Claude Code Setup & Integration

Learn how to set up Claude Code CLI with WorkflowAI MCP server integration for enhanced AI-powered development workflows.

## Prerequisites

- **Poetry** for dependency management
- **WorkflowAI API key** (get yours from the [WorkflowAI dashboard](https://workflowai.com/organization/settings/api-keys))
- **Node.js 18+** and **jq** for JSON processing (optional but recommended)

## Quick Start

### 1. Install Dependencies

```bash
poetry install
```

### 2. Add WorkflowAI MCP Server

Configure Claude Code to use WorkflowAI's MCP server:

```bash
# preview
claude mcp add workflowai https://run-preview.workflowai.com/mcp/ --transport http -H "Authorization: Bearer YOUR_API_KEY_HERE"

# dev
claude mcp add workflowai https://api.workflowai.dev/mcp/ --transport http -H "Authorization: Bearer YOUR_API_KEY_HERE"
```

Replace `YOUR_API_KEY_HERE` with your WorkflowAI API key.

### 3. Verify Configuration

Test your MCP server connection:

```bash
# Start Claude
claude

# Check server status
/mcp
```

You should see the WorkflowAI server listed as "connected".

### 4. Run Your First Command

```bash
poetry run python main.py
```

## CLI Usage

Claude Code CLI supports both interactive and non-interactive modes with powerful session management.

### Print Mode

For scripted workflows, use print mode (`-p` or `--print`):

```bash
claude -p "Generate a hello world function"
```

### Output Formats

Control how results are displayed:

```bash
# Human-readable text (default)
claude -p "Create a function" --output-format text

# Structured JSON with metadata
claude -p "Create a function" --output-format json

# Real-time streaming
claude -p "Create a function" --output-format stream-json
```

### Session Management

Claude Code offers two approaches for conversation continuity:

#### Auto-Continue (Recommended)

The simplest way to maintain context across commands:

```bash
# Initial request
claude -p "Create a calculator function"

# Continue the conversation
claude -p --continue "Add subtraction and tests"

# Keep building on the same session
claude -p -c "Add error handling"
```

#### Manual Session Control

For advanced workflows requiring explicit session management:

```bash
# Get session ID from JSON output
claude -p "Create a calculator function" --output-format json
# Returns: {"session_id": "f81f5e47-2261-4da0-b213-24c170e03294", ...}

# Resume specific session
claude -p --resume f81f5e47-2261-4da0-b213-24c170e03294 "Add subtraction and tests"
```

### Command Options

Key flags for customizing behavior:

| Flag | Description |
|------|-------------|
| `--max-turns N` | Limit conversation turns |
| `--allowedTools "Edit,Bash"` | Restrict available tools |
| `--disallowedTools "Web"` | Exclude specific tools |
| `--model sonnet` | Specify model (sonnet, opus, etc.) |
| `--dangerously-skip-permissions` | Bypass permission checks (sandboxes only) |

## Advanced Features

### Debugging and Logging

Enable verbose logging for MCP server interactions:

```bash
claude --verbose -p "what is WorkflowAI?" --output-format json --max-turns 3
```

> **Note**: Verbose mode requires `--output-format json` to display the complete conversation flow.

### JSON Response Structure

When using `--output-format json`, you receive detailed metadata:

```json
{
  "type": "result",
  "subtype": "success",
  "duration_ms": 15623,
  "num_turns": 7,
  "result": "Your response text...",
  "session_id": "unique-session-id",
  "total_cost_usd": 0.0289,
  "usage": {
    "input_tokens": 17,
    "output_tokens": 549,
    "cache_read_input_tokens": 64779
  }
}
```

## Common Workflows

### Development Workflow

```bash
# Start a new project
claude -p "Create a web server"
claude -p --continue "Add authentication to the server"
claude -p -c "Add error handling and logging"
```

### Script-Based Development

```bash
# Using session management in scripts
RESULT=$(claude -p "Create a web server" --output-format json)
SESSION_ID=$(echo $RESULT | jq -r '.session_id')
claude -p --resume $SESSION_ID "Add authentication to the server"
```

### Constrained Execution

```bash
# Limit tools and turns for specific tasks
claude -p "Analyze this codebase" --allowedTools "Read" --max-turns 5
```

## Agent Evaluation & Testing

Claude Code CLI supports automated agent testing workflows.

### Running Evaluations

```bash
cd evaluations/dataset
claude -p "read prompt.md and follow instructions" --verbose --output-format json --max-turns 10
```

### Creating New Agents

```bash
# Create and test new agents
cd new-agent
claude -p "read prompt.md and follow instructions" --verbose --output-format json

# Evaluate the agent (separate from creation to prevent leakage)
claude -p "read evaluate.md and follow instructions" --verbose --output-format json
```

## Troubleshooting

### Common Issues

**MCP Server Not Connected**
- Verify your API key is correct
- Check network connectivity to WorkflowAI endpoints
- Ensure you're using the correct environment URL

**Permission Errors**
- Use `--dangerously-skip-permissions` only in sandboxed environments
- Check that required tools are in `--allowedTools` list

**Session Not Found**
- Session IDs expire after inactivity
- Use `--continue` for simple workflows instead of manual session management

## Reference

### Project Structure
- `main.py` - Main script with MCP tool integration
- `pyproject.toml` - Poetry configuration and dependencies
- `evaluations/` - Agent testing and evaluation examples
- `new-agent/` - Template for creating new agents

### External Resources
- [Claude Code SDK Documentation](https://docs.anthropic.com/en/docs/claude-code/sdk)
- [Multi-turn Conversations Guide](https://docs.anthropic.com/en/docs/claude-code/sdk#multi-turn-conversations)
- [WorkflowAI Platform](https://workflowai.com)
