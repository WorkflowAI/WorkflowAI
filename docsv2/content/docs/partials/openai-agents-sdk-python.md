---
title: OpenAI Agents SDK (Python)
summary: How to use the official OpenAI Agents SDK (Python) with WorkflowAI with input variables and structured outputs. https://openai.github.io/openai-agents-python/
---

```python
from openai import AsyncOpenAI
from agents import (
    Agent,
    Runner,
    set_default_openai_client,
    set_default_openai_api,
    set_tracing_disabled,
)
from agents import ModelSettings, RunConfig
from pydantic import BaseModel

workflowai_client = AsyncOpenAI(
    base_url="https://api.workflowai.dev/v1/", # keep the trailing slash – the SDK expects it.
    api_key="wai-***" # use create_api_key MCP tool
)

# Make every model call go through WorkflowAI
set_default_openai_client(workflowai_client)
# WorkflowAI currently only supports the Chat Completions API
set_default_openai_api("chat_completions")
# tracing must be disabled
set_tracing_disabled(True)

translation_agent = Agent(
    name="Translator",
    instructions=(
        "You are a professional translator in the style of {{author}}. " # input variables are recommended to pass variables in the instructions
        "Translate the user's input from English to French. "
        "Respond ONLY with the translation; no extra commentary."
    ),
    model="gpt-4o-mini",
    model_settings=ModelSettings(
        metadata={"agent_id": "translator-agent"} # recommended: set `agent_id` to identify your agent in the WorkflowAI UI
    )
)

# Example of running with input variables
def run_agent(agent, user_message, input_variables, **kwargs):
    run_config = RunConfig(
        model_settings=ModelSettings(
            extra_body={"input": input_variables}
        ),
        **kwargs
    )

    return Runner.run_sync(agent, user_message, run_config=run_config)

# Usage example:
result = run_agent(
    translation_agent,
    "Hello, how are you today?",
    {"author": "Shakespeare"}
)

print(result.final_output)

# structured outputs (https://openai.github.io/openai-agents-python/agents/#output-types)

class EmailAnalysis(BaseModel):
    summary: str
    key_points: list[str]
    action_items: list[str]

email_analyzer_agent = Agent(
    name="Email Analyzer",
    instructions=(
        "You are a helpful assistant that analyzes emails and provides a summary of the content. Analyze the following email: {{email}}"
    ),
    model="gpt-4o-mini",
    model_settings=ModelSettings(
        metadata={"agent_id": "email-analyzer-agent"}
    ),
    output_type=EmailAnalysis
)

# Generate a realistic email for testing
realistic_email = """
Subject: Q4 Marketing Campaign Review & Budget Approval Needed

Hi Team,

I hope this email finds you well. As we approach the end of Q3, I wanted to touch base regarding our Q4 marketing campaign planning.

Key Updates:
- Our social media engagement is up 23% compared to last quarter
- The email marketing campaign generated 1,200 new leads
- Website traffic increased by 15% month-over-month
- However, our conversion rate has dropped to 2.8% (down from 3.2%)

Action Items Needed:
1. Please review the attached Q4 budget proposal and provide feedback by Friday
2. Marketing team needs to schedule a strategy session for next week
3. We need approval for the additional $15K budget for paid advertising
4. Design team should prepare mockups for the holiday campaign by Oct 15th

The CMO wants to discuss this in our Monday meeting, so please come prepared with your thoughts on the conversion rate decline and potential solutions.

Let me know if you have any questions or concerns.

Best regards,
Sarah Mitchell
VP of Marketing
sarah.mitchell@company.com
(555) 123-4567
"""

result = run_agent(
    email_analyzer_agent,
    "", # no user messages required, {{email}} is an input variable in the instructions
    {"email": realistic_email}
)

print("Email Analysis Result:")
print(f"Summary: {result.final_output.summary}")
print(f"Key Points: {result.final_output.key_points}")
print(f"Action Items: {result.final_output.action_items}")
```
