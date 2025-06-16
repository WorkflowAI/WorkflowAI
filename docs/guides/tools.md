# Tools

## What are tools?

Tools are a way to extend the capabilities of your AI agent.

Real-life use cases for tools:
- Search the web to gather the latest news about a company or topic.
- Browse a specific web page to extract information for a report.
- Execute a SQL query to fetch monthly sales data from a company database.
- Search in a vector database to find similar documents or images based on content.
- Send an email to a prospect after identifying information about their company online.

## Types of tools

There are two types of tools:

- **Hosted Tools**: Built-in tools provided by WorkflowAI (such as web search and browser). Hosted tools require no code or engineering effort to use, but offer limited customization.
- **Custom Tools**: Tools you define and implement yourself. Custom tools require you to write code to handle tool calls, but they are fully customizable to your needs.

If you're new to using tools or want to quickly try out a capability, we recommend starting with a hosted tool (if one fits your use case), as they are the fastest and easiest way to get started.

## What hosted tools are available?

WorkflowAI currently supports tools for:
- Web search: using Google and Perplexity
- Browser: using a text-based browser

## How to use hosted tools?

### From code

To add a hosted tool to your agent, find the tool name below (`@tool`) and add it to your agent prompt.

For example, to use the `@google-search` tool, you can add the following to your agent prompt:

```python
messages = [
{
  "role": "system",
  "content": "Use @google-search to find the weather in {{location}}."
},
]
```

WorkflowAI will automatically add the tool mentioned in the `tools` parameter sent to the LLM.

### From the Playground

[TODO: adjust when the proxy playground is available with tools]

Tools can be added in the Playground by either:
1. Describing the use case to the playground chat agent 
2. Under "Version" tap on the tools you want to enable.

[TODO: video how to add a tool from the playground]
{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/12ee172f6c8f7cd9448fda2579088d7f/watch" %}

### Web search

WorkflowAI supports two web search tools from Google and Perplexity:
- `@google-search` makes a web search using Google
- `@perplexity-sonar-pro` makes a web search using Perplexity's Sonar Pro model

{% tabs %}

{% tab title="Google Search" %}
```python
messages = [
    {
        "role": "system",
        "content": "Use @google-search to find the weather in {{location}}."
    }
]

We use https://serper.dev/ for our Google search queries.
```
{% endtab %}

{% tab title="Perplexity" %}
```python
messages = [
    {
        "role": "system",
        "content": "Use @perplexity-sonar-pro to summarize the latest news about {{topic}}."
    }
]
```
{% endtab %}

{% endtabs %}

### Browser (text-only)

Use the tool `@browser-text` to extract text from a web page. Note that this tool only supports text-based browsing.

```python
messages = [
    {
        "role": "system",
        "content": "Use @browser-text to extract the company name, number of employees, and email address from {{company_url}}."
    }
]
```

{% hint style="info" %}
We're working on adding more tools, if you need any specfic tool, please open a discussion on [GitHub](https://github.com/workflowai/workflowai/discussions/categories/ideas) or [Discord](https://discord.com/invite/auuf8DREZh)
{% endhint %}

## Custom tools

### From code

WorkflowAI is fully compatible with the `tools` parameter from the OpenAI `chat.completions` API, so you can use your existing code without modification.

For more details, refer to OpenAI's documentation on [tools and function calling](https://platform.openai.com/docs/guides/function-calling).

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current temperature for a given location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City and country e.g. Bogotá, Colombia"
                }
            },
            "required": [
                "location"
            ],
            "additionalProperties": False
        },
        "strict": True
    }
}]

completion = client.chat.completions.create(
    model="gpt-4.1",
    messages=[{"role": "user", "content": "What is the weather like in Paris today?"}],
    tools=tools
)

print(completion.choices[0].message.tool_calls)
```

#### Supported parameters

[TODO: @guillaq]
- `strict` 