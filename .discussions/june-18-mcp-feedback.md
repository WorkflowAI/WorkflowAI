`fetch_run_details` returns:

```json
{
  "result": {
    "id": "019784a3-8689-72c9-31a9-fd74df201b8b",
    "agent_id": "city-info-agent",
    "agent_schema_id": 2,
    "status": "success",
    "agent_input": {
      "workflowai.messages": [],
      "city": "Paris "
    },
    "agent_output": {
      "city": "Paris",
      "country": "Germany",
      "capital": "Berlin"
    },
    "duration_seconds": 2.3,
    "cost_usd": 0.000081,
    "created_at": "2025-06-18T20:03:18.793000+00:00",
    "user_review": null,
    "ai_review": null,
    "error": null,
    "conversation_id": "019784a3-8e7b-7389-92d4-61ad5b1c87fd"
  }
}
```

- [ ] there is no `agent_version_id` accessible?

So I worked on a new Run model in `_mcp_models.py` that includes the `agent_version_id` field.

I'm assuming that unsaved versions still have a `version_id` field, right?

- [ ] the LLM completions are not returned in the current response, which can make the agent debugging harder. I think the LLM completions should be returned in the response.
- [ ] I'm not sure that `agent_input` and `agent_output` needs to be returned in the response. `agent_input` might be useful to isolate the variables from the prompt. `agent_output` would actually be included in the LLM completions field.
- [ ] I don't think that `workflowai.messages[]` should be returned in the response.

- [ ] when returning a Run, we need to make sure that we return the output schema (including the examples and descriptions), as well. especially, for models that support structured outputs natively, I think the `response_format` is not part of the `llm_completions` and so the `response_format` should be included in the Run object.

- [ ] for error like `failed_generation`, currently, the `agent.output` returned is empty.

```json
"agent_output": {}
```

I think that adding `llm_completions` would might fix the issue, where currently, a MCP client would not be able to know what the LLM completion was.

- [ ] `temperature` is not returned in the response, TODO: check the parameters from /v1/chat/completions that needs to be included as well.
