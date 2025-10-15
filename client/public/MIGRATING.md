# Migrating out of WorkflowAI

The WorkflowAI run endpoint and SDK will stop working on January 31st, 2026. Here are the instructions on how to migrate out of WorkflowAI.

WorkflowAI's main feature was to provide a unique and consistent API for structured data across models and providers.
Now that most providers support structured outputs and hosted tools and that models are smart enough to provide consistent
results without the need for fine-tuned prompt engineering, the WorkflowAI wrapper seems redundant. The OpenAI chat
completion has now become a standard and can also be used directly for several providers.

## Converting to the message paradigm

WorkflowAI exposes a simple "structured data in / structured data out" endpoint. Behind the scene, the payload is
converted to a list of messages.

### System message

The version instructions were sent in the system message wrapped in the `<instructions>` tag. The
`<instructions>` tag is likely not needed and can be omitted.

For models that do not support structured outputs, the system message was also used to provide
the requested output schema. The appended prompt was very simple:

````
Return a single JSON object enforcing the following schema:
```json
{{output_schema}}
```
````

> The exact templates that were used are available in [templates.py](https://github.com/WorkflowAI/WorkflowAI/blob/main/api/core/runners/workflowai/templates.py). They can likely be simplified now. For example, WorkflowAI also provided the input schema in the system message but we would now advise against it.

> On Anthropic, the system message is sent in the `system` field of the request. See their [API documentation](https://docs.claude.com/en/api/messages#body-system)

### User message

The user message essentially contained the input data, serialized as a JSON object. When files were provided, they were extracted from the JSON and sent in the appropriate fields. The exact processing that WorkflowAI did is detailed in [workflowai_runner.py](https://github.com/WorkflowAI/WorkflowAI/blob/main/api/core/runners/workflowai/workflowai_runner.py).

### Hosted tools

WorkflowAI hosted a few tools like web search and browser, which were activated by mentioning their handle (e.g., `@google-search` or `@browser-text`) in the instructions. Several providers now support native tools, see for example the [OpenAI documentation](https://platform.openai.com/docs/guides/tools-web-search?api-mode=chat).

The exact tools that WorkflowAI used were:

- `@search-google` -> [Serper](https://serper.dev), see [run_google_search.py](https://github.com/WorkflowAI/WorkflowAI/blob/main/api/core/tools/search/run_google_search.py)
- `@perplexity-...` -> [Perplexity](https://perplexity.ai), see [run_perplexity_search.py](https://github.com/WorkflowAI/WorkflowAI/blob/main/api/core/tools/search/run_perplexity_search.py)
- `@browser-text` -> a combination of [Firecrawl](https://firecrawl.dev) and [ScrapingBee](https://scrapingbee.com), see [browser_text_tool.py](https://github.com/WorkflowAI/WorkflowAI/blob/main/api/core/tools/browser_text/browser_text_tool.py). We found that ScrapingBee would generate less failed requests.

### Using different providers

WorkflowAI supported multiple providers. The list of the models that each providers supported and the pricing data is available in the [model_provider_data_mapping.py file](https://github.com/WorkflowAI/WorkflowAI/blob/main/api/core/domain/models/model_provider_data_mapping.py).

There are now several available options to avoid having to write code for each provider:

- in Javascript/TS, [Vercel AI Gateway](https://vercel.com/docs/ai-gateway)
- in Python, [Instructor](https://python.useinstructor.com/)
- [OpenRouter](https://openrouter.ai/) provides a unified API and similar functionality as WorkflowAI and is OpenAI compatible

### OpenAI compatible code

Below is pseudo code that should help you migrate the current version to an OpenAI client. The following is designed so that it can be easily integrated in existing code using any coding agent, and minimize the amount of code that needs to be rewritten.

```js

const openaiClient = new OpenAI({
    // depends on the provider
    baseURL: __BASE_URL__,
    apiKey: __API_KEY__,
});

/*
Generate the response format corresponding to the output schema. Response format can either be the JSON schema itself or equivalent Zod or Pydantic objects depending on the language.

__OUTPUT_SCHEMA__
*/

const __OUTPUT_TYPE_NAME__ = z.object(...)
// Or: class __OUTPUT_TYPE_NAME__(BaseModel): ...


/*
Generate a type corresponding to the input JSON schema

__INPUT_SCHEMA__
*/
type __INPUT_TYPE_NAME__ = ...

export function __AGENT_FUNCTION__(input: __INPUT_TYPE_NAME__) {
    // Use the "parse" method to let OpenAI do the object parsing.
    // For languages that do not support the `parse` method, use `create` and parse the result manually.
    const response = await openai.chat.completions.parse({
        model: __MODEL_ID__,
        messages: [
            {
                role: "system",
                content: __INSTRUCTIONS__
                // Include the JSON schema in the instructions if the model does not support native
                // structured outputs.
            },
            {
                role: "user",
                content: JSON.stringify(input)
            }
        ],
        response_format: __OUTPUT_TYPE_NAME__, // Or: zodResponseFormat(__OUTPUT_TYPE_NAME__)
    });

    return response.choices[0].message.parsed;
    // Or:
    // return JSON.parse(response.choices[0].message.content) for languages that do not support the `parse` method.
}

// __AGENT_FUNCTION__ can now be used like the function that was generated by the WorkflowAI SDK.
const output = await __AGENT_FUNCTION__(input);
```
