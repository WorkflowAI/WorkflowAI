import logging
import os

import openai

# Configure the OpenAI client to use WorkflowAI
client = openai.OpenAI(
    api_key=os.environ.get("WORKFLOWAI_API_KEY"),
    base_url=os.environ.get("WORKFLOWAI_API_PROXY_URL"),
)


def prioritize_email(email_content: str):
    completion = client.chat.completions.create(
        model="gpt-4o-latest",
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

Output ONLY the priority level (HIGH, MEDIUM, LOW) no other text.""",
            },
            {
                "role": "user",
                "content": f"Please prioritize this email:\n\n{email_content}",
            },
        ],
    )

    return completion.choices[0].message.content


# Example usage
if __name__ == "__main__":
    sample_email = {
        "body": "Hi team, our client ABC Corp has requested to move today's 3pm meeting to 2pm. Please confirm if you can attend. We need to discuss the Q4 contract renewal.",
    }

    logging.info("=== Single Email Prioritization ===")
    priority = prioritize_email(
        email_content=sample_email["body"],
    )

    print(priority)
