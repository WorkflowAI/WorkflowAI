# Improving your AI Feature

Issues can occur at two levels: schema-level and version-level. The issue type determines the options available to make corrections.
Below you will find some examples of common schema-level and version-level problems.

## Schema-Level Issues

#### Problem: My feature is missing an input or output field
When the schema fields don't align with expected inputs or outputs - such as missing fields - update the feature’s schema to resolve. The schema can be updated in the WorkflowAI web-app or via code directly.

Examples of this problem: 
- A feature where a transcript of a discussion is extracting calendar events, but the input is missing the `transcript_time` parameter.
- A feature where a transcript of a discussion is extracting calendar events, but the output is missing the `event_time` parameter.

#### Problem: My feature has an unwanted field, or the name of a field is wrong
When the schema fields don't align with expected inputs or outputs - extra fields, or incorrect field names - update the feature’s schema to resolve. The schema can be updated in the WorkflowAI web-app or via code directly.

#### Problem: A field format is wrong (Schema-Level)
Certain format issues require schema updates; others do not.

- **Schema Update Required:** Issues involving changes in data structure, such as switching a field from a single string to a list of strings, require the schema to be updated
- **No Schema Update Required:** Formatting adjustments (eg. specific format for dates, bullet points vs. paragraphs, or language requirements) can be resolved by updating field descriptions or examples within the playground. Refer to the [Version-Level Issues section](#problem-a-field-format-is-wrong-version-level) for more information on this case.

## Version-Level Issues

Version-level issues have a wide variety of solutions depending on their nature. The first part of this section highlights common version-level problems and their solutions at a high level. The second part of this section provides further information about each solution.

#### Problem: A field format is wrong (Version-Level)
As noted in the schema-level issues section, certain format issues can be solved on the playground directly; others can not.

- **Playground-Resolvable Cases:** Content format issues (dates, bullet points, language style) can be fixed directly in the playground by editing [instructions](#updating-instructions), or editing [examples, and descriptions](#updating-field-examples-and-descriptions). The edits can be completed with the help of the Playground Chat Agent or manually. 
- **Schema Update Required:** Data structure changes require updating the schema directly. Refer to the [Schema-Level Issues](#problem-a-field-format-is-wrong-schema-level) section for more information.

#### Problem: My feature doesn’t seem to understand the output that I want
Example: a task that should produce a summary in bullet points, but the summary is written as a paragraph.

There are several solutions to try:

- [Update the playground instructions](#updating-instructions) to ensure that the expected output behavior is clearly described. 
    - Example of this problem that would be solved by this solution:A feature that should produce a one paragraph summary, but currently the summary is 2 or more paragraphs. Ensuring that the instructions specifically mention the one paragraph maximum will help ensure the LLM is aware of the size limit
- [Updating a field’s examples and descriptions](#updating-field-examples-and-descriptions) can provided even clearer guidance for issues with a specific field,
    - Example of this problem that would be solved by this solution: A feature that should produce a summary in bullet points, but currently the summary is in a paragraph form. Updating the summary examples to include bullet points can help guide the LLM in formatting.
- [Use highly intelligent models](#trying-different-models). For complicated prompts, or prompts where the instructions, examples, and descriptions have all been updated to no avail, experiment with different models, specifically models with higher intelligence. The playground chat agent can recommend high intelligence models, and model intelligence scores can also be viewed when hovering over models in the playground model dropdown. 

If even highly intelligent models are not able to produce the correct output, the prompt may be too complex for current LLM capabilities. See [Determine Feature Feasibility](testing-your-ai-feature.md#determine-feature-feasibility) for more information on feature limitations. 

#### Problem: The output does not contain up-to-date information
LLMs have knowledge cut-offs and may produce outdated information. Integrating tools into instructions helps the LLM real-time data access. A list of available tools is available in the [Adding Hosted Tools to Instructions](#adding-hosted-tools-to-instructions) section.

Example of this problem: 
- asking an LLM the current stock price of AAPL without including any @search tool.

#### Problem: I’m getting a lot of errors when I use tools

Tools help models perform different functionality that they would otherwise be unable to do. For example, accessing real-time data that is more recent than their knowledge cut-offs.
Some models manage tools better than others; experimenting with [different models](#trying-different-models) will help you find the models that work best with the tools you need to use.

#### Problem: I’m getting errors related to a model’s context window
An LLM's context window refers to the maximum number of tokens (words or subwords) that the model can consider simultaneously when generating a response. In simpler terms, it's how much recent information the model can "remember" or use as context during a conversation or task.

Models have varying context window sizes. If there is an error related to a feature exceeding a model’s context window, [switch models](#trying-different-models) to one that has a larger context window. The playground chat agent can provide recommendations for models with large context windows, and you can also view model’s context windows by hovering a model in the playground model dropdown to view its details

### Additional Guidance on Version-Level Solutions:

#### Updating Instructions: 
Instructions provide overall guidance on how the agent should approach tasks, including what tools to use, what tone to adopt, and general behavioral guidelines. They're best for defining the agent's overall approach and methodology. 

Models will respond to the same instructions differently. When improving the instructions, remember that the instructions don’t need to work for every model on the playground. Ultimately, they only need to work for one model, as in the end, only one version will be chosen to be deployed at a time.
Instructions can be updated with playground agent assistance or manually on the playground.

#### Updating Field Examples and Descriptions: 
Examples and descriptions provide specific formatting guidance for individual fields. They show the agent exactly what the output should look like for each field and provide context about what each field should contain.

Examples and Descriptions edits are made on the playground by:
- **In all cases:** Asking the playground agent to make an update on your behalf by describing the change
- **If output is currently displayed:** Hovering over a field name, then hover over the description/examples modal and tap Edit
- **If no output is displayed:** Hovering over a description or example and tap Edit

#### Updating Temperature: 
Temperature affects a model’s balance between precision and creativity: 

- **Lower (near 0):** More deterministic, consistent outputs that strictly follow instructions.
- **Higher (near 1):** More creative, varied outputs with potentially more exploration

The temperature can be adjusted on the playground in the temperature section underneath the instructions.

#### Adding Hosted Tools to Instructions: 
Tools help models perform different functionality that they would otherwise be unable to do. Integrate WorkflowAI-hosted tools to provide real-time data from internet searches and scraping websites. 

Tools can be added by describing the use case to the playground chat agent or enabled manually using the buttons at the bottom of the instructions text field.
Hosted tools that are currently available:
- **@browser-text:** browses websites for information
- **@perplexity-sonar-pro:** browses the web for information using perplexity: a premier search offering with search grounding, supporting advanced queries and follow-ups.
- **@search-google:** browses the web for information using google (not the default browser tool, should only be suggested as an alternative to perplexity, if perplexity is not performing as desired)

#### Trying Different Models:
Each LLM model offers distinct strengths and weaknesses. Experimenting with models directly in the playground or through agent recommendations helps identify the best model for your feature complexity and performance requirements.

Different models can be selected using the model dropdowns on the playground. Model recommendations for a use case can be provided by the playground chat agent.

