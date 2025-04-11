# Runs
A run is a single execution of an agent. For example:

![Run view](</docs/assets/images/runs/run-view.png>)

Each run has a unique identifier and can be accessed directly via a URL, like [this example run](https://workflowai.com/docs/agents/review-summary-generator/runs/0195dd7a-6977-7197-7ec3-4fc44ade50dc).

{% hint style="warning" %}
**Privacy Note**: Run URLs are private by default and only accessible to users within your organization. They are not publicly accessible, ensuring your data and AI interactions remain secure.
{% endhint %}

By default, WorkflowAI stores all runs, available in the "Runs" section. You can view a list of all runs for a specific agent, like [this example runs list](https://workflowai.com/docs/agents/review-summary-generator/1/runs?page=0).

![Run list](</docs/assets/images/runs/list-runs.png>)

## Why storing all runs?
- **Observability**: Understand how the AI is performing by tracking and analyzing its outputs over time.
- **Saving cost**: For the same input and model versions, cached runs can be served without triggering a new LLM call, reducing costs to $0 for serving cached runs.
- **Fine-Tuning and distillation**: Saving all runs is required for fine-tuning models and distillation processes.

## How to search runs?
WorkflowAI provides a powerful search – available under the "Runs" section – to find specific runs:

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/d2f9b4f417bda8734b0a6f474f621d29/watch" %}

{% hint style="info" %}
**Architecture**: Under the hood, runs are stored in a Clickhouse database, which is optimized for handling large amounts of data, and for fast search and aggregation queries. Clickhouse also compresses data, which reduces storage costs. Learn more about Clickhouse [here](https://clickhouse.com/docs/en/introduction).
{% endhint %}

## View a run's prompt and response

WorkflowAI provides full transparency into the interaction with the LLM. You can easily examine both the raw prompt sent to the model and the complete response received:

1. Navigate to any run's detail view
2. Click the "View Prompt" button to see the exact instructions sent to the LLM

You can try viewing the prompt for [this example run](https://workflowai.com/docs/agents/review-summary-generator/runs/0195dd7a-6977-7197-7ec3-4fc44ade50dc).

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/9d2ee8a8afe315d10b5f8a7157f8ad22/watch" %}

## Try in playground

To import a run into the playground, you can use either:
- the "Try in playground" button in the run detail view, which will automatically import the run input, and the version used to generate the run.
- only import the run input, by clicking on the "Try Input in Playground" button in the run detail view.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/7e570d6af89ed145009edda4289444b9/watch" %}

## Delete a run

Deleting a specific run is not possible. However, you can delete all runs for a specific agent, by deleting the agent.