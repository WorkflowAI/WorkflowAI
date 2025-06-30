# Deployments

This guide walks you through using deployments to update an agent's prompt or model without changing any code. Deployments allow you to separate your code from your AI configuration, enabling faster iteration and non-technical team members to make changes.

## Overview

When using deployments, you:
1. Store your prompt/instructions in WorkflowAI (with or without input variables)
2. Deploy a version (prompt + model) to an environment
3. Update your code to point to the deployed version instead of hardcoded prompts

Your code points to a deployment using a schema number and environment, while the actual prompt and model are managed through the WorkflowAI dashboard.

## Why Use Deployments?

Teams typically use deployments when they want:
- **Non-technical users** to make prompt and model changes without code deployments
- **Faster feedback loops** by avoiding engineering bottlenecks for prompt iterations
- **Cost optimization** by switching to newer, cheaper models without code changes
- **Real-time improvements** based on user feedback without redeploying code

## Step-by-Step Guide

Let's walk through two common scenarios for setting up deployments.

### Scenario 1: Data Extraction Agent (with input variables)

This example shows an agent that extracts event details from emails using input variables.

#### Step 1: Start with a Basic Agent

Here's our initial agent with a hardcoded prompt:

```python
from pydantic import BaseModel

class EventDetails(BaseModel):
    event_name: str
    event_date: str
    event_location: str
    event_description: str

completion = client.beta.chat.completions.parse(
    model="event-extractor/llama4-maverick-instruct-fast",
    messages=[{
        "role": "user",
        "content": "Extract the event details from the following email: " + email_content
    }],
    response_format=EventDetails,
)

print(completion.choices[0].message.parsed)
```

#### Step 2: Add Input Variables to Your Prompt

Replace the hardcoded parts of your prompt with input variables using `{variable_name}` syntax:

```python
completion = client.beta.chat.completions.parse(
    model="event-extractor/llama4-maverick-instruct-fast",
    messages=[{
        "role": "user",
        "content": "Extract the event details from the following email: {email}"
    }],
    response_format=EventDetails,
    extra_body={
        "input": {
            "email": email_content
        }
    }
)
```

**Why input variables?** Input variables help WorkflowAI understand which parts of your prompt are dynamic (change with each request) versus static (part of the prompt template). This separation allows prompt engineers to modify the static template without affecting the dynamic data your code provides.

#### Step 3: Deploy the Version and Update Code

After deploying in the WorkflowAI dashboard:

```python
completion = client.beta.chat.completions.parse(
    model="event-extractor/#1/production",
    messages=[],  # Empty because prompt is now stored in WorkflowAI
    response_format=EventDetails,
    extra_body={
        "input": {
            "email": email_content
        }
    }
)
```

### Scenario 2: Chatbot Agent (no input variables needed)

This example shows a chatbot where all instructions are stored as the system message in WorkflowAI.

#### Step 1: Start with a Basic Chatbot

Here's a chatbot with hardcoded system instructions:

```python
completion = client.chat.completions.create(
    model="customer-support-bot/gpt-4o-mini",
    messages=[
        {
            "role": "system", 
            "content": "You are a helpful customer support agent for TechCorp. Always be polite, provide accurate information about our products, and escalate complex issues to human agents."
        },
        {
            "role": "user", 
            "content": user_message
        }
    ]
)

print(completion.choices[0].message.content)
```

#### Step 2: Deploy and Update Code

The system message becomes the "prompt" stored in WorkflowAI. After deploying:

```python
completion = client.chat.completions.create(
    model="customer-support-bot/#1/production",
    messages=[
        {
            "role": "user", 
            "content": user_message
        }
    ]  # System message now comes from the deployment
)

print(completion.choices[0].message.content)
```

**Key difference**: No `extra_body.input` needed since there are no input variables. The user message is still provided normally in the messages array, but the system message (instructions) comes from the deployed prompt.

## Deploying a Version

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/58dfabcb7b91f2a57d99602876dc98f1/watch" %}

For both scenarios, the deployment process is the same:

1. Go to the **Deployments** section in the WorkflowAI dashboard
2. Select your target environment: `development`, `staging`, or `production`
3. Click **Deploy Version**
4. Choose the version (prompt + model combination) you want to deploy
5. Click **Deploy**

The deployment will be associated with a schema number that defines:
- **Input variables** your code must provide (if any)
- **Output format** (response_format) your code expects (if using structured outputs)

You can view all schemas in the **Schemas** section of the WorkflowAI dashboard.

## Understanding the Model Parameter Format

When using deployments, your model parameter follows this format:
`"agent-name/#schema-number/environment"`

- **agent-name** = your agent name
- **#schema-number** = schema number (defines input/output contract)
- **environment** = `development`, `staging`, or `production`

{% hint style="warning" %}
**Important**: The OpenAI SDK requires a `messages` parameter to be present. When using deployments:
- **With input variables** (Scenario 1): Pass an empty array `messages=[]` because the prompt is stored in WorkflowAI
- **Without input variables** (Scenario 2): Pass your user message normally in the `messages` array, but the system message comes from the deployment

Never omit the `messages` parameter entirely as this will cause SDK errors.
{% endhint %}

## Understanding Schemas

Schemas define the "contract" between your code and the deployment. A schema includes:
- **Input variables** that must be provided in `extra_body.input` (if using input variables)
- **Output format** structure (your `response_format`, if using structured outputs)

**Schemas are automatically created by WorkflowAI** when you make changes to input variables or output formats. You don't manually create or manage schema numbers - WorkflowAI detects incompatible changes and assigns new schema numbers automatically.

### When Schema Numbers Are Automatically Incremented

WorkflowAI automatically creates a new schema number when you change:
- Input variable names, add new ones, or remove existing ones
- The structure of your `response_format` (add/remove fields, change types)

### Schema Migration Workflow

When you need to change the schema:
1. Create a new version with updated input variables or output format in WorkflowAI
2. **WorkflowAI automatically detects the changes and assigns a new schema number** (like `#2`)
3. Deploy the new version to your target environment
4. Update your code to use the new schema number: `"agent-name/#2/production"`
5. Test thoroughly before deploying to production

This ensures backward compatibility - existing code using `#1` continues working while new code uses `#2`.

You can view all automatically generated schemas in the **Schemas** section of the WorkflowAI dashboard.

## Error Handling

<!-- TODO @guillaume: Document specific error types and messages returned when:
- Input variables are missing from extra_body.input
- Input variable names don't match the deployed schema  
- response_format doesn't match the deployed schema
- Schema number doesn't exist
- Environment doesn't have a deployment
-->

When there's a mismatch between your code and the deployed schema (missing input variables or incompatible response_format), the API will return an error. 

## Important Notes

- **Agent-specific**: Deployments work with named agents only, not the `default` agent
- **Environment isolation**: Each environment (development/staging/production) has independent deployments
- **Schema independence**: You can have different deployments for each schema without affecting each other
- **Input variables optional**: Not all agents need input variables - simple chatbots can store all instructions in the deployed prompt

<!-- TODO: Add link to agent identification section when available -->

## Next Steps

