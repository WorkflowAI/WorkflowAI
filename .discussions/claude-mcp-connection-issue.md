# Claude MCP Server Connection Issue

## Problem Description

Connecting to our WorkflowAI MCP server using Claude code does not work as expected. Users are unable to establish a successful connection when following the standard MCP server setup instructions.

## How to Reproduce

### 1. Add the WorkflowAI MCP Server to Claude

```bash
claude mcp add workflowai <https://run-preview.workflowai.com/mcp/sse> --transport sse -H "Authorization: Bearer YOUR_API_KEY_HERE"
```

Replace `YOUR_API_KEY_HERE` with your actual WorkflowAI API key.

### 2. Test MCP Server Configuration

To verify that the MCP server is properly configured:

1. Start Claude:
   ```bash
   claude
   ```

2. Use the MCP command to check server status:
   ```
   /mcp
   ```

This will show you the status of all configured MCP servers and confirm that the WorkflowAI server is connected.

## Expected Behavior

The MCP server should connect successfully and show as "connected" when checking the server status.

## Actual Behavior

The connection fails or shows an error state when attempting to connect to the WorkflowAI MCP server.

## Additional Information

- **Server URL**: `https://run-preview.workflowai.com/mcp/sse`
- **Transport**: SSE (Server-Sent Events)
- **Authentication**: Bearer token required

## Status

🔍 **Investigation needed** - This issue requires further investigation to determine the root cause of the connection failure.

## Related Links

- [MCP Documentation](https://modelcontextprotocol.io/)
- [WorkflowAI MCP Server Documentation](../docs/)

---

*Created: $(date +%Y-%m-%d)*
*Last Updated: $(date +%Y-%m-%d)*