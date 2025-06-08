import logging
import re
from difflib import SequenceMatcher
from typing import List, Optional

import openai
from httpx import AsyncClient
from pydantic import BaseModel, Field

from core.domain.review import ReviewOutcome
from tests.e2e.agent_evals.consts import TENANT, WORKFLOWAI_API_KEY, WORKFLOWAI_API_URL, WORKFLOWAI_USER_TOKEN

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching by removing extra whitespace and converting to lowercase."""
    # Convert to lowercase first
    normalized = text.lower()
    # Replace common punctuation with spaces (instead of removing)
    normalized = re.sub(r'[.,;:!?"\'\-_]', " ", normalized)
    # Remove extra whitespace, newlines, and normalize to single spaces
    normalized = re.sub(r"\s+", " ", normalized.strip())
    return normalized


def fuzzy_contains(verbatim: Optional[str], text: Optional[str], threshold: float = 0.8) -> bool:
    """
    Check if verbatim is contained in text using fuzzy matching.

    Args:
        verbatim: The text to search for
        text: The text to search in
        threshold: Similarity threshold (0.0 to 1.0), default 0.8

    Returns:
        bool: True if verbatim is fuzzy-matched in text
    """
    if not verbatim or not text:
        return False

    # Normalize both strings
    norm_verbatim = normalize_text(verbatim)
    norm_text = normalize_text(text)

    # If normalized verbatim is empty, return False
    if not norm_verbatim:
        return False

    # Check for exact match first (fastest)
    if norm_verbatim in norm_text:
        return True

    # For fuzzy matching, check against sliding windows of the text
    verbatim_len = len(norm_verbatim)
    best_ratio = 0.0

    # Slide through the text with windows of various sizes around the verbatim length
    for window_size in [verbatim_len, verbatim_len + 5, verbatim_len - 5]:
        if window_size <= 0:
            continue

        for i in range(len(norm_text) - window_size + 1):
            window = norm_text[i : i + window_size]
            ratio = SequenceMatcher(None, norm_verbatim, window).ratio()
            best_ratio = max(best_ratio, ratio)

            if best_ratio >= threshold:
                return True

    return best_ratio >= threshold


class ChatAnswerJudgment(BaseModel):
    assertion: str = Field(
        description="The assertion to judge, as passed in, must repeat EXACTLY the assertion passed in, char per char",
    )
    reason: str = Field(description="The reason for the judgment")
    verbatims: List[str] = Field(
        description="The verbatims from the answer that support the judgment, verbatim must be exactly the same as in the answer to judge, char per char",
    )
    is_assertion_enforced: bool = Field(description="Whether the assertion is true or false")


class ChatAnswerJudgmentResponse(BaseModel):
    judgements: List[ChatAnswerJudgment]


async def judge_answer(
    answer_to_judge: str,
    assertions: List[str],
) -> ChatAnswerJudgmentResponse:
    proxy_client = openai.AsyncOpenAI(
        api_key=WORKFLOWAI_API_KEY,
        base_url=WORKFLOWAI_API_URL + "/v1",
    )

    response = await proxy_client.beta.chat.completions.parse(
        model="chat-answer-judge-agent/gemini-2.0-flash-001",
        messages=[
            {
                "role": "system",
                "content": """Judge the answer against the following assertions: {% for assertion in assertions %}
                {{assertion}}
                {% endfor %}""",
            },
            {
                "role": "user",
                "content": "The chat answer to judge is: {{answer_to_judge}}",
            },
        ],
        extra_body={
            "input": {
                "answer_to_judge": answer_to_judge,
                "assertions": assertions,
            },
        },
        response_format=ChatAnswerJudgmentResponse,
    )

    assert response.choices[0].message.parsed

    return response.choices[0].message.parsed


class RegisterAIReviewRequest(BaseModel):
    evaluator_id: str = "llm-as-judge"
    outcome: ReviewOutcome
    positive_aspects: List[str]
    negative_aspects: List[str]


async def register_ai_review(agent_id: str, run_id: str, judge_answer: ChatAnswerJudgmentResponse) -> None:
    request = RegisterAIReviewRequest(
        outcome="positive"
        if all(judgment.is_assertion_enforced for judgment in judge_answer.judgements)
        else "negative",
        positive_aspects=[judgment.assertion for judgment in judge_answer.judgements if judgment.is_assertion_enforced],
        negative_aspects=[
            judgment.assertion for judgment in judge_answer.judgements if not judgment.is_assertion_enforced
        ],
    )
    url = f"{WORKFLOWAI_API_URL}/{TENANT}/agents/{agent_id}/runs/{run_id}/manual-ai-reviews"
    async with AsyncClient() as client:
        response = await client.post(
            url,
            json=request.model_dump(),
            headers={"Authorization": f"Bearer {WORKFLOWAI_USER_TOKEN}"},
        )
        assert response.status_code == 200


async def check_assertions_llm_as_judge(
    answer_to_judge: str,
    assertions: List[str],
    agent_id: str | None = None,
    run_id: str | None = None,
) -> None:
    response = await judge_answer(answer_to_judge, assertions)
    assert len(response.judgements) == len(assertions), (
        "The number of assertions and the number of judgements must be the same"
    )
    for assertion in assertions:
        assert any(judgment.assertion == assertion for judgment in response.judgements), (
            f"The assertion {assertion} was not found in the judgements"
        )

    # remove escape characters in answer_to_judge
    cleaned_answer_to_judge = (
        answer_to_judge.replace("\n", "")
        .replace("\r", "")
        .replace("\t", "")
        .replace("\b", "")
        .replace("\f", "")
        .replace("\a", "")
        .replace("\v", "")
        .replace("\0", "")
    )

    if agent_id and run_id:
        await register_ai_review(agent_id, run_id, response)

    for judgment in response.judgements:
        # check the verbatims are in the answer using fuzzy matching
        for verbatim in judgment.verbatims:
            try:
                assert fuzzy_contains(verbatim, cleaned_answer_to_judge), (
                    f"The verbatim '{verbatim}' was not found in the answer (using fuzzy matching)"
                )
            except Exception as e:
                logger.exception("Verbatim, mismatch error", exc_info=e)

        assert judgment.is_assertion_enforced, (
            f"The assertion {judgment.assertion} was not enforced, reason: {judgment.reason}"
        )
