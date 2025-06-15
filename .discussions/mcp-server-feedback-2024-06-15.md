# MCP-Server Feedback - June 15, 2024

## Use-case #1:

> Ask Cursor: using WorkflowAI, can you create a new agent that summarize a text?

- [ ] Does the AI engineer encourages the use the input variables? At least in the code generated, input variables are not used.

Generated the following completion code:
```python
completion = client.beta.chat.completions.parse(
    model="text-summarizer/gpt-4o",  # Agent name following WorkflowAI convention
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please summarize the following text:\n\n{text}"}
    ],
    response_format=TextSummary,
    temperature=0.3  # Slightly creative but consistent
)
```

- [ ] The `base_url` was set to `api.workflowai.com` instead of `run.workflowai.com`. We need more context on when to use `api.workflowai.com` and when to use `run.workflowai.com`.

- [ ] agent prefix needs to be added to the `metadata` field as the preferred way to identify the agent. https://github.com/WorkflowAI/fumadocs-demo/blob/main/demo/my-app/content/docs/observability/index.mdx#identify-your-agent (probably just requires the documentation repo to be merged in `workflowai/workflowai` and up-to-date?)

- [ ] how does the integration between the IDE and our playground is expected to work? I would imagine that the AI engineer should be able to return a list of "next steps" after the agent was created, and open the playground?

> Ask Cursor: how can i compare different models?

- [ ] Interestingly, the MCP server/client did not try to open the playground, but instead generated code with different models (using `list_models` tool). What's the right way to handle a "compare models" use-case?

> Ask Cursor: can you open the playground on workflowai?

- [ ] the MCP client was not able to open the playground directly.

----

- [ ] `list_models` tool returns `supports.structured_output` as `false` for some models, which made Cursor to not use the `response_format` parameter. Actually, the `/v1/models` response includes a lot of fields that should not be exposed.

More generally, the list of fields in the `/v1/models` response should be explicity selected, instead of including all the fields from our internal configuration file.
See this PR: https://github.com/WorkflowAI/WorkflowAI/pull/453

- [ ] should `list_models` include some sort of `usage_guidelines` for each model? For example, how would a agent know that `-preview` models from Google should not be used in production because of low rate limits?

```json
{
  "id": "google/gemini-1.5-pro-preview",
  "object": "model",
  "created": 1234567890,
  "usage_guidelines": "Preview model with lower rate limits - not recommended for production use"
}
```

