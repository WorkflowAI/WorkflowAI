## Deployments

### What are deployments?
Deploy specific versions of an agent with ease, allowing for updates to prompts and models **without any code changes**.

### Why are deployments useful?

- ✅ update to a new model or prompt without asking your engineering team.
- ✅ save cost by updating to a more recent, cheaper model, without changing your code.
- ✅ improve the quality of your tasks outputs by adjusting the prompt, in real-time, based on users' feedback.
- ✅ use different versions of a task in different environments (development, staging, production).

### How to deploy a version?

1. Go to [workflowai.com](https://workflowai.com) and login.
2. Go to **Deployments** section from the menu.
3. Pick the environment you want to deploy to, either: production, staging, or development.
4. Tap **Deploy Version**
5. Select the version you want to deploy.
6. Tap **Deploy**

After deploying a version: you will be able to reference the version you want to use by its environment in your code. Anytime you want to update the version, you can do so by going to the **Deployments** section and deploying a new version to the same environment, no code changes are required.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/58dfabcb7b91f2a57d99602876dc98f1/watch" %}

{% hint style="warning" %}
To avoid any breaking changes: deployments are **schema specific**, not AI feature specific. This means that if you want to deploy a new version of your AI feature that is on a different schema, you will need to update the schema number in your code.

This also means that you can deploy a (development, staging, production) version for each schema of an agent without the version deployed to production being affected.
{% endhint %}