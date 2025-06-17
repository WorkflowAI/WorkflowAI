import os

import openai
from pydantic import BaseModel, Field

client = openai.OpenAI(
    api_key=os.environ.get("WORKFLOWAI_API_KEY"),
    base_url=os.environ.get("WORKFLOWAI_API_PROXY_URL"),
)


class MeetingSummarizerOutput(BaseModel):
    summary: str = Field(description="A concise summary of the meeting")
    key_points: list[str] = Field(description="A list of key points from the meeting")
    participants: list[str] = Field(description="A list of participants in the meeting")

    class Todo(BaseModel):
        title: str = Field(description="The title of the todo")
        description: str | None = Field(description="The description of the todo", default=None)
        due_date: str | None = Field(description="The due date of the todo", default=None)
        participant_assigned: str | None = Field(description="The participant assigned to the todo", default=None)

    todos: list[Todo] = Field(description="A list of todos from the meeting")


response = client.beta.chat.completions.parse(
    model="claude-3-5-sonnet-latest",
    messages=[  # Message contains the "static" parts of the agents instructions, with same placeholder {{}} where variables will be injected at runtime
        {
            "role": "system",
            "content": "You are a helpful assistant that summarizes meetings. You will be given a meeting transcript and you will need to summarize the meeting in a concise manner and extract the key points and todos. Current datetime is {{current_datetime}}",
        },
        {
            "role": "user",
            "content": "Here is the meeting transcript: {{meeting_transcript}}",
        },
    ],
    response_format=MeetingSummarizerOutput,  # Defines the output format for the agent (uses structured generation)
    extra_body={  # Extra body contains the variables, the "dynamic" parts of the agents instructions, with same placeholder {{}} where variables will be injected at runtime
        "input": {
            "current_datetime": "2025-06-10 10:00:00",
            "meeting_transcript": """
Sarah Johnson (Product Manager): Good morning everyone, thank you for joining our Q2 product roadmap review. We have about an hour to cover our progress and plan for the next quarter. Let's start with Alex updating us on the mobile app development.

Alex Chen (Engineering Lead): Thanks Sarah. We've made solid progress on the mobile app. The authentication system is complete, and we've finished the core user interface. However, we're running about two weeks behind schedule due to some technical challenges with the payment integration. We discovered the third-party API we planned to use has some limitations that weren't apparent in the initial evaluation.

Sarah Johnson: That's concerning. What are our options to get back on track?

Alex Chen: We have two options. First, we could implement a workaround that would take about a week but might limit some features. Second, we could switch to a different payment provider, which would take three weeks but give us better long-term capabilities.

Mike Rodriguez (Finance): From a budget perspective, switching providers now could impact our Q3 projections. What's the cost difference?

Alex Chen: The new provider has a slightly higher transaction fee, about 0.2% more, but they offer better fraud protection and international support.

Lisa Park (Marketing): The international support could be huge for our Q4 expansion plans. We're already planning campaigns for European markets.

Sarah Johnson: Good point Lisa. Let's go with the provider switch. Alex, can you put together a detailed timeline and share it by Friday?

Alex Chen: Absolutely, I'll have that ready.

Sarah Johnson: Now let's discuss the customer feedback from our beta release. Lisa, what are you seeing?

Lisa Park: Overall response has been positive. We're seeing a 78% satisfaction rate in our surveys. The main complaints are about the onboarding process being too lengthy and some confusion around the pricing tiers. We need to streamline the signup flow.

Sarah Johnson: Mike, can we look into simplifying our pricing structure?

Mike Rodriguez: I'll work with the team to create some options. Maybe we can reduce from four tiers to three and make the differences clearer.

Sarah Johnson: Perfect. What about support tickets, David?

David Kim (Customer Success): We're averaging about 45 tickets per day, which is manageable. Most common issues are password resets and billing questions. I think if we improve the onboarding that Lisa mentioned, we could reduce this by about 30%.

Sarah Johnson: Excellent. Let's wrap up with action items. Alex, you'll deliver the payment provider timeline by Friday. Mike, pricing structure options by next Wednesday. Lisa, can you draft a proposal for the simplified onboarding flow?

Lisa Park: Sure, I'll have that ready by Monday.

Sarah Johnson: Great. David, please prepare a support ticket analysis for our next meeting. Any other questions before we wrap up?

Alex Chen: Just one - should we schedule a follow-up specifically for the European expansion planning?

Sarah Johnson: Yes, let's do that. I'll send out a calendar invite for next Thursday. Thanks everyone, great meeting.
            """,
        },
    },
    metadata={
        "agent_id": "meeting-summarizer",
    },
)


# Print the response
print(f"Response: {response.choices[0].message.parsed}")  # noqa: T201


# Print the cost of the run
if response.choices[0].model_extra is not None:
    print(f"Cost: {response.choices[0].model_extra.get('cost_usd', 'cost not available')} dollars")  # noqa: T201
