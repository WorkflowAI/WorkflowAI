## Vercel AI

## Using with Vercel AI SDK

When integrating the WorkflowAI proxy with the [Vercel AI SDK](https://sdk.vercel.ai/), passing custom parameters like `input` variables for templating or a `trace_id` (which WorkflowAI expects within an `extraBody` object) requires specific handling depending on the provider setup.

*   **Standard `openai` Provider:** If using the default Vercel AI SDK setup with the `openai` library pointing to the WorkflowAI proxy URL, the SDK's frontend hooks (`useChat`, `useCompletion`) do not directly expose an `extraBody` parameter. You would typically pass your custom data (e.g., template variables, trace ID) using the `body` option in the hook, send it to your backend API route, and have the backend code construct the `extraBody` object before calling the `openai` client's `create` or `parse` method.

*   **Custom Providers (e.g., OpenRouter):** Dedicated AI SDK providers, such as [`@openrouter/ai-sdk-provider`](https://github.com/OpenRouterTeam/ai-sdk-provider), often provide more direct ways to pass provider-specific parameters. As shown in the OpenRouter provider documentation, they allow passing custom data via `providerOptions` in the SDK function call (e.g., `streamText`, `generateText`), or via `extraBody` options during provider or model configuration.

*   **WorkflowAI Approach:** To achieve the convenience of passing WorkflowAI's `extraBody` content directly from Vercel AI SDK functions, you would ideally use a dedicated WorkflowAI provider for the AI SDK (if one exists) or potentially adapt a compatible provider (like OpenRouter's, if the API structure aligns sufficiently). Such a provider would allow passing `input` or `trace_id` using mechanisms like `providerOptions` or `extraBody` settings, similar to the examples in the OpenRouter provider documentation. Without a dedicated provider, the backend API route modification remains the standard approach.