## Playground

The playground is WorkflowAI's tool to allow quick and easy iterating on prompts and models, so you can create the best version of your AI feature possible.

![Playground](../assets/images/playground-fullscreen.png)

### What are the different parts of the playground?

The playground is composed of 3 sections:
- **Input**: where the content given to the AI feature is defined.
- **Parameters**: where the details of how the AI feature should behave are described.
- **Outputs**: where the AI feature's results are displayed.

#### Input
You can manually enter the input content, import existing data, or - for text inputs only -  you can use WorkflowAI to generate synthetic data.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/a59fd6b80ce55d9bd6b83a4a9789f998/watch" %}

#### Parameters
Parameters dictate how the AI feature should behave.  

##### Prompt Instructions
The prompt are the instructions given to the LLM to describe what is expected from the agent and how it should process the input.

When you create a new agent, WorkflowAI will generate a default prompt for you. You can manually edit the prompt to refine the behavior of the AI feature, but our recommended approach is to use the chat agent on the playground to help with editing. Simply describe the problem with the current behavior or what you want to see instead, and the chat agent will help iterate on the prompt to get the results you're looking for.

##### Temperature
Temperature is a parameter that controls the randomness of the LLM's outputs. WorkflowAI provides three preset temperature settings:

- **Precise** (Default): The recommended and default setting for all tasks
  - Best for tasks requiring accuracy and consistency
  - Ideal for factual responses, code generation, or structured data extraction
  - Produces reliable, repeatable results

- **Balanced**: Moderate setting that balances creativity and coherence
  - Good for general-purpose tasks
  - Works well for most conversational and analytical tasks
  - Provides reasonable variation while maintaining relevance

- **Creative**: Maximum diversity and exploration
  - Best for tasks requiring unique or innovative outputs
  - Ideal for brainstorming, creative writing, or generating alternatives
  - Produces more varied but potentially less focused results
- **Custom**: User-defined temperature setting
  - Allows precise control over the temperature value
  - For advanced users who understand the impact of temperature

"Precise" is automatically selected as the default temperature setting for all new features to ensure consistent and reliable outputs. You can adjust this in the Parameters section of the Playground if your use case requires more variation.

![Prompt and Temperature](../assets/images/playground/parameters.png)

##### Descriptions and Examples

Descriptions and Examples are optional fields available for string-based fields that can be used to provide additional, field-specific information to the LLM. If you find that the prompt instructions alone are not guiding the LLM to handle a specific field, you can add or modify the description or examples to help the LLM understand the field better.

- **Description**: A description of the field can including what it is and/or what it is used for.
- **Examples**: You can add one or multiple examples of a field to help the LLM understand what the field formatting should look like.

Examples and Descriptions edits are made on the playground by:
- **In all cases:** Asking the playground agent to make an update on your behalf by describing the change
- **If output is currently displayed:** Hovering over a field name, then hover over the description/examples modal and tap Edit
- **If no output is displayed:** Hovering over a description or example and tap Edit

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/b631d5bd71c86c9c2ae7e4f52f97de1f/watch" %}

#### Outputs
The outputs section displays the LLM outputs.

For each output, WorkflowAI also displays:
- 💰 Cost: The total price in USD for generating this output
- ⚡ Latency: How long it took to get a response from the model, in seconds
- 📊 Context window usage: How much of the model's maximum token limit was used, shown as a percentage

> WorkflowAI Cloud offers a price-match guarantee, meaning that you're not charged more than the price per token of the model you're using. Learn more about the price-match guarantee [here](https://workflowai.com/pricing).

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/045750fa2005dc315713368a503ebd29/watch" %}

#### Diff mode
You can enable diff mode to highlight the differences between LLM outputs, making it easy to spot differences in how models handle your task. Diff mode can be especially helpful for text-heavy outputs, like texts summarizations or composition.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/a4407bafc47b930a877f00ffe1f7644a/watch" %}