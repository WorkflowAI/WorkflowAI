# MCP

## Week 1

### Demo

in Cursor, setup a new repo with MCP enabled for WorkflowAI.

then write the following goal:

```
using WorkflowAI:
- write a AI agent that can summarize a text. if there is a URL in the text, extract the text from the URL to be able to write an accurate summary.
- find a model that works well for this task
- and is cheap.
give me 3 options (models) from choose from with pros and cons.
```

how well can the agent in Cursor do?

what tools needs to be exposed in the MCP?
- `chat` to interact with our own AI agent, or maybe `search_documentation` to search the documentation of WorkflowAI?
- my guess is that a `chat` would be more powerful because the agent could ask follow up questions. (basically the chat is a better interface for humans, so I'm assuming chat is a better interface for AI agents too)
- the tool `chat` needs to have a way to require a `chat_id` parameter that would be consistent across the chat (implemented below).

```python
# server.py
from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")

# https://gofastmcp.com/servers/tools
@mcp.tool
async def chat(chat_id: str, message: str) -> str:
    # docstring is passed as the tool's description by default
    """
    Ask questions about:
    - how to use WorkflowAI, get help with implementation.
    - how to use the tools available in WorkflowAI.
    - how to use the models available in WorkflowAI.
    - send error messages and get help with implementation.

    The chat_id needs to be consistent across a chat. If you want to start a new chat, you need to provide a new chat_id.

    Example:
    message: "I want to build a chatbot that can check the weather in a city. How can I do that?"
    chat_id: "123"

    message: "This error is happening <error message>, can you help me fix it?"
    chat_id: "123"
    """
    return "Hello, world!"

if __name__ == "__main__":
    mcp.run()
```