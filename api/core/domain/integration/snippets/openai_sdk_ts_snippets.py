# ---------------------------------------------------------------------------
# OpenAI SDK (TypeScript/JavaScript) – WorkflowAI Integration Code Snippets
# ---------------------------------------------------------------------------
# These snippets are embedded in the public documentation and within the in-app
# onboarding flow. They MUST be valid TypeScript / modern JavaScript so that
# developers can copy-paste them directly into a Create-React-App / Node / Bun
# or Vite project without modification.


# Landing Page (Basic Usage) --------------------------------------------------
OPENAI_SDK_TS_LANDING_PAGE_SNIPPET = """```typescript
import OpenAI from 'openai';

// 1. Configuration – point the OpenAI SDK at WorkflowAI
const client = new OpenAI({
  apiKey: process.env.WORKFLOWAI_API_KEY || 'YOUR_WORKFLOWAI_API_KEY',
  baseURL: 'https://run.workflowai.com/v1',
});

// 2. Simple chat request
const response = await client.chat.completions.create({
  // Always prefix the model with an agent name for better organisation in WorkflowAI
  model: 'quick-start-agent/gpt-4o-mini',
  messages: [
    { role: 'system', content: 'You are a helpful assistant.' },
    { role: 'user', content: 'Hello!' },
  ],
});

console.log(response.choices[0].message.content);
```"""


# Landing Page (Reliable Structured Output) -----------------------------------
# Requires openai@^4.55.0 for `beta.chat.completions.parse`.
OPENAI_SDK_TS_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET = """```typescript
import OpenAI from 'openai';
import { z } from 'zod';
import { zodResponseFormat } from 'openai/helpers/zod';

// 1. Configuration – WorkflowAI proxy
const client = new OpenAI({
  apiKey: process.env.WORKFLOWAI_API_KEY || 'YOUR_WORKFLOWAI_API_KEY',
  baseURL: 'https://run.workflowai.com/v1',
});

// 2. Define a Zod schema for structured output
const CountryInfoSchema = z.object({
  country: z.string().describe('The country where the city is located.'),
  continent: z.string().describe('The continent of the country.'),
});

// 3. Function wrapping a structured request
export async function getCountryInfo(city: string) {
  const completion = await client.beta.chat.completions.parse({
    model: 'geo-extractor/gpt-4o',
    messages: [
      { role: 'system', content: 'You are a helpful assistant that provides geographical information.' },
      { role: 'user', content: `Which country is ${city} in and on which continent?` },
    ],
    // Validate & parse against the Zod schema
    response_format: zodResponseFormat(CountryInfoSchema, 'country_info'),
  });

  // The SDK returns a parsed object in `message.parsed`
  return completion.choices[0].message.parsed;
}
```"""


# Integration Chat – Initial "How-To" Message ----------------------------------
# NOTE: The <WORKFLOWAI_API_KEY_PLACEHOLDER> token is dynamically replaced by
# the backend when sending instructions to the user. Do not rename it.
OPENAI_SDK_TS_INTEGRATION_CHAT_INITIAL_SNIPPET = """```typescript
import OpenAI from 'openai';

// After (WorkflowAI Proxy)
const client = new OpenAI({
  apiKey: <WORKFLOWAI_API_KEY_PLACEHOLDER>,
  baseURL: 'https://run.workflowai.com/v1', // OpenAI SDK now uses WorkflowAI's chat completion API endpoint
});

// Everything else (model calls, parameters) stays the same
const response = await client.chat.completions.create({
  ...,
});
```"""


# Integration Chat – Suggesting Agent-Prefixed Model Name ----------------------
OPENAI_SDK_TS_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET = """```typescript
const response = await client.chat.completions.create({
  model: '<PROPOSED_AGENT_NAME_PLACEHOLDER>',
  ...
});
```"""
