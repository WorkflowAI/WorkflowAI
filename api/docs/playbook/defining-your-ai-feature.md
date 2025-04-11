# Defining your AI Feature
{% hint style="success" %}
For product and engineering teams
{% endhint %}

## Articulating the Goal of your AI Feature 

When thinking about building your own AI feature, it’s important to consider three key aspects:
1. **Goal:** Clearly describe how input data transforms into output data, ex. extracting calendar events detected in a list of provided emails.
2. **Input:** The type of data the feature will start with, ex. a list of emails.
3. **Output:** The type of data the feature will produce, ex. a list of calendar events.


## Creating your Schema

{% hint style="info" %}
We recommend building your first features directly in the [web-app](https://workflowai.com/) as opposed to the [Python SDK](../sdk/python/get-started.md), as the web app is the fastest way to get started.
{% endhint %}

Once you’ve established a clear goal for your AI feature, tap **+ New** on the web-app and write a few sentences describing what the agent should do. Based on your description, the AI feature builder will identify specific fields required for the input and output. Collectively, these fields create your schema. 

Some schemas are straightforward. For example: summarizing an article, typically involves one input field (the article) and one output field (the summary). Other features may need multiple fields. For instance, an input composed of a thread of emails might have separate fields for email content, senders, recipients, and timestamps.

Initially, include all obvious fields, but don't worry about perfection. Schemas can be adjusted later as necessary. For guidance on addressing schema issues, refer to the section all about [improving your AI Feature](improving-your-ai-feature.md).

Once you're happy with your first schema, tap **Save and Try in Playground**. From there, WorkflowAI will automatically generate a first set of instructions for the feature and a first input to use for testing.

Congratulations, your AI agent is running! You can move on to testing and improving it on the playground.
