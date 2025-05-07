from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.dependencies.security import UserDep

router = APIRouter(prefix="/integrations")


class Integration(BaseModel):
    slug: str = Field(description="The slug of the integration", examples=["openai-sdk-python", "instructor-python"])
    display_name: str = Field(description="The name of the integration", examples=["OpenAI SDK", "Instructor"])
    language: str = Field(description="The language of the integration", examples=["Python", "TypeScript"])
    logo_url: str = Field(
        description="The URL of the logo of the integration",
        examples=["https://openai.com/images/logo.png", "https://instructor.com/logo.png"],
    )
    code_snippet: str = Field(
        description="A code snippet that shows how to use the integration",
    )
    structured_output_snippet: str = Field(
        description="A code snippet that shows how to use the integration with structured outputs",
    )


class IntegrationListResponse(BaseModel):
    integrations: list[Integration] | None = None


STATIC_INTEGRATIONS = [
    Integration(
        slug="openai-sdk-python",
        display_name="OpenAI SDK (Python)",
        language="Python",
        logo_url="",
        code_snippet="""from openai import OpenAI

# After (WorkflowAI Proxy)
client = OpenAI(
    api_key="wfai-your-key...",  # ← 1. Use your WorkflowAI key
    base_url="https://run.workflowai.com/v1"
)

# Everything else (model calls, parameters) stays the same
response = client.chat.completions.create(
    model="gpt-4o",  # Or claude-3.5-sonnet-large
    messages=[{"role": "user", "content": "Hello!"}]
)""",
        structured_output_snippet="""from pydantic import BaseModel

class UserInfo(BaseModel):
    name: str
    age: int
)

# After (WorkflowAI Proxy)
client = OpenAI(
    api_key="wfai-your-key...",  # ← 1. Use your WorkflowAI key
    base_url="https://run.workflowai.com/v1"
)

# Everything else (model calls, parameters) stays the same
response = client.beta.chat.completions.parse(
    model="gpt-4o",  # Or claude-3.5-sonnet-large
    messages=[{"role": "user", "content": "Hello!"}]
    response_format=UserInfo
)
""",
    ),
    Integration(
        slug="instructor-python",
        display_name="Instructor (Python)",
        language="Python",
        logo_url="",
        code_snippet="""import os

import instructor
from openai import OpenAI
from pydantic import BaseModel


class UserInfo(BaseModel):
    name: str
    age: int

def extract_user_info(user_message: str) -> UserInfo:
    client = instructor.from_openai(
        OpenAI(base_url="https://run.workflowai.com/v1", api_key="<your-workflowai-key>"),
        mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
    )

    return client.chat.completions.create(
        model="user-info-extraction-agent/claude-3-7-sonnet-latest", # Agent now runs Claude 3.7 Sonnet
        response_model=UserInfo,
        messages=[{"role": "user", "content": user_message}],
    )

if __name__ == "__main__":
    user_info = extract_user_info("John Black is 33 years old.")
    print("Basic example result:", user_info)  # UserInfo(name='John Black', age=33)
""",
        structured_output_snippet="""import os

import instructor
from openai import OpenAI
from pydantic import BaseModel


class UserInfo(BaseModel):
    name: str
    age: int

def extract_user_info(user_message: str) -> UserInfo:
    client = instructor.from_openai(
        OpenAI(base_url="https://run.workflowai.com/v1", api_key="<your-workflowai-key>"),
        mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS,
    )

    return client.chat.completions.create(
        model="user-info-extraction-agent/claude-3-7-sonnet-latest", # Agent now runs Claude 3.7 Sonnet
        response_model=UserInfo,
        messages=[{"role": "user", "content": user_message}],
    )

if __name__ == "__main__":
    user_info = extract_user_info("John Black is 33 years old.")
    print("Basic example result:", user_info)  # UserInfo(name='John Black', age=33)
""",
    ),
]


@router.get(
    "",
    description="Get the list of WorkflowAI official integrations",
)
async def list_integrations(user: UserDep) -> IntegrationListResponse:
    return IntegrationListResponse(integrations=STATIC_INTEGRATIONS)


@router.get(
    "/slug/{slug}",
    description="Get one of the WorkflowAI official integrations, by slug",
)
async def get_integration(slug: str) -> Integration:
    integration = next((integration for integration in STATIC_INTEGRATIONS if integration.slug == slug), None)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.get(
    "/language/{language}",
    description="Get the list of WorkflowAI official integrations, for a specific language",
)
async def get_integration_code(language: str) -> IntegrationListResponse:
    integrations = [integration for integration in STATIC_INTEGRATIONS if integration.language == language]
    return IntegrationListResponse(integrations=integrations)
