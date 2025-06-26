import json
from typing import Any, NamedTuple, cast

from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.parsed_chat_completion import ParsedChatCompletion
from pydantic import BaseModel
from workflowai import Run

from tests.e2e.agent_evals.judge_agent import check_assertions_llm_as_judge


class AgentRunIds(NamedTuple):
    agent_id: str
    run_id: str


def extract_proxy_agent_id_and_run_id(raw_id: str) -> AgentRunIds:
    agent_id = raw_id.split("/")[0]
    run_id = raw_id.split("/")[1]
    return AgentRunIds(agent_id=agent_id, run_id=run_id)


async def workflowai_eval(
    output_to_eval: Any,
    assertions: list[str],
    agent_id: str | None = None,
    agent_run_id: str | None = None,
) -> None:
    if isinstance(output_to_eval, Run):  # WorkflowAI run from the SDK
        agent_id = output_to_eval.agent_id
        agent_run_id = output_to_eval.id
        answer_to_judge: str = cast(str, output_to_eval.output.model_dump_json())  # type: ignore[reportUnknownReturnType]
    elif isinstance(output_to_eval, ParsedChatCompletion):  # OpenAI proxy run with structured outputs
        agent_id, agent_run_id = extract_proxy_agent_id_and_run_id(output_to_eval.id)
        answer_to_judge: str = cast(str, output_to_eval.choices[0].message.parsed.model_dump_json())  # type: ignore[reportUnknownReturnType]
    elif isinstance(output_to_eval, ChatCompletion):
        agent_id, agent_run_id = extract_proxy_agent_id_and_run_id(output_to_eval.id)
        answer_to_judge: str = cast(str, output_to_eval.choices[0].message.content)
    elif isinstance(output_to_eval, BaseModel):
        answer_to_judge = json.dumps(output_to_eval.model_dump(mode="json"))
    elif isinstance(output_to_eval, dict):
        answer_to_judge = json.dumps(output_to_eval)
    elif isinstance(output_to_eval, str):
        answer_to_judge = output_to_eval
    else:
        raise ValueError(
            "Output must be a workflowai.Run or openai.ParsedChatCompletion or openai.ChatCompletion",
        )

    await check_assertions_llm_as_judge(
        agent_id=agent_id,
        run_id=agent_run_id,
        answer_to_judge=answer_to_judge,
        assertions=assertions,
    )
