import logging
from time import time
from typing import AsyncIterator

from openai.types.chat.chat_completion_assistant_message_param import ChatCompletionAssistantMessageParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam
from pydantic import BaseModel

from api.routers.openai_proxy._openai_proxy_handler import OpenAIProxyHandler
from api.routers.openai_proxy._openai_proxy_models import (
    OpenAIProxyChatCompletionRequest,
    OpenAIProxyChatCompletionResponse,
    OpenAIProxyMessage,
    OpenAIProxyResponseFormat,
)
from api.services.feedback_svc import FeedbackTokenGenerator
from api.services.groups import GroupService
from api.services.run import RunService
from core.agents.agent_creation_agent import agent_creation_agent
from core.domain.events import EventRouter
from core.domain.fields.chat_message import ChatMessage
from core.domain.tenant_data import TenantData
from core.storage.backend_storage import BackendStorage


class AgentCreationResult(BaseModel):
    agent_id: str
    agent_schema_id: int
    version_id: str
    run_id: str


class AgentCreationChatResponse(BaseModel):
    assistant_answer: str
    agent_creation_result: AgentCreationResult | None


class AgentCreationService:
    def __init__(self, storage: BackendStorage, event_router: EventRouter):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.storage = storage
        self._event_router = event_router

    async def _handle_agent_creation(
        self,
        user_org: TenantData,
        group_service: GroupService,
        run_service: RunService,
        event_router: EventRouter,
        feedback_generator: FeedbackTokenGenerator,
    ):
        # TODO: plug actual data from agent tool call

        handler = OpenAIProxyHandler(
            group_service=group_service,
            storage=self.storage,
            run_service=run_service,
            event_router=event_router,
            feedback_generator=feedback_generator,
        )

        # Create a completion request that will be executed
        completion_request = OpenAIProxyChatCompletionRequest(
            model="gpt-4o-latest",
            messages=[
                OpenAIProxyMessage(
                    role="system",
                    content="You are a helpful assistant called {{name}}",
                ),
            ],
            response_format=OpenAIProxyResponseFormat(
                type="json_schema",
                json_schema=OpenAIProxyResponseFormat.JsonSchema(
                    schema={"type": "object", "properties": {"answer": {"type": "string"}}},
                ),
            ),
            agent_id="example-agent",
            stream=False,
        )

        prepared_run = await handler.prepare_run(completion_request, user_org)

        response = await handler.handle_prepared_run(
            prepared_run=prepared_run,
            body=completion_request,
            metadata=None,
            start_time=time(),
            tenant_data=user_org,
        )

        if not isinstance(response, OpenAIProxyChatCompletionResponse):
            raise Exception("handle_prepared_run with stream=False should return a OpenAIProxyChatCompletionResponse")

        return AgentCreationResult(
            agent_id=prepared_run.variant.task_id,
            agent_schema_id=prepared_run.variant.task_schema_id,
            version_id=response.version_id,
            run_id=response.id.split("/")[-1],
        )

    async def stream_agent_creation(
        self,
        user_org: TenantData,
        group_service: GroupService,
        run_service: RunService,
        event_router: EventRouter,
        feedback_generator: FeedbackTokenGenerator,
        messages: list[ChatMessage],
    ) -> AsyncIterator[AgentCreationChatResponse]:
        openai_messages: list[ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam] = []
        for msg in messages:
            if msg.role == "USER":
                openai_messages.append(
                    ChatCompletionUserMessageParam(
                        role="user",
                        content=msg.content,
                    ),
                )
            elif msg.role == "ASSISTANT":
                openai_messages.append(
                    ChatCompletionAssistantMessageParam(
                        role="assistant",
                        content=msg.content,
                    ),
                )

        acc = ""
        async for chunk in agent_creation_agent(openai_messages):  # pyright: ignore[reportArgumentType]
            self.logger.info(f"agent_creation_agent Chunk: {chunk}")

            has_created_agent = False

            if chunk.assistant_answer:
                acc += chunk.assistant_answer

            if chunk.tool_call and not has_created_agent:
                has_created_agent = True
                agent_creation_result = await self._handle_agent_creation(
                    user_org=user_org,
                    group_service=group_service,
                    run_service=run_service,
                    event_router=event_router,
                    feedback_generator=feedback_generator,
                )
                yield AgentCreationChatResponse(
                    assistant_answer=acc,
                    agent_creation_result=agent_creation_result,
                )

            else:
                yield AgentCreationChatResponse(
                    assistant_answer=acc,
                    agent_creation_result=None,
                )
