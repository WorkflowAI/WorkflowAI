import logging
import os
from typing import Literal

import openai
from pydantic import BaseModel, Field

# Configure the OpenAI client to use WorkflowAI
client = openai.OpenAI(
    api_key=os.environ.get("WORKFLOWAI_API_KEY"),
    base_url=f"{os.environ.get('WORKFLOWAI_API_URL')}/v1",
)


class EmailPriority(BaseModel):
    reasoning: str = Field(
        description="Brief explanation of why this priority was assigned",
    )
    priority: Literal["high", "medium", "low"] = Field(
        description="Priority level based on urgency and importance",
    )


def prioritize_email(email_content: str):
    completion = client.chat.completions.create(
        model="test-email-prioritizer/gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": """You are an intelligent email prioritization assistant.

Analyze emails and assign priority levels based on:
- URGENCY: Time-sensitive matters, deadlines, meetings
- IMPORTANCE: Impact on work, relationships, or goals
- SENDER: VIP contacts, colleagues, customers vs spam/marketing
- CONTENT: Action items, requests, information sharing
- CONTEXT: Keywords like "urgent", "asap", "deadline", "meeting"

Priority Guidelines:
- HIGH: Urgent + Important (CEO emails, client issues, deadlines today)
- MEDIUM: Important but not urgent, or urgent but less important
  * Meeting notes, summaries, and follow-ups from colleagues
  * Work-related information sharing that may contain decisions or action items
  * Updates from team members about project progress or outcomes
- LOW: FYI emails, newsletters, marketing, non-urgent personal updates

Be concise but thorough in your analysis.

Respond with a JSON object that has a reasoning and priority (high, medium, low) fields
""",
            },
            {
                "role": "user",
                "content": f"Please prioritize this email:\n\n{email_content}",
            },
        ],
    )

    content = completion.choices[0].message.content
    if not content:
        raise ValueError("No content returned from the model")
    return EmailPriority.model_validate_json(content)


# Example usage
if __name__ == "__main__":
    sample_email = {
        "body": "Hi team, our client ABC Corp has requested to move today's 3pm meeting to 2pm. Please confirm if you can attend. We need to discuss the Q4 contract renewal.",
    }

    logging.info("=== Single Email Prioritization ===")
    priority = prioritize_email(
        email_content=sample_email["body"],
    )

    logging.info(f"Priority: {priority.priority.upper() if priority else 'None'}")  # noqa G004
    logging.info(f"Reasoning: {priority.reasoning if priority else 'None'}")  # noqa G004
