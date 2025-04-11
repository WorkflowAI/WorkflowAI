# Versions

## What is a version?

A version is a specific **configuration** of an agent.

WorkflowAI defines two types of (agent) versions:

| Version Type | Example | Description |
|--------------|---------|-------------|
| **Major** Versions | 1, 2, 3, ... | A major version represents a specific configuration of a agent, including its instructions, temperature, descriptions/examples, and tools. |
| **Minor** Versions | 1.1, 1.2, 1.3, ... | A minor version represents a major version **associated with a specific model** (e.g., OpenAI's GPT-4o-mini). |


![Version 2 is a major version, version 2.1 is version 2 running on Gemini 2.0](/docs/assets/images/versions/versions.png)

## Why are versions useful?

Versions are useful for several reasons:
- They allow you to save a specific configuration of an agent, so you can reproduce it later.
- They allow you to [compare the performance of different versions of an agent](/docs/playbook/evaluating-your-ai-feature.md).
- They allow you to [deploy a specific version of an agent](/docs/features/deployments.md).


## How to:

### Save a version
When using the playground, you can save a version by clicking on the "Save" button.

![Save a version](/docs/assets/images/versions/save-version.png)

Additionnaly, you can save all versions currently running by clicking on the "Save all versions" button.

![Save all versions](/docs/assets/images/versions/save-all-versions.png)

{% hint style="info" %}
You should save a version when you're satisfied with the LLM output and want to preserve the current configuration. A saved version captures your chosen model, prompt, temperature setting, and other parameters, allowing you to reliably reproduce these results later, or use them in a [deployment](/deployments).
{% endhint %}

### List all versions
You can access the list of all versions by clicking on the "Versions" section from the menu.

![List of all versions](/docs/assets/images/versions/versions-section-full.png)

### Clone a version

Cloning a version is useful when you want to create a new version based on an existing version. For example, you have a version running on OpenAI's GPT-4o-mini, and you want to quickly reuse the same instructions, temperature, and tools for a new version running on Gemini 2.0.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/be1801a4342a1352fa5aa9aa7f5da707/watch" %}

