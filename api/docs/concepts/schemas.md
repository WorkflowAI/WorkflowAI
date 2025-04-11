# Schemas
## What are schemas?
An AI feature has at least one schema. Each schema define:
- an input structure
- an output structure

For example, a [feature that answer question about a PDF](https://workflowai.dev/workflowai/tasks/pdf-question-answering/1/schemas) is represented:

![alt text](/docs/assets/images/schema.png)

{% tabs %}
{% tab title="Python" %}
{% hint style="info" %}
WorkflowAI uses [Pydantic](https://docs.pydantic.dev/) to define schemas.
{% endhint %}

```python
class PdfQuestionAnsweringTaskInput(BaseModel):
    pdf_document: Optional[File] = None
    question: Optional[str] = None

class SupportingQuote(BaseModel):
    quote: Optional[str] = None
    page_number: Optional[float] = None

class PdfQuestionAnsweringTaskOutput(BaseModel):
    answer: Optional[str] = None
    supporting_quotes: Optional[list[SupportingQuote]] = None
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
interface PdfQuestionAnsweringTaskInput {
    pdf_document?: File;
    question?: string;
}

interface SupportingQuote {
    quote?: string;
    page_number?: number;
}

interface PdfQuestionAnsweringTaskOutput {
    answer?: string;
    supporting_quotes?: SupportingQuote[];
}
```
{% endtab %}
{% endtabs %}

## Examples
For example, if you want an agent to summarize a text, the input is a text, and the output is a summary. If you want this agent to summarize a text in a specific language, you'll need to add a language parameter to the input. The inputs are like all the variables the LLM will have access to. The outputs are the different variables the LLM will generate.

{% hint style="info" %}
When using WorkflowAI web-app, you can write what you want the agent to do, and the web-app will generate a schema for you.
{% endhint %}

## Why are schemas a good idea?
Clear input and output structures (=schemas) have a few benefits:
1. simplify integration with a backend by providing a clear interface
2. provide output consistency
3. increase the quality of LLM outputs by structuring the task

### Technical details
WorkflowAI leverages structured generation, also called [structured output](https://platform.openai.com/docs/guides/structured-outputs), or [controlled generation](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output). Structured generation is currently enabled for [all supported OpenAI models](https://platform.openai.com/docs/guides/structured-outputs), and for all models on [Fireworks](https://docs.fireworks.ai/structured-responses/structured-response-formatting#structured-response-modes). When structured generation is not available, WorkflowAI automatically falls back to [JSON mode](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency), and **always guarantees** the output will follow the output schema.


## How to create a schema?
WorkflowAI supports two ways to create a schema:
- using our web-app, using AI or manually. 
- [writing code directly (for Python)](/docs/sdk/python/get-started.md).

## Edit a schema
Finding the right schema takes a few iterations, so we try to make editing a schema as easy as possible.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/a34d249ba3c4259d436491eeb50ecaaf/watch" %}

When possible, we recommend to edit the schema using the agent via the playground. If you need more control, you can manually edit the schema.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/283622ef29c1587c5a49604a4d880606/watch" %}


## Archiving and restoring a schema
When building a new task, it's very likely you'll need multiple iterations to get the right schema. To clean up unused schemas, you can archive them.

To archive a schema, navigate to the "Schemas" section from the menu, and click on the "Archive" button in the schema's detail view.

To restore a schema, navigate to the "Schemas" section from the menu, and click on the "Restore" button in the schema's detail view.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/1a6551a93fdb49d0c0c2cdedfc9920b1/watch" %}

{% hint style="important" %}
Archived schemas are not deleted, but hidden from the UI. Any deployment or version using an archived schema will continue to work, to avoid breaking changes.
{% endhint %}