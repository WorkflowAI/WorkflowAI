# Testing your AI Feature
{% hint style="success" %}
For product and engineering teams
{% endhint %}

## Determine Feature Feasibility

The first thing to determine after a first schema of the feature has been created is whether the goal of the feature is possible to accomplish with existing LLM limitations. 

After the first run of the new feature on the playground: confirm whether the feature resembles what was originally described and - if not - what is wrong with it? Can the issues be overcome using the techniques described in [Improving your AI Feature](improving-your-ai-feature.md)? Or are the issues indicative that the feature is beyond the limitations of current LLMs? Sometimes this answer isn’t immediately evident and becomes clearer over time. But getting an initial feel is important. 

#### A note about diagnosing issues with your AI Feature

Addressing issues with your AI feature are an inherent part of building a successful feature and can occur at any stage. Problems generally happen more frequently early in the development process and generally decrease over time as you optimize your feature to align more closely with your goal.

## Test with Various Inputs

After creating your schema, the first thing to do is test the feature by running it with varied inputs to ensure reliability across multiple scenarios. Aim for 10-20 diverse inputs depending on feature complexity.

Options for generating test data include:

- **Early Internal/Beta Deployment (recommended):** Deploy an early version internally or to a beta group and gather real-world data using WorkflowAI [observability and feedback features](../features/user-feedback.md).
- **Generated Data:** WorkflowAI can automatically generate suitable test inputs. It’s possible to provide specific instructions to guide the generation process.
- **Imported Input:** Input can be directly imported on the playground to facilitate testing.

## Test with Various Models

WorkflowAI provides access to 70 different LLM models that can be used for running features. Different models will have different strengths - some are known for being highly intelligent, others are very cheap, and still others will excel in performing tasks quickly. Ultimately a prompt only needs to work for one model, as in the end, only one version will be chosen to be deployed at a time.

When selecting the best model for a feature, consider the following capabilities:

- **Intelligence:** Is the model able to perform the task requested and produce the correct output for the feature? More complicated features will require more advanced models.
- **Price:** What is the estimated run volume of the feature and the associated budget? If there is a limited budget for a high volume feature, it might be necessary to pick a cheaper model.
- **Latency:** How fast does the feature need to return an output? If a feature is user-facing, it’s generally best to avoid high latency models as the waiting time can lead to a poor user experience. Background features can generally get away with slower models as the pace is less noticeable. 