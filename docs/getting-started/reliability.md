## Reliability
[![Better Stack Badge](https://uptime.betterstack.com/status-badges/v2/monitor/1cuxx.svg)](https://status.workflowai.com)

Our goal with WorkflowAI Cloud is to provide a 100% uptime on our API endpoint that is used for running an AI agent.

We've designed our architecture to be resilient in a few ways:
- the run endpoints have 2 redundancy mechanisms in place by default:
  - Most of our models are available on [multiple providers](#id-1.-automatic-fallback-to-secondary-ai-providers) meaning that we can automatically switch to a different provider if the initial one is down. 
  - For errors not covered by the provider redundancy, we implement [fallback to different AI models](#id-2.-fallback-to-different-ai-models)
- at the API level, we run our inference API `run.workflowai.com` in a separate container, isolated from the rest of our other API endpoints. This allows us to scale and deploy the inference API independently of the rest of our API.
- at the database level, we use a multi-region database to ensure that your data is always available.
- at the datacenter level, we bring redundancy by running our API in multiple independent regions.

## 1. Automatic fallback to secondary AI providers

WorkflowAI continuously monitors the health and performance of all integrated AI providers. When a provider experiences downtime or degraded performance, our system automatically switches to a healthy alternative provider without any manual intervention.

For example, all OpenAI models are also available through Azure OpenAI Service. If the OpenAI API becomes unavailable, WorkflowAI will automatically failover to Azure OpenAI within one second. This seamless transition ensures your agent runs continue without interruption, and you don't need to make any changes to your code.

This intelligent routing between providers happens behind the scenes, maintaining consistent response times and reliability for your applications even during provider outages.

## 2. Fallback to different AI models

Sometimes there are situations where using the exact same model on a different provider will not enable 100% uptime, for example:
- the model does not have redundancy of providers and the uniquely available provider is having issues. Although we strive to ensure redundancies, some models (like Grok 3 and Deepseek R1 at the time of writing) are rare or specific enough that it is not possible to have multiple providers
- all providers for a given model are down, or the rate limits are exceeded on all providers.
- the completion failed because of limitations of the model, a very common example are content moderation errors or failed generations when using structured outputs.

In any of the above cases, falling back to a different AI model can ensure the completion succeeds.

### Model Fallback configuration

Configuring model fallback is done by setting the `use_fallback` argument in the completion endpoint.

- **Automatic model fallback** `use_fallback="auto"` is the default value and uses a different model based on the type of error that occurred. See details [below](#automatic-model-fallback)
- **Disable model fallback** `use_fallback="never"` disables model fallback entirely. This can be useful if you care more about consistency than success. For example, for text generation, you might like the tone of a single unique model and would rather have a generation fail than switching to a different model.
- **Custom model fallback** `use_fallback=["gemini-2.0-flash-001", "o3-mini-latest-medium"]` allows passing a list of models to try in order when the initial model fails.

{% hint style="info" %}
Configuring the model fallback is only available through code for now.
{% endhint %}

#### Automatic model fallback

The default fallback algorithm (i.e. when `use_fallback` is not provided or when `use_fallback="auto"`) assigns each model a fallback model based on the type of error that occurred:
- for rate limit errors, we use a model of the same category (similar price and speed) that is supported by a different provider
- structured generation errors can occur for models without native structured output. In this case, we use a model at the same price point that supports native structured output. For example, `GPT 4.1 Nano` would be used as a fallback for models like `Llama 4 Scout` and `Gemini 2.0 Flash`.
- for content moderation errors, we use a model that has been historically more permissive. For example,  Llama 4 Maverick on Groq seems to be on the stricter side whereas non preview Gemini models on Vertex are often more permissive.
- for context size errors (the request exceeds the model's context window), we use a model at the same price point and **at least twice** the context window of the original model, if available. As an indication, at the time of writing, GPT 4.1 models support a 1M token context window, and only Gemini 1.5 Pro supports a 2M token context window.

{% hint style="info" %}
The exhaustive fallback definitions are visible in the [codebase](https://github.com/WorkflowAI/WorkflowAI/blob/main/api/core/domain/models/model_datas_mapping.py) 
{% endhint %}
<!-- TODO: add link to doc about finding model ids when available, docs/reference/models.md-->



### Code samples

The `use_fallback` argument is available in all of our run SDKs and endpoints.


#### OpenAI SDK

{% tabs %}

{% tab title="Python" %}

```python
completion = openai.chat.completions.create(
    model="user-extraction/gpt-4o",
    messages=...,
    extra_body={
        use_fallback=["gemini-2.0-flash-001", "o3-mini-latest-medium"] # | "auto" | "never"
    }
)
```
{% endtab %}

{% tab title="TypeScript" %}

```typescript
const completion = await openai.chat.completions.create({
    model: "user-extraction/gpt-4o",
    messages: [...],
    use_fallback: ["gemini-2.0-flash-001", "o3-mini-latest-medium"] // | "auto" | "never"
})
```
{% endtab %}

{% tab title="cURL" %}

```sh
curl -X POST https://run.workflowai.com/v1/chat/completions \
-H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "model": "user-extraction/gpt-4o",
    "messages": [...],
    "use_fallback": ["gemini-2.0-flash-001", "o3-mini-latest-medium"]
}'
# use_fallback="auto" | "never" | ["gemini-2.0-flash-001", "o3-mini-latest-medium"]
```

{% endtab %}

{% endtabs %}

#### WorkflowAI SDK

{% tabs %}

{% tab title="Python" %}

```python
@workflowai.agent(id="user-extraction", version="production", use_fallback=["gemini-2.0-flash-001", "o3-mini-latest-medium"])
def user_extraction(_: UserExtractionInput) -> UserExtractionOutput:
    ...
```

{% endtab %}

{% tab title="TypeScript" %}

```typescript
const extractUser= workflowAI.agent<UserExtractionInput, UserExtractionOutput>({
  id: 'user-extraction',
  schemaId: 1,
  version: 'production',
  useFallback: ['gemini-2.0-flash-001', 'o3-mini-latest-medium'],
});
```

{% endtab %}

{% tab title="cURL" %}

```sh
curl -X POST https://run.workflowai.com/v1/agents/user-extraction/schemas/1/run \
-H "Authorization: Bearer $WORKFLOWAI_API_KEY" \
-H "Content-Type: application/json" \
-d '{
    "version": "production",
    "use_fallback": ["gemini-2.0-flash-001", "o3-mini-latest-medium"],
    "task_input": ...
}'
```

{% endtab %}

{% endtabs %}

## 3. Database redundancy

We use MongoDB Atlas for our primary database infrastructure, which ensures high availability through a distributed architecture with a [99.995% SLA](https://www.mongodb.com/cloud/atlas/reliability). Our database deployment includes 7 replicas across 3 Azure regions:
- 3 replicas in East US2
- 2 replicas in Iowa
- 2 replicas in California

These replicas automatically synchronize data between them, ensuring that if one database instance or even an entire region fails, the others can immediately take over without data loss. MongoDB Atlas also offers automatic failover capabilities, where if the primary node becomes unavailable, a secondary replica is automatically promoted to primary, typically within seconds. This multi-region architecture ensures continuous database operations even during regional outages, maintenance windows, or unexpected infrastructure issues.

{% hint style="info" %}
For storing run history and analytics data, we use Clickhouse, which excels at handling large volumes of data efficiently. It's important to note that while Clickhouse powers our analytics and observability features, it's not required for the core agent execution functionality. The process that stores run history is completely isolated from the critical run path, ensuring that your agents will continue to run normally even if the Clickhouse database experiences temporary unavailability.
{% endhint %}

## 4. Datacenter redundancy

We use [Azure Front Door](https://azure.microsoft.com/en-us/products/frontdoor) as our global load balancer to ensure high availability across multiple regions. Our infrastructure is deployed in both East US and Central US datacenters, providing geographic redundancy.

Azure Front Door continuously monitors the health of our backend services in each region. If one of our datacenters experiences an outage or performance degradation, Azure Front Door automatically redirects traffic to the healthy region within approximately 30 seconds. This intelligent routing happens without any manual intervention, ensuring minimal disruption to your API calls.

This multi-region architecture allows us to maintain high availability even during regional cloud provider outages, helping us achieve our goal of 100% uptime for the WorkflowAI API.

{% hint style="info" %}
If you have any questions about our architecture, please [contact us](mailto:team@workflowai.support).
{% endhint %}
