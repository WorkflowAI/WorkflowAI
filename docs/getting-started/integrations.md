# Integrations

info
let us know what integrations you'd like to see. ...

WorkflowAI integrates with the programming languages and AI SDKs you already use.

Our list of integrations:
| Language    | Integrations                                                                 |
|-------------|------------------------------------------------------------------------------|
| curl (HTTP) | [Supported](getting-started/integrations/curl.md)                                                                    |
| Python      | [OpenAI SDK](getting-started/integrations/openai-python.md), [Instructor](getting-started/integrations/instructor-python.md), [PydanticAI](getting-started/integrations/pydanticai.md)       |
| TypeScript  | [OpenAI SDK](getting-started/integrations/openai-js.md), [Vercel AI SDK](getting-started/integrations/vercelai.md)        |

## Under the hood

To support over X integrations, WorkflowAI exposes an API endpoint compatible with the OpenAI `/chat/completions` endpoint.

This means that you can use any OpenAI-compatible SDK to interact with WorkflowAI, including tool, library or framework that we haven't yet officially listed in our list of integrations.

{% hint style="info" %}
**Note:** The OpenAI **Responses API** is not yet supported through the WorkflowAI platform. Use the `chat/completions` endpoint instead.
{% endhint %}

Explore:
- supported parameters
- supported models
- ...

{% hint style="info" %}
**Latency Note:** Using the proxy adds a small amount of latency, typically around 0.1 seconds, to each request compared to calling the underlying model provider directly. This minimal overhead enables the enhanced features like observability, model failover, and consistent API access.
{% endhint %}