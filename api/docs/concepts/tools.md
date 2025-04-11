# Tools

## What are tools?

Tools enable AI agents to:
|   |   |
|----------|----------|
| **Access External Data** | Web searches, web scraping, databases, APIs, files |
| **Perform Actions** | Form submissions, code execution, API calls, custom functions |

Tools have two forms:
| **Custom Tools** | Developer-defined tools.                                                                 |
|-----------------------|-----------------------------------------------------------------------------------------|
| **Hosted Tools**      | WorkflowAI-built tools (e.g., *search-web*, *browser-text*).

Hosted tools do not require any code, or engineering effort. But custom tools will require you to write code to handle the tool calls.

## Custom Tools

Custom tools are tools specific to your application. You are responsible for running these tools when they are called by the AI agent.

### Add a new tool

#### Using the playground



#### Using code

{% hint style="info" %}
Adding a custom tool through code is currently only available with our Python SDK. Read the documentation for [adding custom tools](../sdk/python/tools.md).
{% endhint %}

### Handling tool calls

When the model returns a tool call, you need to execute the tool and return the result. 

## Hosted Tools

### What hosted tools are available?
WorklfowAI supports and manages the following tools:
- `@search`: search the web to answer a question
- `@browser-text`: navigate on webpages (text-only)

We're working on adding more tools, if you need any specfic tool, please open a discussion on [GitHub](https://github.com/workflowai/workflowai/discussions/categories/ideas) or contact us on [Slack](https://workflowai.com/slack).

### How to enable tools?

[todo: explain how to enable tools]
From the playground, under "Instructions", tap on the tools you want to enable.

[image]

### How are tools billed?
Tools are billed independently from the LLM inference costs.
- `@search` tool: $0.... per search
- `@browser-text` tool: $0.... per webpage