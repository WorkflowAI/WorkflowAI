# Model Context Protocol (MCP)

The Model Context Protocol (MCP) is an open standard that enables AI models to securely connect to external data sources and tools. Think of MCP like a USB-C port for AI applications - it provides a standardized way to connect AI models to different systems, databases, and services.

WorkflowAI supports MCP integration through the OpenAI-compatible chat/completions endpoint, allowing you to leverage the growing ecosystem of MCP servers with any model supported by WorkflowAI.

## What is MCP?

MCP allows AI models to access:
- **External data sources** (databases, file systems, APIs)
- **Live information** (real-time data, current state)
- **Specialized tools** (code execution, analysis tools)
- **Business systems** (CRM, documentation, internal tools)

Unlike static data or pre-trained knowledge, MCP enables models to access up-to-date, contextual information during the conversation.

## MCP vs Traditional Tools

| Feature | **Traditional Tools** | **MCP Servers** |
|---------|---------------------|-----------------|
| **Setup** | Define individual functions | Connect to pre-built servers |
| **Scope** | Single function per tool | Multiple related tools per server |
| **Maintenance** | Custom code required | Server maintained by community |
| **Discovery** | Manual tool definition | Automatic tool discovery |
| **Context** | Limited to function parameters | Rich contextual data access |

## Provider Implementation Comparison

Before diving into WorkflowAI's approach, let's compare how OpenAI, Anthropic, and Mistral implement MCP:

### OpenAI Implementation (Responses API)

**Approach**: Tool-centric configuration via Responses API

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4.1",
    "tools": [
      {
        "type": "mcp",
        "server_label": "github",
        "server_url": "https://mcp.github.com/sse",
        "allowed_tools": ["search_repositories", "create_issue"],
        "require_approval": "never"
      }
    ],
    "input": "Check my repositories for security issues"
  }'
```

**Key Characteristics:**
- **Endpoint**: Uses `/v1/responses` (not chat/completions)
- **Configuration**: MCP servers configured in `tools` array with `type: "mcp"`
- **Tool Filtering**: `allowed_tools` parameter to limit available tools
- **Approval Control**: `require_approval` parameter for security
- **Server Identification**: `server_label` for naming servers

### Anthropic Implementation (Messages API)

**Approach**: Parameter-centric configuration via Messages API

```bash
curl https://api.anthropic.com/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: mcp-client-2025-04-04" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1000,
    "messages": [{"role": "user", "content": "Check my repositories for security issues"}],
    "mcp_servers": [
      {
        "type": "url",
        "url": "https://mcp.github.com/sse",
        "name": "github",
        "authorization_token": "ghp_xxxxxxxxxxxx",
        "tool_configuration": {
          "enabled": true,
          "allowed_tools": ["search_repositories", "create_issue"]
        }
      }
    ]
  }'
```

**Key Characteristics:**
- **Endpoint**: Uses standard `/v1/messages` API
- **Configuration**: Dedicated `mcp_servers` parameter
- **Beta Feature**: Requires `anthropic-beta: mcp-client-2025-04-04` header
- **Tool Control**: `tool_configuration` object for fine-grained control
- **Authentication**: Direct `authorization_token` in server config

### Mistral Implementation

**Approach**: Agent-centric configuration with Python SDK

**Note**: Mistral provides CURL examples for their general `/v1/agents/completions` API, but their MCP documentation only shows Python SDK examples, not raw API calls.

```python
# Python SDK example from Mistral docs
from mistralai import Mistral
from mistralai.extra.run.context import RunContext
from mistralai.extra.mcp.sse import MCPClientSSE, SSEServerParams

client = Mistral(api_key=api_key)
server_url = "https://mcp.github.com/sse"
mcp_client = MCPClientSSE(sse_params=SSEServerParams(url=server_url))

async with RunContext(model="mistral-medium-latest") as run_ctx:
    await run_ctx.register_mcp_client(mcp_client=mcp_client)
    
    run_result = await client.beta.conversations.run_async(
        run_ctx=run_ctx,
        inputs="Check my repositories for security issues"
    )
```

**Key Characteristics:**
- **Endpoint**: Uses `/v1/agents/completions` via Python SDK
- **Configuration**: MCP servers registered via `RunContext` and `register_mcp_client()`
- **Agent Management**: Agents created with `/v1/agents` endpoint
- **Python-Only**: No raw CURL examples for MCP integration
- **Conversation-Based**: Uses `conversations.run_async()` for execution

### WorkflowAI Hybrid Approach

**Best of Both Worlds**: Maintains OpenAI compatibility while offering flexible configuration

```bash
# Option 1: Extended tools parameter (OpenAI-style)
curl https://run.workflowai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer wai-xxx" \
  -d '{
    "model": "security-analyst/claude-3-7-sonnet-latest",
    "messages": [{"role": "user", "content": "Check my repositories for security issues"}],
    "tools": [
      {
        "type": "mcp_server",
        "mcp_server": {
          "type": "sse",
          "name": "github",
          "url": "https://mcp.github.com/sse",
          "auth": {"type": "bearer", "token": "ghp_xxx"},
          "allowed_tools": ["search_repositories", "create_issue"]
        }
      }
    ]
  }'

# Option 2: Dedicated mcp_servers parameter (Anthropic-style)
curl https://run.workflowai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer wai-xxx" \
  -d '{
    "model": "security-analyst/claude-3-7-sonnet-latest",
    "messages": [{"role": "user", "content": "Check my repositories for security issues"}],
    "extra_body": {
      "mcp_servers": [
        {
          "type": "sse",
          "name": "github", 
          "url": "https://mcp.github.com/sse",
          "auth": {"type": "bearer", "token": "ghp_xxx"},
          "allowed_tools": ["search_repositories", "create_issue"]
        }
      ]
    }
  }'
```

**Key Advantages:**
- **Full OpenAI Compatibility**: Uses standard `/v1/chat/completions` endpoint
- **Flexible Configuration**: Both tools-based and parameter-based approaches
- **Agent Integration**: Works with WorkflowAI's agent/version/deployment system
- **No Beta Headers**: Production-ready without experimental flags

### API Specification Comparison

| Feature | **OpenAI** | **Anthropic** | **Mistral** | **WorkflowAI** |
|---------|------------|---------------|-------------|----------------|
| **MCP Documentation** | CURL examples | CURL examples | Python SDK only | Both options |
| **Endpoint** | `/v1/responses` | `/v1/messages` | `/v1/agents/completions` | `/v1/chat/completions` |
| **Beta Required** | No | Yes (`mcp-client-2025-04-04`) | No | No |
| **MCP Location** | `tools` array | `mcp_servers` parameter | `RunContext.register_mcp_client()` | Both options |
| **Tool Filtering** | `allowed_tools` | `tool_configuration.allowed_tools` | Not documented | `allowed_tools` |
| **Authentication** | Headers/URL params | `authorization_token` | SDK OAuth flows | `auth` object |
| **Multi-server** | Multiple tool entries | Array of servers | Multiple `register_mcp_client()` calls | Both patterns |
| **OpenAI Compat** | Different endpoint | Different API | Different paradigm | Full compatibility |

## Supported MCP Server Types

WorkflowAI focuses exclusively on remote MCP servers:

### SSE Servers (Server-Sent Events)
Remote servers using Server-Sent Events. Perfect for real-time data and cloud services.

```python
client.chat.completions.create(
    model="security-analyst/claude-3-7-sonnet-latest", 
    messages=[{"role": "user", "content": "Check this code for vulnerabilities"}],
    extra_body={
        "mcp_servers": [{
            "type": "sse",
            "name": "semgrep",
            "url": "https://mcp.semgrep.ai/sse"
        }]
    }
)
```

### HTTP Servers (Streamable)
Servers using streamable HTTP transport for high-performance scenarios.

```python
client.chat.completions.create(
    model="data-analyst/gemini-2.5-pro-preview",
    messages=[{"role": "user", "content": "Analyze sales data from Q4"}],
    extra_body={
        "mcp_servers": [{
            "type": "http",
            "name": "analytics",
            "url": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer token"}
        }]
    }
)
```

## Authentication Strategies

WorkflowAI supports two authentication approaches for MCP servers:

### Strategy 1: UI-Configured Authentication

Configure authentication credentials in the WorkflowAI web application for reusable, secure access:

**TODO**: Setting API keys from the UI might not work properly - this behavior needs to be determined

**In WorkflowAI UI:**
1. Navigate to Agent Settings → MCP Servers
2. Add server with authentication details
3. Configure OAuth flows or store API keys securely

### Strategy 2: Dynamic Authentication

Pass authentication details directly in API requests for dynamic or temporary access:

```python
# Dynamic authentication in request
client.chat.completions.create(
    model="research-assistant/gpt-4o",
    messages=[{"role": "user", "content": "Search GitHub repositories"}],
    extra_body={
        "mcp_servers": [{
            "type": "sse",
            "name": "github",
            "url": "https://mcp.github.com/sse",
            "auth": {
                "type": "bearer",
                "token": os.getenv("GITHUB_TOKEN")
            }
        }]
    }
)
```

## Authentication Configuration

### Bearer Token Authentication
```python
{
    "mcp_servers": [{
        "type": "sse", 
        "name": "github",
        "url": "https://mcp.github.com/sse",
        "auth": {
            "type": "bearer",
            "token": "ghp_xxxxxxxxxxxx"
        }
    }]
}
```

### API Key Authentication
```python
{
    "mcp_servers": [{
        "type": "http",
        "name": "database",
        "url": "https://api.example.com/mcp",
        "auth": {
            "type": "api_key",
            "header": "X-API-Key",
            "value": "your-api-key"
        }
    }]
}
```

## Advanced Features

### Error Handling

...

## Combining with Existing Features

### MCP + Caching

**Important Consideration**: How should MCP tool calls interact with WorkflowAI's existing caching system? This behavior needs to be defined:

- Should MCP tool calls disable caching (like current `tools` behavior)?
- Should caching work with special considerations for MCP servers?
- Should different MCP servers have different caching behaviors?

*This is an open design question that requires further specification.*

Current implementation assumption:
```python
# MCP tool calls respect WorkflowAI's caching behavior
response = client.chat.completions.create(
    model="research-assistant/gpt-4o",
    messages=[{"role": "user", "content": "What's the latest on quantum computing?"}],
    temperature=0,  # Enable caching
    extra_body={
        "use_cache": "always",  # Force cache check
        "mcp_servers": [{
            "type": "sse",
            "name": "arxiv",
            "url": "https://mcp.arxiv.org/sse"
        }]
    }
)
```

### MCP + Deployments + Conversations

```python
# Initial request with MCP server
initial_response = client.chat.completions.create(
    model="code-reviewer/#1/production",
    messages=[{"role": "user", "content": "Review my latest commit"}],
    extra_body={
        "mcp_servers": [{
            "type": "sse",
            "name": "github",
            "url": "https://mcp.github.com/sse",
            "auth": {"type": "bearer", "token": "ghp-token"}
        }]
    }
)

# Follow-up using conversation state
followup_response = client.chat.completions.create(
    model="code-reviewer/#1/production", 
    messages=[{"role": "user", "content": "Apply the suggested changes"}],
    extra_body={
        "reply_to_run_id": initial_response.id,
        # MCP servers from initial request are automatically available
    }
)
```

## Security Considerations

### Authentication Best Practices

1. **Use Environment Variables**: Store sensitive tokens in environment variables, not in code
2. **Scope Permissions**: Use tokens with minimal required permissions
3. **Rotate Credentials**: Regularly rotate API keys and access tokens
4. **Monitor Usage**: Track MCP server usage for unusual patterns

### Safe Server Configuration

```python
# Good: Minimal permissions, specific scopes
{
    "type": "sse",
    "name": "github",
    "url": "https://mcp.github.com/sse", 
    "auth": {
        "type": "bearer",
        "token": os.getenv("GITHUB_TOKEN")  # Read-only token with repo scope
    }
}
```

### Data Privacy

- **User Consent**: Ensure users understand what data MCP servers can access
- **Data Boundaries**: Configure MCP servers with appropriate scope limitations  
- **Audit Logging**: Enable logging for MCP server interactions in production

## Troubleshooting

**TODO**: Comprehensive error handling and troubleshooting documentation will be added in a future release. This will include detailed error codes, common issues, and resolution strategies for MCP server integration.

## API Reference

### MCP Server Configuration Schema

```python
{
    "mcp_servers": [
        {
            "type": "sse|http",           # Required: Server type
            "name": "server-name",        # Required: Unique identifier
            "url": "https://...",         # Required: Server URL
            "headers": {...},             # Optional: HTTP headers
            "auth": {...}                 # Optional: Authentication config
        }
    ]
}
```

### Request Format Options

**Option 1: Extended Tools Parameter**
```python
tools = [
    # Traditional tools
    {"type": "function", "function": {...}},
    # MCP servers
    {"type": "mcp_server", "mcp_server": MCPServerConfig}
]
```

**Option 2: Separate MCP Servers Parameter**
```python
extra_body = {
    "mcp_servers": [MCPServerConfig, ...],
    "mcp_options": {
        "parallel_execution": True,
        "max_tools_per_server": 50,
        "error_handling": "graceful"
    }
}
```

### Response Format

MCP tool calls appear in the response like standard tool calls:

```json
{
    "choices": [{
        "message": {
            "role": "assistant",
            "content": null,
            "tool_calls": [{
                "id": "call_abc123",
                "type": "function", 
                "function": {
                    "name": "search_papers",
                    "arguments": "{\"query\": \"quantum computing\"}"
                },
                "mcp_server": "arxiv"  # Additional field indicating MCP server
            }]
        }
    }],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "mcp_servers_used": ["arxiv", "database"]  # Additional field
    }
}
```

## Provider Documentation References

For additional context and implementation details, refer to the official MCP documentation from other providers:

- **OpenAI MCP Documentation**: [OpenAI Agents SDK - Model Context Protocol](https://openai.github.io/openai-agents-python/mcp/)
- **Mistral MCP Documentation**: [Mistral AI - MCP Integration](https://docs.mistral.ai/agents/mcp/#how-to-use-a-remote-mcp-server-with-authentication)
- **Anthropic MCP Documentation**: [Anthropic - MCP Connector](https://docs.anthropic.com/en/docs/agents-and-tools/mcp-connector)
- **MCP Specification**: [Model Context Protocol Official Specification](https://modelcontextprotocol.io/specification/2025-03-26/index)