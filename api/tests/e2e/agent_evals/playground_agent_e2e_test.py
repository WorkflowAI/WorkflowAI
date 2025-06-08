import datetime
import hashlib
import json
from typing import List, Literal

import openai
import pytest
from httpx import AsyncClient
from pydantic import BaseModel

from api.services.internal_tasks.meta_agent_service import MetaAgentChatMessage, PlaygroundState
from tests.e2e.agent_evals.consts import TENANT, WORKFLOWAI_API_KEY, WORKFLOWAI_API_URL, WORKFLOWAI_USER_TOKEN
from tests.e2e.agent_evals.workflowai_eval import workflowai_eval


class MetaAgentChatResponse(BaseModel):
    messages: List[MetaAgentChatMessage]


class BaseTestScenario:
    @pytest.fixture(autouse=True)
    def setup_messages(self):
        """Auto-setup messages list for each test."""
        self.messages: List[MetaAgentChatMessage] = []

    async def make_playgroud_agent_request(
        self,
        agent_id: str,
        schema_id: int,
        user_message: str | None,
        playground_state: PlaygroundState,
    ) -> tuple[MetaAgentChatResponse, str | None]:
        if user_message is not None:
            self.messages.append(
                MetaAgentChatMessage(
                    role="USER",
                    content=user_message,
                ),
            )

        """Helper to make a request to the playground agent."""
        request_data = {
            "schema_id": schema_id,
            "playground_state": playground_state.model_dump(),
            "messages": [msg if isinstance(msg, dict) else msg.model_dump(mode="json") for msg in self.messages],
        }

        url = f"{WORKFLOWAI_API_URL}/{TENANT}/agents/{agent_id}/prompt-engineer-agent/messages"
        async with AsyncClient() as client:
            response = await client.post(
                url,
                json=request_data,
                headers={"Accept": "text/event-stream", "Authorization": f"Bearer {WORKFLOWAI_API_KEY}"},
                timeout=60.0,
            )

            assert response.status_code == 200

            # Parse streaming response and keep only the last chunk
            last_chunk_messages: List[MetaAgentChatMessage] = []
            last_chunk_agent_run_id: str | None = None
            for line in response.text.strip().split("\n"):
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data and "messages" in data:
                        # Replace previous messages with current chunk's messages
                        last_chunk_messages = []
                        for msg_data in data["messages"]:
                            last_chunk_messages.append(MetaAgentChatMessage(**msg_data))

                    if data and "agent_run_id" in data:
                        last_chunk_agent_run_id = data["agent_run_id"]

            self.messages.extend(
                last_chunk_messages,
            )

            return MetaAgentChatResponse(messages=last_chunk_messages), last_chunk_agent_run_id

    async def get_run_by_id(self, agent_id: str, run_id: str):
        url = f"{WORKFLOWAI_API_URL}/{TENANT}/agents/{agent_id}/runs/{run_id}"
        async with AsyncClient() as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {WORKFLOWAI_API_KEY}"},
            )

        assert response.status_code == 200

        return response.json()

    async def deploy_version(self, agent_id: str, version_id: str, environment_name: str):
        url = f"{WORKFLOWAI_API_URL}/v1/{TENANT}/agents/{agent_id}/versions/{version_id}/deploy"
        async with AsyncClient() as client:
            response = await client.post(
                url,
                json={"environment": environment_name},
                headers={"Authorization": f"Bearer {WORKFLOWAI_USER_TOKEN}"},
            )
            assert response.status_code == 200

    def test_scenario(self):
        pass


class TestScenarioHappyPath(BaseTestScenario):
    @pytest.mark.asyncio
    async def test_scenario_1(self):
        """
        Test the complete happy path user journey through the WorkflowAI platform guided by the Playground Agent (PA).

        This test simulates a typical user workflow from initial agent creation to production deployment:

        1. **Agent Creation**: Creates a sentiment analysis agent via OpenAI proxy with GPT-4o-mini
        2. **Model Exploration**: PA suggests trying different models and provides exact model strings
        3. **Input Variables**: PA guides user to add input variables with {{variable}} syntax
        4. **Structured Outputs**: PA shows how to implement Pydantic models and response_format
        5. **Deployment**: PA provides deployment guidance and documentation links
        6. **Deployment Validation**: PA confirms successful deployment status

        Each stage is validated using LLM-as-judge evaluation to ensure the PA provides appropriate suggestions for the current stage


        The test creates a unique agent name for each run to ensure a clean state and tests
        the PA's ability to detect user progress and provide contextual guidance.
        """

        # compute a 10 chars hash to suffix the agent name in order to "start fresh" every time the test is run
        agent_suffix = hashlib.sha256(str(datetime.datetime.now()).encode()).hexdigest()[:10]
        agent_name = f"e2e-test-sentiment-analyzer-{agent_suffix}"

        proxy_client = openai.OpenAI(
            api_key=WORKFLOWAI_API_KEY,
            base_url=WORKFLOWAI_API_URL + "/v1",
        )

        # First run with OpenAI model, will create the agent on WorkflowAI
        proxy_client.chat.completions.create(
            model=f"{agent_name}/gpt-4o-mini-latest",
            messages=[
                {
                    "role": "system",
                    "content": "classify the sentiment of the following text: This book was super fun to read, though not the last chapter.",
                },
            ],
        )

        playground_state = PlaygroundState(
            is_proxy=True,
            selected_models=PlaygroundState.SelectedModels(
                column_1=None,
                column_2=None,
                column_3=None,
            ),
            agent_run_ids=[],
        )

        # Mimick the first call to the PA, when the user reachs the playground
        PA_answer, _ = await self.make_playgroud_agent_request(
            agent_id=agent_name,
            schema_id=1,
            user_message=None,
            playground_state=playground_state,
        )
        assert PA_answer.messages[0].content == "Hi, I'm WorkflowAI's agent. How can I help you?"

        # Polling
        PA_answer, agent_run_id = await self.make_playgroud_agent_request(
            agent_id=agent_name,
            schema_id=1,
            user_message="poll",
            playground_state=playground_state,
        )
        await workflowai_eval(
            agent_id="proxy-meta-agent",
            agent_run_id=agent_run_id,
            output_to_eval=PA_answer,
            assertions=[
                "The answer must explain that Workflow AI allows to easily switch between models.",
                "The answer must propose at least two models to try.",
                f"The model must provide the the user with the exact model string to copy to the code ({agent_name}/<the model chosen>)",
            ],
        )

        # Second run with a Gemini model, will create the agent on WorkflowAI
        proxy_client.chat.completions.create(
            model=f"{agent_name}/gemini-2.0-flash-001",
            messages=[
                {
                    "role": "system",
                    "content": "classify the sentiment of the following text: This book was super fun to read, though not the last chapter.",
                },
            ],
        )

        # Polling
        PA_answer, agent_run_id = await self.make_playgroud_agent_request(
            agent_id=agent_name,
            schema_id=1,
            user_message="poll",
            playground_state=playground_state,
        )
        await workflowai_eval(
            agent_id="proxy-meta-agent",
            agent_run_id=agent_run_id,
            output_to_eval=PA_answer,
            assertions=[
                "The answer must propose to set up input variables",
                "The code provided must provide the updated messages for the user with variables injected with double curly braces",
                "The code provided must included a part that show how to inject the input variables using 'extra_body': {'input': {...}}",
                "The code must NOT show the usage of structured outputs yet",
            ],
        )

        # Run the agent with input variables
        proxy_client.chat.completions.create(
            model=f"{agent_name}/gemini-2.0-flash-001",
            messages=[
                {
                    "role": "system",
                    "content": "classify the sentiment of the following text: {{text}}",
                },
            ],
            extra_body={"input": {"text": "This book was super fun to read, though not the last chapter."}},
        )

        # Polling
        PA_answer, agent_run_id = await self.make_playgroud_agent_request(
            agent_id=agent_name,
            schema_id=1,
            user_message="poll",
            playground_state=playground_state,
        )
        await workflowai_eval(
            agent_id="proxy-meta-agent",
            agent_run_id=agent_run_id,
            output_to_eval=PA_answer,
            assertions=[
                "The answer must propose to set up structured outputs",
                "The code must provide the structure output class as a Pydantic based model",
                "The code must show where to inject the structured output class in the completion request with response_format",
                "The code must use client.beta.chat.completions.parse NOT, client.chat.completions.create",
                "The code must still make use of the 'extra_body' to inject the input variables and double curly braces in the messages",
            ],
        )

        class SentimentAnalysisOutput(BaseModel):
            sentiment: Literal["positive", "negative", "neutral"]

        run = proxy_client.beta.chat.completions.parse(
            model=f"{agent_name}/gemini-2.0-flash-001",
            messages=[
                {
                    "role": "system",
                    "content": "classify the sentiment of the following text: {{text}}",
                },
            ],
            response_format=SentimentAnalysisOutput,
            extra_body={"input": {"text": "This book was super fun to read, though not the last chapter."}},
        )

        # Polling
        PA_answer, agent_run_id = await self.make_playgroud_agent_request(
            agent_id=agent_name,
            schema_id=1,
            user_message="poll",
            playground_state=playground_state,
        )
        await workflowai_eval(
            agent_id="proxy-meta-agent",
            agent_run_id=agent_run_id,
            output_to_eval=PA_answer,
            assertions=[
                "must propose the user to deploy the agent",
            ],
        )

        # User agrees to deploy the agent
        PA_answer, agent_run_id = await self.make_playgroud_agent_request(
            agent_id=agent_name,
            schema_id=1,
            user_message="Yes please !",
            playground_state=playground_state,
        )
        await workflowai_eval(
            agent_id="proxy-meta-agent",
            agent_run_id=agent_run_id,
            output_to_eval=PA_answer,
            assertions=[
                "must include a link to the deployment documentation",
                "must explain that the user needs to deploy in the UI before updating the code.",
                "must explain how to update the model name in the code once the agent is deployed with '<agent_name>/<agent_schema_id>/<environment_name>'",
                "Must explain that message can be empty now since they are stored in the WorkflowAI deployment in the cloud",
            ],
        )

        last_run_payload = await self.get_run_by_id(agent_name, run.id.split("/")[-1])
        version_id = last_run_payload["group"]["id"]
        await self.deploy_version(
            agent_id=agent_name,
            version_id=version_id,
            environment_name="production",
        )

        # Polling
        PA_answer, agent_run_id = await self.make_playgroud_agent_request(
            agent_id=agent_name,
            schema_id=1,
            user_message="Can you tell me if my agent is deployed ?",
            playground_state=playground_state,
        )
        await workflowai_eval(
            agent_id="proxy-meta-agent",
            agent_run_id=agent_run_id,
            output_to_eval=PA_answer,
            assertions=[
                "must say that the agent is successfully deployed",
                "must mention the 'production' environment",
                "must mention the 'gemini-2.0-flash-001' model",
            ],
        )
