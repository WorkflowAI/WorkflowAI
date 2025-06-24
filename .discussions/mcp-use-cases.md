## Deployments

> is there a way to use workflowai to update the prompt without changing my code?

Cursor made some mistakes:

- [ ] used playground.workflowai.dev --- because the playground URL was not explicitly mentioned?
- [ ] also, generated the following code:

```python
model=f"product-review-sentiment-analyzer/#1/{environment}",  # Format: agent-name/#schema/environment
```

that will not work until the agent is deployed.

flow (from the MCP client):

- `search_documentation`
- fetch existing deployments for a given agent_id. Requires https://linear.app/workflowai/issue/WOR-5045/add-deployment-information-to-get-agent-mcp-tool to be implemented.
- if there is no deployment, create a new one. creating a new deployment currently requires a `version_id` in the `deploy_agent_version` tool.

- [ ] The documentation from `deployments/index` needs to be updated to be "read" by a MCP client.

---

- [ ] Some pages needs to be updated to be marked as "private" (e.g., `use-cases/mcp.private.mdx`). https://linear.app/workflowai/issue/WOR-5068/implement-private-page-functionality-for-documentation.

Because otherwise `search_documentation` will return information that is not meant to be public yet (new features, ..).

---

## ...
