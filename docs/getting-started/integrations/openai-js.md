# OpenAI (JavaScript/TypeScript)

- clarify that the WorkflowAI client is not yet compatible with the the `responses` API from OpenAI.
- what is the minimum SDK version required for `.beta.....parse` 

> 4.55.0 is the minimum version required for `.beta.....parse` 

- show exactly hwo to use in typescript the type for the parse method

### Example 2: Chatbot Core Logic

This snippet demonstrates the core logic for a chatbot: maintaining conversation history and getting the next response.

```typescript
import OpenAI from 'openai';
import type { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
// Import zodResponseFormat helper
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from 'zod';

// --- 1. Configuration ---
// Initialize the OpenAI client configured for WorkflowAI.
const client = new OpenAI({
  apiKey: process.env.WORKFLOWAI_API_KEY || 'YOUR_WORKFLOWAI_API_KEY',
  baseURL: 'https://run.workflowai.com/v1',
});

// --- 2. Define Structured Output Schema for Chatbot ---
// Define a simple schema for the chatbot's response.
const ChatbotResponseSchema = z.object({
    assistant_message: z.string().describe("The chatbot's response to the user."),
});

// --- 3. Conversation State ---
// Store the conversation history. Initialize with a system message.
let conversationHistory: ChatCompletionMessageParam[] = [
  {
    role: 'system',
    content: 'You are a helpful assistant. Keep your responses concise and provide them in the requested JSON format.', // Adjusted system prompt slightly
  },
];

// --- 4. Chat Function Definition (Using Structured Output) ---
/**
 * Sends the current conversation history plus the new user message to the model,
 * requests a structured response, gets the assistant's message, and updates the history.
 *
 * @param userMessage The message input by the user.
 * @returns The assistant's response message string.
 */
async function getChatbotResponseAndUpdateHistory(userMessage: string): Promise<string> {
  // Add the user's message to the history for the API call
  const currentMessages = [
    ...conversationHistory,
    { role: 'user' as const, content: userMessage }
  ];

  try {
    console.log('\\nSending messages (expecting structured response):', JSON.stringify(currentMessages, null, 2));

    // Use .parse() to request and validate structured output
    const completion = await client.beta.chat.completions.parse({
      // Model selection: Use agent prefix + chat model ID.
      model: 'chatbot/gpt-4o-mini',
      messages: currentMessages,
      temperature: 0.7,
      // Define the expected structured response format using Zod schema
      response_format: zodResponseFormat(ChatbotResponseSchema, "chatbot_response"),
    });

    // Extract the message string from the parsed structured object
    const assistantResponse = completion.choices[0]?.message?.parsed?.assistant_message;

    if (assistantResponse) {
      // Update the main history state ONLY after a successful response
      conversationHistory = [
          ...currentMessages,
          // Store the plain string message in the history
          { role: 'assistant' as const, content: assistantResponse }
      ];
      return assistantResponse;
    } else {
      // Handle cases where parsing might succeed but the expected field is missing
      console.error("Parsed object missing 'assistant_message':", completion.choices[0]?.message?.parsed);
      return 'Sorry, I received an unexpected response format.';
    }
  } catch (error) {
    console.error('Error communicating with or parsing response from WorkflowAI:', error);
    // Do not update history on error
    return 'An error occurred. Please try again.';
  }
}

/*
// --- Example Usage (Conceptual) ---
// ... (Usage remains the same as before, calling the async function)
*/
```

This example demonstrates the core loop of a chatbot: taking user input, adding it to the history, sending the history to the API, getting a response, adding the response to the history, and repeating.

----

# WorkflowAI Proxy with TypeScript

WorkflowAI provides an OpenAI-compatible API endpoint, allowing you to seamlessly use WorkflowAI with your existing TypeScript applications built using the official OpenAI SDK or compatible libraries. By simply updating the base URL and API key, your code will leverage WorkflowAI's features.

This approach offers several advantages:

*   **Minimal Code Change:** Switch to WorkflowAI by updating the `baseURL` and `apiKey`.
*   **Leverage Existing SDKs:** Continue using the familiar `openai` Node.js/TypeScript SDK.
*   **Rapid Integration:** Quickly start using WorkflowAI's features.
*   **Multi-Provider Model Access:** Access 80+ models via a single API.
*   **Reliable Structured Output:** Get guaranteed structured data (e.g., using Zod) from any model.
*   **Automatic Cost Calculation:** Get estimated costs per request in the response.
*   **Enhanced Reliability:** Benefit from automatic model provider fallbacks.
*   **Observability Built-in:** Monitor usage, performance, and costs.

## Setup

To use the WorkflowAI proxy with the `openai` TypeScript library, configure the client with your WorkflowAI API key and the WorkflowAI base URL.

```typescript
import OpenAI from 'openai';

// Initialize the OpenAI client configured for WorkflowAI.
const client = new OpenAI({
  apiKey: process.env.WORKFLOWAI_API_KEY || 'YOUR_WORKFLOWAI_API_KEY', // Use your WorkflowAI API Key
  baseURL: 'https://run.workflowai.com/v1', // Point to the WorkflowAI endpoint
});

// You can now use the 'client' object as you normally would with the OpenAI SDK
// Example: Making a simple chat completion request
async function simpleChat() {
  try {
    const response = await client.chat.completions.create({
      // Use an agent prefix + model ID (see "Organizing Runs" below)
      model: "simple-chatbot/gpt-4o-mini",
      messages: [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "Hello!" },
      ],
    });
    console.log(response.choices[0].message.content);
  } catch (error) {
    console.error("Error making chat completion:", error);
  }
}

// simpleChat(); // Uncomment to run
```

**Key Changes:**

1.  **`apiKey`**: Use your `WORKFLOWAI_API_KEY`.
2.  **`baseURL`**: Set the `baseURL` to `https://run.workflowai.com/v1`.

## Organizing Runs with Agent Prefixes

To better organize runs in the WorkflowAI dashboard, prefix the `model` parameter with an "agent" name followed by a slash (`/`). This associates the run with a specific logical agent.

```typescript
const response = await client.chat.completions.create({
  // Model prefixed with agent name 'my-chatbot'
  model: "my-chatbot/gpt-4o",
  messages: [{ role: "user", content: "Tell me about WorkflowAI." }],
});
```

In the WorkflowAI UI, this run will be grouped under the agent `my-chatbot`. If no prefix is provided, it defaults to the `default` agent.

## Switching Between Models

WorkflowAI allows you to use models from multiple providers (OpenAI, Anthropic, Google, etc.) through the same API. Switching is as simple as changing the model identifier string.

```typescript
async function switchModels() {
  const messages = [{ role: "user", content: "Explain the concept of LLM RAG." }];

  // Using OpenAI's GPT-4o via 'my-explainer' agent
  const gptResponse = await client.chat.completions.create({
    model: "my-explainer/gpt-4o",
    messages: messages,
  });
  console.log("GPT-4o says:", gptResponse.choices[0].message.content?.substring(0, 50) + "...");

  // Switching to Anthropic's Claude 3.5 Sonnet (verify exact ID on workflowai.com/models)
  const claudeResponse = await client.chat.completions.create({
    model: "my-explainer/claude-3.5-sonnet-latest", // Simply change the model ID
    messages: messages,
  });
  console.log("Claude 3.5 Sonnet says:", claudeResponse.choices[0].message.content?.substring(0, 50) + "...");

  // Switching to Google's Gemini 1.5 Flash (verify exact ID on workflowai.com/models)
   const geminiResponse = await client.chat.completions.create({
    model: "my-explainer/gemini-1.5-flash-latest", // Use the appropriate model identifier
    messages: messages,
  });
   console.log("Gemini 1.5 Flash says:", geminiResponse.choices[0].message.content?.substring(0, 50) + "...");
}

// switchModels(); // Uncomment to run
```
You don't need separate SDKs or API keys for each provider. Find available model IDs at [workflowai.com/models](https://workflowai.com/models).

## Reliable Structured Outputs (with Zod)

WorkflowAI guarantees reliable structured output (like JSON parsed into objects) from *any* model when using the `openai` TypeScript library with Zod schema validation.

1.  Define your desired output structure using a `zod` schema.
2.  Use the `client.beta.chat.completions.parse()` method.
3.  Use the `zodResponseFormat` helper from `openai/helpers/zod` to pass your schema to the `response_format` parameter.
4.  Access the parsed, type-safe object directly from `completion.choices[0].message.parsed`.

```typescript
import OpenAI from 'openai';
// Import zodResponseFormat helper and Zod itself
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from 'zod';

// --- 1. Configuration ---
const client = new OpenAI({
  apiKey: process.env.WORKFLOWAI_API_KEY || 'YOUR_WORKFLOWAI_API_KEY',
  baseURL: 'https://run.workflowai.com/v1',
});

// --- 2. Define Structured Output Schema ---
// Example: Extracting user details
const UserInfoSchema = z.object({
  name: z.string().describe("The full name of the user."),
  email: z.string().email().describe("The email address of the user."),
  department: z.string().optional().describe("The department the user belongs to, if mentioned.")
}).describe("Schema for user information extracted from text.");

// --- 3. Function Definition ---
/**
 * Extracts user information from text using structured output.
 * @param text The text containing user information.
 * @returns A promise resolving to an object matching UserInfoSchema.
 */
async function extractUserInfo(text: string): Promise<z.infer<typeof UserInfoSchema>> {
  try {
    const completion = await client.beta.chat.completions.parse({
      model: 'user-extractor/gpt-4o', // Use an appropriate agent/model
      messages: [
        {
          role: 'system',
          content: 'You are an expert at extracting user details (name, email, department) from text. Respond using the provided tool.',
        },
        {
          role: 'user',
          content: `Extract the user details from the following text: ${text}`,
        },
      ],
      // Define structured response format using Zod schema and the helper
      response_format: zodResponseFormat(UserInfoSchema, "user_information"), // "user_information" is a name for the tool/function
    });

    // Return the parsed, type-safe object
    return completion.choices[0].message.parsed;

  } catch (error) {
    console.error('Error extracting or parsing user info:', error);
    throw error;
  }
}

/*
// --- Example Usage (Conceptual) ---
async function runUserExtraction() {
    try {
        const text1 = "Please contact John Doe at john.doe@example.com regarding the Q3 report.";
        const userInfo1 = await extractUserInfo(text1);
        console.log("User Info 1:", userInfo1);
        // Expected: { name: 'John Doe', email: 'john.doe@example.com' }

        const text2 = "Reach out to Jane Smith from Marketing via jane.s@company.org.";
        const userInfo2 = await extractUserInfo(text2);
        console.log("User Info 2:", userInfo2);
        // Expected: { name: 'Jane Smith', email: 'jane.s@company.org', department: 'Marketing' }

    } catch (e) {
        console.error("Failed to extract user info:", e);
    }
}
// runUserExtraction(); // Uncomment to run
*/
```

A key benefit is WorkflowAI's compatibility: this method works reliably across **all models** available through the proxy, even those without native structured output support. You don't need to explicitly ask for JSON in the prompt.

## Prompt Templating (with Structured Output)

Combine structured output with Jinja2-style templating in your prompts for cleaner code. Pass template variables using the `input` parameter.

```typescript
import OpenAI from 'openai';
import { zodResponseFormat } from "openai/helpers/zod";
import { z } from 'zod';

// --- 1. Configuration ---
const client = new OpenAI({
  apiKey: process.env.WORKFLOWAI_API_KEY || 'YOUR_WORKFLOWAI_API_KEY',
  baseURL: 'https://run.workflowai.com/v1',
});

// --- 2. Define Structured Output Schema ---
const CountryInfoSchema = z.object({
  country: z.string().describe('The country where the city is located.'),
  continent: z.string().describe('The continent where the country is located.'),
});

// --- 3. Function Definition ---
/**
 * Fetches geographical information for a given city using the WorkflowAI proxy,
 * prompt templating, and structured output via zodResponseFormat.
 *
 * @param city The name of the city to query.
 * @returns A promise that resolves to an object matching CountryInfoSchema.
 */
async function getCountryInfo(city: string): Promise<z.infer<typeof CountryInfoSchema>> {
  try {
    const completion = await client.beta.chat.completions.parse({
      model: 'geo-extractor/gpt-4o',
      messages: [
        {
          role: 'system',
          content: 'You are a helpful assistant that provides geographical information.',
        },
        {
          role: 'user',
          // Use a template variable {{input_city}}
          content: 'Where is the city {{input_city}} located? Provide the country and continent.',
        },
      ],
      // Define structured response format using Zod schema
      response_format: zodResponseFormat(CountryInfoSchema, "geographical_info"),
      // Pass the template variable value via input
      // @ts-expect-error input is specific to the WorkflowAI implementation
      input: {
        input_city: city, // Key matches the template variable name
      },
    });

    // Return the parsed, type-safe object
    return completion.choices[0].message.parsed;

  } catch (error) {
    console.error('Error fetching or parsing country info:', error);
    throw error;
  }
}

/*
// --- Example Usage (Conceptual) ---
async function runGeoExample() {
    try {
        const parisInfo = await getCountryInfo("Paris");
        console.log("Paris Info:", parisInfo); // Output: { country: 'France', continent: 'Europe' } (example)

        const tokyoInfo = await getCountryInfo("Tokyo");
        console.log("Tokyo Info:", tokyoInfo); // Output: { country: 'Japan', continent: 'Asia' } (example)
    } catch (e) {
        console.error("Failed to get geo info:", e);
    }
}
// runGeoExample(); // Uncomment to run if in an executable context
*/
```
Using `input` improves observability in WorkflowAI, as these variables are tracked separately.

## Enhanced Reliability via Provider Fallback

WorkflowAI aims for high availability (100% uptime goal) for the core API (`run.workflowai.com`) through redundancy:

*   **AI Provider Fallback (Default: Enabled):** WorkflowAI monitors integrated AI providers (OpenAI, Azure OpenAI, Anthropic, etc.). If your chosen model provider experiences issues, WorkflowAI automatically routes your request to a healthy alternative (e.g., OpenAI API -> Azure OpenAI API) within seconds. This happens seamlessly without code changes.
*   **Datacenter Redundancy:** The WorkflowAI API is deployed across multiple geographic regions (e.g., East US, Central US) with automatic traffic redirection via Azure Front Door if a region has problems.

These features significantly increase your application's resilience. See the [Reliability documentation](/docs/cloud/reliability) for details.

## Other Features

The WorkflowAI proxy supports many other advanced features compatible with the `openai` TypeScript SDK:

*   **Streaming:** Use `stream: true` in your `create` call for token-by-token responses. Supported for all models.
    ```typescript
    async function streamChat() {
      const stream = await client.chat.completions.create({
        model: 'streaming-chatbot/gpt-4o-mini',
        messages: [{ role: 'user', content: 'Tell me a short story.' }],
        stream: true,
      });
      for await (const chunk of stream) {
        process.stdout.write(chunk.choices[0]?.delta?.content || '');
      }
      console.log(); // Newline after stream ends
    }
    // streamChat(); // Uncomment to run
    ```
*   **Cost Calculation:** Access the estimated request cost via `response.choices[0].cost_usd` (may require accessing the raw response or specific handling depending on the SDK method).
*   **User Feedback:** Access the feedback token via `response.choices[0].feedback_token` (may require accessing the raw response or specific handling depending on the SDK method).
*   **Multimodality (Images):** Send image URLs or base64 data in the `messages` array using the standard OpenAI format for models like GPT-4o or Gemini. Combine with structured output for image analysis.
*   **Reply-to (Conversations):** Create stateful conversations by passing `reply_to_run_id: "previous_run_id"` in the request. WorkflowAI automatically prepends history. (See main proxy docs).
*   **Trace ID (Workflows):** Link multi-step calls into a single workflow trace by passing a consistent `trace_id: "workflow_name/uuid"` in the request for each step. (See main proxy docs).
*   **Deployments:** Use server-managed prompt templates and model configurations by specifying `model: "agent-name/#schema_id/deployment_id"`. Allows UI updates without code changes. (See main proxy docs).
*   **Tool Calling:** Full support for OpenAI's tool calling feature (`tools`, `tool_choice`, `tool_calls`, `tool` role messages). (See main proxy docs).

Refer to the main [WorkflowAI OpenAI-Compatible Proxy](/docs/getting-started/proxy) documentation for more detailed explanations and examples of these advanced features.
