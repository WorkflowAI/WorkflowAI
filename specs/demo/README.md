# MCP Demo with FastMCP

WorkflowAI MCP server for Cursor AI integration.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

### Cursor

MCP servers can be configured in Cursor Settings:

```json
{
  "mcpServers": {
    "WorkflowAI": {
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

**Note:** When the server gets restarted while Cursor is already connected, Cursor can't connect to the new server instance. You need to turn the MCP server off and on in Cursor Settings to refresh the connection.

**TODO:** We need to look into this session stuff from MCP to understand and potentially improve this behavior.

### Claude

**Note:** We need to use the SSE transport because Claude Code does not support streamable-http.

#### Setup API key

> https://docs.anthropic.com/en/docs/claude-code/settings#environment-variables

```json
{
  "env": {
    "ANTHROPIC_API_KEY": "sk-ant-api03-1234567890"
  }
}
```

#### MCP

```bash
claude mcp add --transport sse sse-server http://127.0.0.1:8000/sse
```

## Usage

1. **Start server:**
   ```bash
   # Development mode with hot-reload
   uvicorn server:app --reload --port 8000

   # Or run directly
   python3 server.py
   ```

2. **In Cursor AI Agent mode:**
   ```
   using WorkflowAI:
   - write an AI agent that can summarize a text. If there is a URL in the text, open the URL and use the text from the URL to be able to write an accurate summary.

   First plan your approach. Ask me any questions to clarify the task. Use the chat tool from WorkflowAI to brainstorm your ideas and get feedback.
   Test your agent with 1 example that does not include any URL.
   Do not create a README. Do not write tests. Do not write any documentation.

   Ask for my approval before writing the code.

   - find a model that works well for this task
   - and is cheap.
   Give me 3 options (models) to choose from with pros and cons.
   ```

## Tool

- **chat**: WorkflowAI assistance with `chat_id` and `message` parameters
