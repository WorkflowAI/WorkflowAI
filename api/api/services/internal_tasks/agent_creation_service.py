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
from api.services.documentation_service import DocumentationService
from api.services.feedback_svc import FeedbackTokenGenerator
from api.services.groups import GroupService
from api.services.run import RunService
from core.agents.agent_creation_agent import CreateAgentToolCall, agent_creation_agent
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
        agent_creation_tool_call: CreateAgentToolCall,
    ):
        handler = OpenAIProxyHandler(
            group_service=group_service,
            storage=self.storage,
            run_service=run_service,
            event_router=event_router,
            feedback_generator=feedback_generator,
        )

        messages = [
            OpenAIProxyMessage(
                role="system",
                content=agent_creation_tool_call.system_message_content,
            ),
        ]
        if agent_creation_tool_call.user_message_content:
            messages.append(
                OpenAIProxyMessage(
                    role="user",
                    content=agent_creation_tool_call.user_message_content,
                ),
            )

        completion_request = OpenAIProxyChatCompletionRequest(
            model="gpt-4o-latest",
            messages=messages,
            agent_id=agent_creation_tool_call.agent_name,
            stream=False,
        )

        if agent_creation_tool_call.response_format:
            completion_request.response_format = OpenAIProxyResponseFormat(
                type="json_schema",
                json_schema=OpenAIProxyResponseFormat.JsonSchema(
                    schema=agent_creation_tool_call.response_format,
                ),
            )

        if agent_creation_tool_call.example_input_variables:
            completion_request.input = agent_creation_tool_call.example_input_variables

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

    async def _get_tools_docs(self) -> str:
        tool_docs = await DocumentationService().get_documentation_by_path(
            paths=["agents/tools"],
        )
        return "\n".join([doc.content for doc in tool_docs])

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
            match msg.role:
                case "USER":
                    openai_messages.append(
                        ChatCompletionUserMessageParam(
                            role="user",
                            content=msg.content,
                        ),
                    )
                case "ASSISTANT":
                    openai_messages.append(
                        ChatCompletionAssistantMessageParam(
                            role="assistant",
                            content=msg.content,
                        ),
                    )

        tools_docs = await self._get_tools_docs()

        assistant_answer = ""
        agent_creation_tool_call: CreateAgentToolCall | None = None
        async for chunk in agent_creation_agent(openai_messages, tools_docs):  # pyright: ignore[reportArgumentType]
            assistant_answer = chunk.assistant_answer

            if chunk.agent_creation_tool_call:
                agent_creation_tool_call = chunk.agent_creation_tool_call

            else:
                yield AgentCreationChatResponse(
                    assistant_answer=assistant_answer,
                    agent_creation_result=None,
                )

        if agent_creation_tool_call:
            agent_creation_result = await self._handle_agent_creation(
                user_org=user_org,
                group_service=group_service,
                run_service=run_service,
                event_router=event_router,
                feedback_generator=feedback_generator,
                agent_creation_tool_call=agent_creation_tool_call,
            )
            yield AgentCreationChatResponse(
                assistant_answer=assistant_answer,
                agent_creation_result=agent_creation_result,
            )
