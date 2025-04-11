# User Feedback

WorkflowAI allows you to collect feedback from users about your AI features.

{% hint style="info" %}
Collecting end user feedback is essential for understanding how your AI features perform in real-world scenarios. The main goal is to gather insights about user satisfaction and feature effectiveness when users interact with your AI agents in production environments. This data helps you identify strengths and weaknesses, prioritize improvements, and measure the overall health of your AI-powered features over time.
{% endhint %}

## Feedback loop
1. Add a feedback button to your product: using our web SDK, or by using our API.
2. Users click the button and give feedback.
3. Your team can view the feedback in the WorkflowAI dashboard.
4. Improve instructions based on the feedback.

## How it works

### Feedback Token Lifecycle

The feedback system operates through a secure `feedback_token` that links user feedback to specific AI interactions:

1. **Token Generation**: When you call the `/run` endpoint to execute an AI agent, WorkflowAI automatically generates a unique `feedback_token` for that specific interaction.

2. **Token Security**: The `feedback_token` is a cryptographically signed token that:
   - Is valid only for the specific run that generated it
   - Cannot be used to access any sensitive data
   - Requires no additional authentication to submit feedback

3. **Token Propagation**: Your application needs to pass this token from your backend to your frontend client application where feedback will be collected.

4. **Feedback Submission**: When a user provides feedback, your application sends the `feedback_token` along with the feedback data (positive/negative rating and optional comment) to WorkflowAI.

5. **Storage and Analysis**: WorkflowAI associates the feedback with the original run, making it available in your dashboard for analysis.

{% hint style="info" %}
The `feedback_token` is designed to be safely passed to client-side applications. It contains no sensitive information and can only be used for submitting feedback for the specific run that generated it. The token cannot be used to access any user data, modify your agents, or perform any administrative actions. This security-by-design approach allows you to freely incorporate feedback collection in your frontend without compromising your application's security.
{% endhint %}

### User ID Tracking

- The optional `user_id` parameter allows tracking feedback on a per-user basis
- Each unique combination of (`feedback_token`, `user_id`) can have only one feedback entry
- Submitting new feedback with the same (`feedback_token`, `user_id`) pair will overwrite previous feedback
- This prevents duplicate feedback while allowing users to change their minds

### Data Flow Diagram

```
Backend                              Frontend                             WorkflowAI
┌────────────┐                      ┌────────────┐                      ┌────────────┐
│            │  1. Call /run API    │            │                      │            │
│            │───────────────────────────────────────────────────────────>           │
│            │                      │            │                      │            │
│            │  2. Receive token    │            │                      │            │
│ Your       │<───────────────────────────────────────────────────────────           │
│ Server     │                      │ Your       │                      │ WorkflowAI │
│            │  3. Pass token       │ Client App │                      │ API        │
│            │───────────────────────>           │                      │            │
│            │                      │            │  4. Submit feedback  │            │
│            │                      │            │───────────────────────>           │
│            │                      │            │                      │            │
└────────────┘                      └────────────┘                      └────────────┘
```

## Access `feedback_token`

`feedback_token` needs to be accessed from the client application that will be used to post feedback.

### Python SDK

```python
import workflowai

# Get feedback token from run
run = await my_agent.run(MyAgentInput())
print(run.feedback_token)

# Get feedback token when streaming
async for chunk in my_agent.stream(MyAgentInput()):
    # Process chunks
    pass
print(chunk.feedback_token)
```

### Typescript SDK

```typescript
import { WorkflowAI } from "@workflowai/workflowai";

const workflowAI = WorkflowAI();

// Get feedback token from run
const { output, feedbackToken } = await myAgentFunction(input);
console.log(feedbackToken);

// Get feedback token when streaming
let lastChunk: RunStreamEvent<OutputType> | undefined;
for await (const chunk of stream) {
    lastChunk = chunk;
}
console.log(lastChunk?.feedbackToken);
```

### API

The feedback token is returned by the run endpoint. See the [endpoint documentation](https://run.workflowai.com/docs#/Run/run_task_v1__tenant__agents__task_id__schemas__task_schema_id__run_post).

```
POST /v1/_/agents/my-agent/schemas/1/run
Host: https://run.workflowai.com
Authorization: Bearer {Add your API key here}
Content-Type: application/json

# JSON Body
{
   "task_input": ...
}

# Response
{
   "task_output": ...,
   "feedback_token": ...
}
```

## Post feedback

### Web SDK

The web SDK is the simplest way to add a feedback button to your web app.

#### React

```bash
npm install @workflowai/react
```

```typescript
import { FeedbackButtons } from '@workflowai/react'

...
   <FeedbackButtons feedbackToken={...} userID={...} className='...'/>
...
```

### SDKs/REST API

Use our API if:
- you want full customization over the feedback button and send the feedback via your own backend.
- you want to post feedback from a non-browser environment (e.g. mobile apps).

#### Python

```python
import workflowai

await workflowai.send_feedback(feedback_token="...", outcome="positive", comment=..., user_id=...)
```

#### Typescript

```typescript
import { WorkflowAI } from "@workflowai/workflowai";

const workflowAI = WorkflowAI()

await workflowAI.sendFeeback({feedback_token: "", outcome: "positive", comment: "...", userID: ""})
```

#### REST API

Posting feedback is a single non authenticated API call with a `feedback_token` and `outcome` in the body.
See the [full documentation](https://api.workflowai.com/docs#/Feedback/create_run_feedback_v1_feedback_post).

```
POST /v1/feedback
Host: https://api.workflowai.com
Content-Type: application/json

{
  "feedback_token": "...", # the token as returned by the run endpoint
  "outcome": "positive", # "positive" | "negative"
  "comment": "...", # optional, the comment from the user
  "user_id": "..." # optional, if provided, feedback will be associated with a specific user. Posting feedback for the same `feedback_token` and `user_id` will overwrite the existing feedback.
}
```

## View user feedback

Go to the "User Feedbacks" section from the menu, and you'll see a list of feedback.

![User Feedback Screen](</docs/assets/images/user-feedback.png>)

{% hint style="info" %}
If you need any help, email us at team@workflowai.support or open a discussion on [GitHub](https://github.com/workflowai/workflowai/discussions).
{% endhint %}
