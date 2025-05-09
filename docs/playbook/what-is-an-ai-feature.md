# What is an AI Feature?

AI Features are mini-programs that use AI algorithms (LLMs) as their brain to accomplish tasks typically provided by users or other AI features. The AI feature understands the task requirements, plans a sequence of actions to achieve the task, executes the actions, and determines whether the task has been successfully completed.

Some examples of what AI features can do:
- **Summarize** long pieces of text
- **Browse** a company URL and extract the list of their customers
- **Search** the web to find the answer to a question 
- **Generate** a product description from an image 
- **Extract** structured data from a PDF, image, and other file types
- **Classify** the sentiment of a customer message
- **Scrape** a website and extract structured data

For more inspiration on AI features you can build, sign up and log in at [WorkflowAI.com](https://workflowai.com) and select the **+ New** button to see a wide variety of example features. 

## What is *not* an AI Feature?

An AI feature should involve a single input-to-output interaction. Combining multiple sequences of inputs and outputs would instead constitute a workflow, which is not currently supported. In the event that there is a task that is better suited for a workflow, break the process into multiple agents that each handle one portion of the task only.
- **Valid AI Feature:** "Extract calendar events detected in a thread of emails."
- **Invalid AI Feature (ie. a Workflow):** "Extract calendar events from a thread of emails and then automatically send invitations for the events to guests."