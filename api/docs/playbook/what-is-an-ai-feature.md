# What is an AI Feature?

> The unprecedented capabilities of foundation models have opened the door to agentic applications that were previously unimaginable. These new capabilities make it finally possible to develop autonomous, intelligent agents to act as our assistants, coworkers, and coaches. They can help us create a website, gather data, plan a trip, do market research, manage a customer account, automate data entry, prepare us for interviews, interview our candidates, negotiate a deal, etc. The possibilities seem endless, and the potential economic value of these agents is enormous.
> [Chip Huyen](https://huyenchip.com/2025/01/07/agents.html)

AI Features are mini-programs that use AI algorithms (LLMs) as their brain to accomplish tasks typically provided by users or other AI features. The AI feature understands the task requirements, plans a sequence of actions to achieve the task, executes the actions, and determines whether the task has been successfully completed.

Some examples of what AI features can do:
- **Summarize** a text [todo: add link to public task]
- **Browse** a company URL to extract the list of customers [todo: add link to public task]
- **Search** the web to answer a question [todo: add link to public task]
- **Generate** product descriptions from images [todo: add link to public task]
- **Extract** structured data from a PDF, image [todo: add link to public task]
- **Classify** a customer message into a category [todo: add link to public task]
- **Scrape** a listing website to extract structured data [todo: add link to public task]

<details>
<summary>REAL-LIFE EXAMPLE</summary>

Apple recently introduced a AI agent that can rewrite a text with a different tone.

[image]
</details>

For more inspiration on AI features you can build, go to [workflowai.com](https://workflowai.com) and enter your company URL to get customized recommendations, or browse the suggested AI features to see a wide range of capabilities. 

For more information on how to build AI features, check out our [Python SDK guide](../sdk/python/get-started.md).

## What is *not* an AI Feature?

An AI feature should involve a single input-to-output interaction. Combining multiple sequences of inputs and outputs would instead constitute a [workflow](workflows.md), which is not currently supported. In the event that there is a task that is better suited for a workflow, break the process into multiple agents that each handle one portion of the task only.
- **Valid AI Feature:** "Extract calendar events detected in a thread of emails."
- **Invalid AI Feature (ie. a Workflow):** "Extract calendar events from a thread of emails and then automatically send invitations for the events to guests."