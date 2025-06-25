# AI Engineer Agent architecture

- [ ] The agent should have access to the following tools:
- [ ] `search_documentation(query)` to search the documentation of the WorkflowAI platform (1). Another alternative approach (2) would be to expose the `search_documentation` tool directly in our MCP server. We can try both approaches, but i'm concerned that the MCP client would have to decide between ~similar two tools (`ask_ai_engineer` and `search_documentation`), and get confused (whereas the AI agent prompt would include information about what is in a documentation, vs what is in a guide).

- [ ] The AI agent should be able to classify the user's request between: (one of the guides, or search_documentation, or both?) We could use templated answers (using Ninja2 syntax) to reduce the response time and save on tokens generated.

See the following prompt:

```python
prompt = """
You are an expert AI engineer building AI agents on top of WorkflowAI platform.
You work with other agents to design, build, evaluate, debug and improve agents.

## Available Tools:
- search_documentation(query) - Use this to search the WorkflowAI platform documentation for specific technical questions not covered by the guides below.

## Available Guides:
Based on the user's needs, you can return one or more of the following guides:

<guides>
<guide>
<variable>{{building_new_agent_guide}}</variable>
<when_to_use>When the user wants to build a new agent from scratch.</when_to_use>
</guide>
<guide>
<variable>{{migrating_existing_agent_guide}}</variable>
<when_to_use>When the user wants to migrate an existing agent to WorkflowAI.</when_to_use>
</guide>
<guide>
<variable>{{improving_and_debugging_existing_agent_guide}}</variable>
<when_to_use>When the user wants to improve or debug an existing agent already running on WorkflowAI. For example, when the user wants to find a faster model to run the agent or, or when the user reports an issue with the agent</when_to_use>
</guide>
</guides>

IMPORTANT: When returning a guide, return ONLY the Jinja2 template variable exactly as shown (including the double curly braces). Do NOT expand or fill in the template with actual guide content. The template will be processed later by the system.

<examples>
<example>
<user_message>I want to build a new agent</user_message>

<reply>
Relevant guides:
{{building_new_agent_guide}}
</reply>
</example>

<example>
<user_message>I want to build a new agent, and also, what is the business model of WorkflowAI?</user_message>

You should call the `search_documentation` tool to answer the question about the business model of WorkflowAI.

<reply>
About your question on the business model, <answer from `search_documentation` tool call result>...

Relevant guides:
{{building_new_agent_guide}}
</reply>
</example>
</examples>

```

- [ ] The AI agent should be able to access the "context" of the agent (deployments, user feedbacks), and use it to answer the user's question. See the [CurrentAgentContext](https://github.com/WorkflowAI/WorkflowAI/blob/74c25f38873ffb1a47dd585ec09e6ed80b988053/api/core/agents/ai_engineer_agent.py#L126) class. There is a discussion on the right approach: 1/ should the `CurrentAgentContext` be pre-filled automatically when the agent_id is known (I think [this is the current approach](https://github.com/WorkflowAI/WorkflowAI/blob/74c25f38873ffb1a47dd585ec09e6ed80b988053/api/core/agents/ai_engineer_agent.py#L286), or 2/ the AI agent should be able to use tools to fetch the context, or 3/ the MCP client should be able to fetch the context directly.

## Notes

June 20:

- Keep the `ask_ai_engineer` tool, we don't know yet if in the future there is a big difference between a `ask_ai_engineer` and a `search_documentation` tool or even letting Cursor browse the public.
- Make the guides public in the docs.

June 22:

- [x] Pierre suggested a new `search_documentation` tool: https://linear.app/workflowai/issue/WOR-5025/search-documentation-tool that will be used to return knowledge about the WorkflowAI platform and let the MCP client do the work. In that path, we will not implement the `ask_ai_engineer` tool.

## Guides

- [ ] Building a new agent (See docsv2/content/docs/use-cases/new_agent.mdx)
- [ ] Migrating an existing agent (not started yet)
- [ ] Improving and debugging an existing agent (not started yet)

## TODO:

- [x] Expose "guides" publicly, in the `guides` section of the docs.
- [x] Add `metadata` in the `new_agent` guide.
- [ ] write all guides for the AI Engineer agent.
- [x] add a guide about "deployments". (we have `deployments/index.mdx` already)
- [ ] UX: how to connect the web app and the AI Engineer agent?
- [ ] (maybe) write a guide about "when a new model comes out, how to test it?"
- [ ] prototype how to support multiple programming languages.
- [ ] remove TODOs from the guides.

_Later:_

- [ ] add `reply_to_conversation_id` to give memory to the AI Engineer agent.
- [ ] compare different models for the AI agent `model` itself, including reasoning models.

## Resources

- https://platform.openai.com/docs/guides/reasoning-best-practices?utm_source=chatgpt.com
- https://cookbook.openai.com/examples/gpt4-1_prompting_guide?utm_source=chatgpt.com
- https://github.com/anthropics/anthropic-cookbook/blob/main/patterns/agents/prompts/research_lead_agent.md
- https://cookbook.openai.com/examples/enhance_your_prompts_with_meta_prompting?utm_source=chatgpt.com
