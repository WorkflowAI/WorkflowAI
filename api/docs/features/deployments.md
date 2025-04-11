## Deployments

Deploy specific versions of an agent with ease, allowing for updates to prompts and models **without any code changes**.

### Why use deployments?

- ✅ update to a new model or prompt without asking your engineering team.
- ✅ save cost by updating to a more recent, cheaper model, without changing your code.
- ✅ improve the quality of your tasks outputs by adjusting the prompt, in real-time, based on users' feedback.
- ✅ use different versions of a task in different environments (development, staging, production).

### How to deploy a version?

1. Go to **Deployments** section from the menu.
2. Pick the environment you want to deploy to, either: production, staging, or development.
3. Tap **Deploy Version**
4. Select the version you want to deploy.
5. Tap **Deploy**

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/58dfabcb7b91f2a57d99602876dc98f1/watch" %}

{% hint style="warning" %}
To avoid any breaking changes: deployments are **schema specific**, meaning that you can deploy a (development, staging, production) version for each schema of an agent.
{% endhint %}

### Using your own AI Providers API
#### When to use your own API key?
- if you have custom **zero day** data-retention agreement. Note that WorkflowAI Cloud has signed contratuals agreements with all AI providers that prohibit the use of customer data to train their models.
 - if you have credits from [Microsoft Startups](https://startups.microsoft.com/), [Google AI credits](https://cloud.google.com/startup), or [Amazon Bedrock credits](https://aws.amazon.com/startups/credits).
- if you want to use your own rate limits.

Remember that WorkflowAI Cloud offers a price-match guarantee, meaning that you're not charged more than the price per token of the model you're using. Learn more about the price-match guarantee [here](/docs/cloud/pricing.md).
