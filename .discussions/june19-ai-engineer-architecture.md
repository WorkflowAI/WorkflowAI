# AI Engineer Agent architecture

- [ ] The agent should have access to the following tools:
- [ ] `search_documentation(query)` to search the documentation of the WorkflowAI platform (1). Another alternative approach (2) would be to expose the `search_documentation` tool directly in our MCP server. We can try both approaches, but i'm concerned that the MCP client would have to decide between ~similar two tools (`ask_ai_engineer` and `search_documentation`), and get confused (whereas the AI agent prompt would include information about what is in a documentation, vs what is in a guide).

- [ ] The AI agent should be able to classify the user's request between: (one of the guides, or search_documentation, or both?) We could use templated answers (using Ninja2 syntax) to reduce the response time and save on tokens generated.

For example, the AI agent could generate only these tokens:

```
I see you're asking about building a new agent. Here is our guide:
{{building_new_agent_guide}}

About your question on the business model, our ____ <answer from `search_documentation` tool call result>
```

- [ ] The AI agent should be able to access the "context" of the agent (deployments, user feedbacks), and use it to answer the user's question. See the [CurrentAgentContext](https://github.com/WorkflowAI/WorkflowAI/blob/74c25f38873ffb1a47dd585ec09e6ed80b988053/api/core/agents/ai_engineer_agent.py#L126) class. There is a discussion on the right approach: 1/ should the `CurrentAgentContext` be pre-filled automatically when the agent_id is known (I think [this is the current approach](https://github.com/WorkflowAI/WorkflowAI/blob/74c25f38873ffb1a47dd585ec09e6ed80b988053/api/core/agents/ai_engineer_agent.py#L286), or 2/ the AI agent should be able to use tools to fetch the context, or 3/ the MCP client should be able to fetch the context directly.

## Guides

- [ ] Building a new agent
- [ ] Migrating an existing agent
- [ ] Improving and debugging an existing agent

## TODO:

- [ ] add `reply_to_conversation_id` to give memory to the AI Engineer agent.
- [ ] compare different models for the AI agent, including reasoning models.

## Resources

- https://platform.openai.com/docs/guides/reasoning-best-practices?utm_source=chatgpt.com
- https://cookbook.openai.com/examples/gpt4-1_prompting_guide?utm_source=chatgpt.com
- https://github.com/anthropics/anthropic-cookbook/blob/main/patterns/agents/prompts/research_lead_agent.md
- https://cookbook.openai.com/examples/enhance_your_prompts_with_meta_prompting?utm_source=chatgpt.com
