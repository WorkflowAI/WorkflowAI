---
title: Runs
---

import { Tabs, Tab } from "fumadocs-ui/components/tabs"

## Definition

A run is ...

## Metadata

<Callout type="warning">
We highly recommend reading this section. Metadata is essential for debugging and troubleshooting your AI agents.
</Callout>

You can attach custom metadata to a run. Think of metadata as the fields you or your AI engineer will use for debugging and troubleshooting. For example, when a customer reports an issue, you or your AI engineer will want to search by `user_id`, `customer_id`, or `session_id` to find their specific runs. Add these identifiers as metadata so you or your AI engineer can easily trace problems back to specific users, sessions, or contexts.

### Setup

<Callout type="info">
**Using WorkflowAI's AI Engineer**:

```
Add the following metadata to the agent "my-agent-id" using WorkflowAI:
user_id, user_email.
```
</Callout>

<Tabs items={['Python', 'TypeScript', 'cURL']}>
<Tab value="Python">
```python
completion = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello, how are you?"}],
    metadata={
        "agent_id": "my-agent-id", # [!code highlight]
        "user_id": "123", # [!code highlight]
        "language": "english" # [!code highlight]
    }
)
```
</Tab>
<Tab value="TypeScript">
```typescript
const completion = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [{"role": "user", "content": "Hello, how are you?"}],
    metadata: {
        agentId: "my-agent-id", // [!code highlight]
        userId: "123", // [!code highlight]
        language: "english" // [!code highlight]
    }
});
```
</Tab>
<Tab value="cURL">
```sh
curl -X POST https://run.workflowai.com/v1/chat/completions \
-H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello, how are you?"}],
    "metadata": {
        "agent_id": "my-agent-id",
        "user_id": "123",
        "language": "english"
    }
}'
```
</Tab>
</Tabs>

### Special metadata keys

| Key | Description | Example | Added automatically |
|-----|-------------|---------|-------------------|
| `agent_id` | The ID of the agent that generated the run | `summarizer-agent`, `translation-agent` | No |
| `conversation_id` | Groups related runs into [conversations](/docs/observability/conversations) for multi-turn interactions | `01234567-89ab-cdef-0123-456789abcdef` | Yes |
| `environment` | The environment of the run | `production`, `staging`, `development` | Yes, when using a deployment |
| `source` | The source of the run request | `my+app` (from proxy), `WorkflowAI` (from web app) | Yes |
| `temperature` | The temperature setting used in the LLM | `0.7`, `1.0` | Yes |
| `schema` | The schema used | `1`, `2` | Yes |
| `review` | TBD | TBD | TBD |

<Callout type="info">
  TODO: @guillaume to check all the metadata keys and add them to the table.
  Double check the value I listed above too. For example, `dev` or `development`?
</Callout>

<Callout type="info">
  TODO: @guillaume is there any limit on the metadata size?
</Callout>

Then, you can [search for runs by metadata](/docs/observability/runs#search-runs).

## View runs for a specific agent

### Using the UI

A run is a single execution of an agent. For example:

![Run view](/images/runs/run-view.png)

Each run has a unique identifier and can be accessed directly via a URL, like [this example run](https://workflowai.com/docs/agents/review-summary-generator/runs/0195dd7a-6977-7197-7ec3-4fc44ade50dc).

<Callout type="warning">
**Privacy Note**: Run URLs are private by default and only accessible to users within your organization. They are not publicly accessible, ensuring your data and AI interactions remain secure.
</Callout>

By default, WorkflowAI stores all runs, available in the "Runs" section. You can view a list of all runs for a specific agent, like [this example runs list](https://workflowai.com/docs/agents/review-summary-generator/1/runs?page=0).

![Run list](</images/runs/list-runs.png>)

#### Metadata

When viewing a run, you can see the metadata added to the run.

TODO: @anya add screenshot of run view with metadata

### Using the API

...

### Using MCP

...

## Search runs

### Using the UI

WorkflowAI provides a powerful search – available under the "Runs" section – to find specific runs:

<div style={{ position: 'relative', paddingTop: '56.25%' }}>
  <iframe
    src="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/d2f9b4f417bda8734b0a6f474f621d29/iframe?autoplay=false&muted=false&controls=true"
    style={{
      border: 'none',
      position: 'absolute',
      top: 0,
      left: 0,
      height: '100%',
      width: '100%'
    }}
    allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;"
    allowFullScreen={true}
  ></iframe>
</div>

<Callout type="info">
**Architecture**: Under the hood, runs are stored in a Clickhouse database, which is optimized for handling large amounts of data, and for fast search and aggregation queries. Clickhouse also compresses data, which reduces storage costs. Learn more about Clickhouse [here](https://clickhouse.com/docs/en/introduction).
</Callout>

### Using the API

...
TODO: @guillaume how to search for runs by metadata?

### Using MCP

...
```
(show text that will trigger the search_run tool)
```

## View a run's prompt and response (completions)

### Using the UI

WorkflowAI provides full transparency into the interaction with the LLM. You can easily examine both the raw prompt sent to the model and the complete response received:

1. Navigate to any run's detail view
2. Click the "View Prompt" button to see the exact instructions sent to the LLM

You can try viewing the prompt for [this example run](https://workflowai.com/docs/agents/review-summary-generator/runs/0195dd7a-6977-7197-7ec3-4fc44ade50dc).

<div style={{ position: 'relative', paddingTop: '56.25%' }}>
  <iframe
    src="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/9d2ee8a8afe315d10b5f8a7157f8ad22/iframe?autoplay=false&muted=false&controls=true"
    style={{
      border: 'none',
      position: 'absolute',
      top: 0,
      left: 0,
      height: '100%',
      width: '100%'
    }}
    allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;"
    allowFullScreen={true}
  ></iframe>
</div>
