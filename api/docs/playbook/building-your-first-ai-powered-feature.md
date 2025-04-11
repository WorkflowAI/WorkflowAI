## Building your first AI-powered feature, in a few minutes.
> for product and engineering teams

First goal is to set something running quickly, a POC (Proof of Concept) to validate that AI is able to do what you want, without aiming for perfect results all the time, but getting a first feel of what is possible, or not.

To create a first version of a new AI-powered feature, you'll only need to be able to describe in a few sentences what the AI-powered feature should do.

{% hint style="info" %}
We recommend starting using the [web-app](https://workflowai.com/), as it's the fastest way to get started.
{% endhint %}

### New AI-powered feature
Tap "+ New" on the web-app, then pick from the list of suggested AI-powered features, or write a few sentences describing what the AI-powered feature should do.

### A first schema
WorkflowAI will automatically generate a first schema based on your description. 

A schema is a definition of the (input, output) of your AI-powered feature. For example, if you want an AI-powered feature to summarize a text, the input is a text, and the output is a summary. If you want the AI-powered feature to summarize a text in a language that is dependent on the context, you'll need to add a language parameter to the input. The input is like all the variables the LLM will have access to. The output is the different fields the LLM will generate.

{% hint style="info" %}
Don't focus on the first schema being perfect, you'll likely iterate on the schema multiple times. WorkflowAI handles very well multiple schemas per AI-powered feature, so you can easily edit the schema later.
{% endhint %}

Once you're happy with your first schema, tap "Save and Try in Playground". 

WorkflowAI will automatically:
- generate the first instructions for the AI-powered feature
- generate a input (using synthetic data generation)

Congratulations, your AI-powered feature is running! Now you can iterate on it from the playground.

<details>
<summary>INSIDE WORKFLOWAI'S OWN AGENTS</summary>
- instructions generation
- synthetic data generation
</details>

[info]
Make sure the first input reflects what production data will look like. You can use "Generate" or "Import"
[/info]

## First iterations
> This step can be done by either product or development team.

The playground has been designed to quickly iterate on your AI-powered feature. We recommend you take the following steps to adjust how your AI-powered feature behaves.

### Clear output fields descriptions
The first step is to make sure the descriptions are clear and complete. Descriptions are helping the LLM to understand what the input and the output are. WorkflowAI will use AI to generate the descriptions, but you can also edit them manually.

### Specific output fields examples
Examples are very powerful way to help the LLM understand what the output should look like.

### Try different models
Get a first feel of what models are performing well, and don't hesitate to try multiple models.

### Temperature

## AI-assisted Prompt Engineering

WorkflowAI includes a AI-assisted prompt engineering feature.

Explain [write feedback] -- scope: can update instructions, but also fields description and example.

At this point, our AI-powered feature should be working! If you can't get the output you want, go to step 