# Tools

## What are tools?

Tools enable AI agents to:
|   |   |
|----------|----------|
| **Access External Data** | Web searches, web scraping, databases, APIs, files |
| **Perform Actions** | Form submissions, code execution, API calls, custom functions |

Tools have two forms:
| **Custom Tools** | Developer-defined tools. Custom tools will require you to write code to handle the tool calls.                                                                |
|-----------------------|-----------------------------------------------------------------------------------------|
| **Hosted Tools**      | WorkflowAI-built tools (e.g., *search-web*, *browser-text*). Hosted tools do not require any code or engineering effort.


## Custom Tools

Custom tools are tools specific to your application. You are responsible for running these tools when they are called by the AI agent.

Adding a custom tool through code is currently only available with our Python SDK. Read the documentation for [adding custom tools](../sdk/python/tools.md).

## Hosted Tools

### What hosted tools are available?
WorklfowAI supports and manages the following tools:
- `@browser-text` allows fetching the content of a web page (text-only)
- `@google-search` allows performing a web search using Google's search API
- `@perplexity-sonar-pro` allows performing a web search using Perplexity's Sonar Pro model

We're working on adding more tools, if you need any specfic tool, please open a discussion on [GitHub](https://github.com/workflowai/workflowai/discussions/categories/ideas) or [Discord](https://discord.gg/jSahs44g)

### How to enable tools?

Tools can be added in the Playground by either:
1. Describing the use case to the playground chat agent 
2. Under "Instructions" tap on the tools you want to enable.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/12ee172f6c8f7cd9448fda2579088d7f/watch" %}
