## Deployments

> is there a way to use workflowai to update the prompt without changing my code?

Cursor made some mistakes:

- [ ] used playground.workflowai.dev --- because the playground URL was not explicitly mentioned? I need to check more.
- [ ] also, generated the following code:

```python
model=f"product-review-sentiment-analyzer/#1/{environment}",  # Format: agent-name/#schema/environment
```

that will not work until the agent is deployed.

flow (from the MCP client perspective):

- use `search_documentation` to learn more about deployments.
- fetch existing deployments for a given agent_id. Requires https://linear.app/workflowai/issue/WOR-5045/add-deployment-information-to-get-agent-mcp-tool to be implemented.
- if there is no deployment, create a new one. creating a new deployment currently requires a `version_id` in the `deploy_agent_version` tool.

- [ ] TODO: The documentation from `deployments/index` needs to be updated to be "read" by a MCP client.

---

## Deployments (2)

> can you update to use the production enviroment from workflowai?

Cursor struggled to update to the production environment code:

- first did not put any schema "#n" in the `model` parameter (but managed to fix this error itself)
- but did not manage to update the `messages` parameter to `[]` empty.

One solution would be to have a `get_code(version)` tool in the MCP to clarify how to update the code. Maybe `get_code` return pseudo-code that are applicable to all programing languages.

---

## Update the code to a new version 2.1

I noticed, while using this prompt:

> update the code to version 2.1

that the MCP client was confused between the way deployments works, and pointing to a specific version (2.1) and generated the following code:

```python
model="agent-id/2.1"
```

My intention was the "end-user" was for the code to be updated with `model=<model from 2.1>` and the list of `messages` to be updated with the prompt from 2.1.

But the MCP client using `model="agent-id/2.1"` is also not completely stupid.

- What is the correct way to update the code to a new version? I think we need to decide.

If we want to update `model`, `messages` and other parameters in the code, we might need to introduce a `get_code` tool in the MCP to clarify.

Using the following prompt, which is more explicit:

> can you use the version 2.1 model and prompt?

Indeed, the MCP client updated the `model` and `messages` parameters in the code, this time.

## search runs for a given enviroment

I did a few tests with the following prompt:

> how would you search for runs that for a given environment?

and the MCP client is confused by the right way to use `search_runs`.

So I updated the `search_runs` tool description to clarify that the "version" field can be used to search for both version IDs (e.g., "2.1") and deployment environments (e.g., "dev", "staging", "production").
Needs to be tested.
