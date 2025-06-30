# Conversations

## Reply to (conversations)

🚧 This feature is currently not implemented.

WorkflowAI enhances the standard stateless OpenAI `chat/completions` endpoint by allowing you to create stateful conversations. Instead of manually managing and sending the entire message history with each turn, you can reference a previous run ID. WorkflowAI will then automatically retrieve the message history from that run and prepend it to the messages in your current request.

![Placeholder Reply to](../assets/proxy/chatbot.png)

**Mechanism: Using `reply_to_run_id`**

To continue a conversation, include the `id` of the immediately preceding chat completion run within the `extra_body` parameter of your new API request, using the key `reply_to_run_id`.

**Example (Conceptual Python):**

```python
import openai
import os

# Configure the OpenAI client for WorkflowAI
# ... (client setup as before)

# --- First turn ---
first_response = client.chat.completions.create(
  model="chatbot-agent/gpt-4o-mini",
  messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello, who are you?"}
  ]
)
first_run_id = first_response.id
print(f"First message: {first_response.choices[0].message.content}")
print(f"First run ID: {first_run_id}")

# --- Second turn (Replying to the first run) ---
if first_run_id:
    second_response = client.chat.completions.create(
      model="chatbot-agent/gpt-4o-mini", # Can be the same or different model
      # Only provide the NEW message for this turn
      messages=[
        {"role": "user", "content": "What can you do?"} 
      ],
      extra_body={
          # Reference the previous run ID
          "reply_to_run_id": first_run_id 
          # Optionally include trace_id or input variables as well
          # "trace_id": "my-conversation-trace-abc" 
      }
    )
    second_run_id = second_response.id
    print(f"Second message: {second_response.choices[0].message.content}")
    print(f"Second run ID: {second_run_id}")

    # --- Third turn (Replying to the second run) ---
    # third_response = client.chat.completions.create(..., messages=[{"role": "user", "content": "..."}], extra_body={"reply_to_run_id": second_run_id})

```

**How it Works:**

When WorkflowAI receives a request containing `reply_to_run_id`, it performs these steps before calling the underlying LLM:

1.  Looks up the run associated with the provided `reply_to_run_id`.
2.  Retrieves the complete `messages` array (including system, user, and assistant turns) from that historical run.
3.  Prepends these historical messages to the `messages` array sent in the current request.
4.  Sends the combined message list to the target language model.

**Benefits:**

*   **Simplified State Management:** Offloads the burden of storing and transmitting potentially long conversation histories from your client application.
*   **Reduced Payload Size:** Your client only needs to send the latest user message(s), significantly reducing the size of the API request payload for long conversations.
*   **Seamless Agent/Chatbot Development:** Makes building multi-turn conversational agents much easier, as the proxy handles the context continuity.

This feature effectively turns the stateless chat completion endpoint into a stateful one, managed by WorkflowAI based on the run history.

### Deployments + reply_to

You can combine the Deployments feature with the stateful conversation feature (`reply_to_run_id`) to easily manage conversational context while using server-managed model configurations.

**Mechanism:**

Make an API call specifying:

1.  The target deployment in the `model` parameter: `model="<agent-name>/#<schema_id>/<deployment-id>"`
2.  The previous run ID in the `extra_body`: `extra_body={"reply_to_run_id": "chatcmpl-xxxx"}`
3.  Typically, only the *new* user message(s) in the `messages` array.

**How it Works:**

When both are provided, WorkflowAI performs the following:

1.  Retrieves the full message history from the run specified by `reply_to_run_id`.
2.  Identifies the **model** associated with the `<agent-name>/#<schema_id>/<deployment-id>` from your Deployment configurations.
3.  Prepends the retrieved history to the new message(s) provided in the current request's `messages` array.
4.  Sends the combined message list to the **model specified by the Deployment**.

**Important Interaction Note:** In this specific scenario (using both `reply_to_run_id` and a Deployment ID), the prompt template defined within the Deployment configuration is **not applied**. The message history fetched via `reply_to_run_id` provides the necessary context, and the Deployment ID primarily serves to select the correct model for the next turn in the conversation. Any `input` variables in `extra_body` will apply to templates within the *new* message(s) provided in the current call.

**Benefit:** This allows you to maintain conversation state effortlessly using `reply_to_run_id` while ensuring that the appropriate, environment-specific model (managed via Deployments) is used for generating the next response.