from datetime import datetime
from typing import Any, NamedTuple

import openai
import pytest
import workflowai
from pydantic import BaseModel, Field

from tests.e2e.agent_evals.consts import WORKFLOWAI_API_KEY
from tests.e2e.agent_evals.workflowai_eval import workflowai_eval

AGENT_ID = "meeting-summarization"
# Present 'workflowai_eval' (works for proxy, SDK and custom)

# Failing test case:
# http://localhost:3000/workflowai/agents/est-meeting-summary-struct/2/runs?page=0&taskRunId=0197358e-82d2-7351-ae9b-6102e76fe8e5

# Update instructions

# One more thing.
# http://localhost:3000/workflowai/agents/meeting-summarization/1/runs?page=0

"""
    TestCase(
        input_dict={"meeting_transcript": ""},
        assertions=[
            "The summary should be an empty string",
            "The todos should be an empty list",
            "The participants should be an empty list",
        ],
    ),
"""


class TestCase(NamedTuple):
    input_dict: dict[str, Any]
    assertions: list[str]


TEST_CASES = [
    TestCase(
        input_dict={"meeting_transcript": ""},
        assertions=[
            "The summary should be an empty string",
            "The todos should be an empty list",
            "The participants should be an empty list",
        ],
    ),
    TestCase(
        input_dict={"meeting_transcript": "The meeting did not happen"},
        assertions=[
            "The summary should explain that the meeting did not happen",
            "The todos should be an empty list",
            "The participants should be an empty list",
        ],
    ),
    TestCase(
        input_dict={
            "meeting_transcript": """John: Good morning, everyone. Thanks for joining this project kickoff meeting for Project Phoenix.

Alice: Good morning, John. Glad to be here.

Bob: Morning!

John: Let's start with introductions. I'm John, the project manager. Alice, can you go next?

Bob: Cheers!""",
        },
        assertions=[
            "The participants shoulb be Bob, Alice, John",
            "The summary should be a short summary of the meeting",
            "The todos should be empty",
        ],
    ),
]

# PROXY TEST

#


@pytest.mark.parametrize(
    "input, assertions",
    TEST_CASES,
)
async def test_meeting_summarization_proxy_struct_gen(input: dict[str, Any], assertions: list[str]):
    proxy_client = openai.OpenAI(api_key=WORKFLOWAI_API_KEY, base_url="http://localhost:8000/v1")
    now = datetime.now()

    response = proxy_client.beta.chat.completions.parse(
        model="test-meeting-summary-struct/gemini-2.0-flash-001",
        messages=[
            {
                "role": "system",
                "content": "Extract the summary, todos, and participants from the meeting transcript. If the meeting transcript is empty, the summary should be an empty string, the todos should be an empty list, and the participants should be an empty list.",
            },
            {
                "role": "user",
                "content": "Current datetime is {{current_datetime}}. Meeting transcript is {{meeting_transcript}}",
            },
        ],
        response_format=MeetingSummarizationOutput,
        extra_body={"input": {"meeting_transcript": input["meeting_transcript"], "current_datetime": now.isoformat()}},
    )
    await workflowai_eval(response, assertions)


# SDK TEST
class MeetingSummarizationInput(BaseModel):
    meeting_transcript: str
    current_datetime: datetime = Field(default_factory=datetime.now)


class MeetingSummarizationOutput(BaseModel):
    summary: str
    todos: list[str]
    participants: list[str]


@workflowai.agent(id=AGENT_ID, model="gemini-2.0-flash-001")
async def meeting_summarization(input: MeetingSummarizationInput) -> workflowai.Run[MeetingSummarizationOutput]:
    """Extract the summary, todos, and participants from the meeting transcript.
    If the meeting transcript is empty, the summary should be an empty string, the todos should be an empty list, and the participants should be an empty list.
    """
    ...


@pytest.mark.parametrize(
    "input, assertions",
    TEST_CASES,
)
async def test_meeting_summarization_sdk(input: dict[str, Any], assertions: list[str]):
    output = await meeting_summarization(MeetingSummarizationInput(**input))
    await workflowai_eval(output, assertions)


"""
@pytest.mark.skip(reason="Flacky test")
@pytest.mark.parametrize(
    "input, assertions",
    TEST_CASES,
)
async def test_meeting_summarization_proxy(input: dict[str, Any], assertions: list[str]):
    proxy_client = openai.OpenAI(api_key=WORKFLOWAI_API_KEY, base_url="http://localhost:8000/v1")

    now = datetime.now()
    response = proxy_client.chat.completions.create(
        model="test-meeting-summary-raw-text/gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Extract the summary, todos, and participants from the meeting transcript. Output a JSON composed of summary: str, todos: list[str], participants: list[str]",
            },
            {
                "role": "user",
                "content": "Current datetime is {{current_datetime}}. Meeting transcript is {{meeting_transcript}}",
            },
        ],
        extra_body={"input": {"meeting_transcript": input["meeting_transcript"], "current_datetime": now.isoformat()}},
    )
    await workflowai_eval(response, copy.deepcopy(assertions))
"""
