from typing import AsyncIterator, Self

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.dependencies.security import UserDep
from api.dependencies.services import IntegrationAgentServiceDep
from api.services.internal_tasks.integration_service import (
    IntegrationChatMessage,
    IntegrationChatResponse,
)
from core.domain.integration_domain import OFFICIAL_INTEGRATIONS, IntegrationKind
from core.domain.integration_domain import Integration as DomainIntegration
from core.utils.stream_response_utils import safe_streaming_response

router = APIRouter(prefix="/integrations")


class Integration(BaseModel):
    id: IntegrationKind = Field(
        description="The slug of the integration",
    )
    display_name: str = Field(description="The name of the integration", examples=["OpenAI SDK", "Instructor"])
    programming_language: str = Field(description="The language of the integration", examples=["Python", "TypeScript"])
    logo_url: str = Field(
        description="The URL of the logo of the integration",
        examples=["https://openai.com/images/logo.png", "https://instructor.com/logo.png"],
    )
    code_snippet: str = Field(
        description="A code snippet that shows how to use the integration",
    )
    structured_output_snippet: str | None = Field(
        description="A code snippet that shows how to use the integration with structured outputs",
    )

    @classmethod
    def from_domain(cls, domain_integration: DomainIntegration) -> Self:
        return cls(
            id=domain_integration.slug,
            display_name=domain_integration.display_name,
            programming_language=domain_integration.programming_language,
            logo_url=domain_integration.logo_url,
            code_snippet=domain_integration.landing_page_snippet,
            structured_output_snippet=domain_integration.landing_page_structured_generation_snippet,
        )


class IntegrationListResponse(BaseModel):
    integrations: list[Integration] | None = None


@router.get(
    "",
    description="Get the list of WorkflowAI official integrations",
)
async def list_integrations(user: UserDep) -> IntegrationListResponse:
    return IntegrationListResponse(
        integrations=[Integration.from_domain(integration) for integration in OFFICIAL_INTEGRATIONS],
    )


@router.get(
    "/search",
    description="Search for WorkflowAI official integrations by id or language",
)
async def search_integrations(
    id: IntegrationKind | None = None,
    language: str | None = None,
) -> IntegrationListResponse | Integration:
    # If id is provided, return a single integration
    if id:
        integration = next((integration for integration in OFFICIAL_INTEGRATIONS if integration.slug == id), None)
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        return Integration.from_domain(integration)

    # If language is provided, filter by language
    if language:
        integrations = [
            integration for integration in OFFICIAL_INTEGRATIONS if integration.programming_language == language
        ]
        return IntegrationListResponse(
            integrations=[Integration.from_domain(integration) for integration in integrations],
        )

    # If no parameters provided, return all integrations
    return IntegrationListResponse(
        integrations=[Integration.from_domain(integration) for integration in OFFICIAL_INTEGRATIONS],
    )


class IntegrationAgentChatRequest(BaseModel):
    integration_slug: IntegrationKind = Field(
        description="The slug of the integration that the user is trying to integrate",
    )
    messages: list[IntegrationChatMessage] = Field(
        description="The list of messages in the conversation, the last message being the most recent one",
    )


@router.post(
    "/messages",
    description="To chat with WorkflowAI's integration agent",
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": IntegrationChatResponse.model_json_schema(),
                },
            },
        },
    },
)
async def get_integration_chat_answer(
    request: IntegrationAgentChatRequest,
    integration_service: IntegrationAgentServiceDep,
) -> StreamingResponse:
    async def _stream() -> AsyncIterator[BaseModel]:
        async for chunk in integration_service.stream_integration_chat_response(
            integration_slug=request.integration_slug,
            messages=request.messages,
        ):
            yield chunk

    return safe_streaming_response(_stream)
