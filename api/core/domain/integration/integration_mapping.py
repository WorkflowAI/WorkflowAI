from core.domain.integration.integration_domain import (
    Integration,
    IntegrationKind,
    IntegrationPartner,
    ProgrammingLanguage,
)
from core.domain.integration.snippets.instructor_python_snippets import (
    INSTRUCTOR_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
    INSTRUCTOR_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
    INSTRUCTOR_PYTHON_LANDING_PAGE_SNIPPET,
    INSTRUCTOR_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
)
from core.domain.integration.snippets.openai_sdk_python_snippets import (
    OPENAI_SDK_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
    OPENAI_SDK_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
    OPENAI_SDK_PYTHON_LANDING_PAGE_SNIPPET,
    OPENAI_SDK_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
)
from core.domain.integration.snippets.openai_sdk_ts_snippets import (
    OPENAI_SDK_TS_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
    OPENAI_SDK_TS_INTEGRATION_CHAT_INITIAL_SNIPPET,
    OPENAI_SDK_TS_LANDING_PAGE_SNIPPET,
    OPENAI_SDK_TS_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
)

WORKFLOWAI_API_KEY_PLACEHOLDER = "<WORKFLOWAI_API_KEY_PLACEHOLDER>"
PROPOSED_AGENT_NAME_AND_MODEL_PLACEHOLDER = "<PROPOSED_AGENT_NAME_PLACEHOLDER>"


OFFICIAL_INTEGRATIONS = [
    Integration(
        integration_partner=IntegrationPartner.OPENAI_SDK,
        programming_language=ProgrammingLanguage.PYTHON,
        default_for_language=True,
        output_class="pydantic.BaseModel",
        display_name="OpenAI SDK (Python)",
        slug=IntegrationKind.OPENAI_SDK_PYTHON,
        logo_url="https://workflowai.blob.core.windows.net/workflowai-public/python.png",
        landing_page_snippet=OPENAI_SDK_PYTHON_LANDING_PAGE_SNIPPET,
        landing_page_structured_generation_snippet=OPENAI_SDK_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
        integration_chat_initial_snippet=OPENAI_SDK_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
        integration_chat_agent_naming_snippet=OPENAI_SDK_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
        documentation_filepaths=[
            "developers/python/openai.md",
        ],
    ),
    Integration(
        integration_partner=IntegrationPartner.OPENAI_SDK,
        programming_language=ProgrammingLanguage.TYPESCRIPT,
        default_for_language=True,
        output_class="zod.z.object",
        display_name="OpenAI SDK (TypeScript)",
        slug=IntegrationKind.OPENAI_SDK_TS,
        logo_url="https://workflowai.blob.core.windows.net/workflowai-public/ts.png",
        landing_page_snippet=OPENAI_SDK_TS_LANDING_PAGE_SNIPPET,
        landing_page_structured_generation_snippet=OPENAI_SDK_TS_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
        integration_chat_initial_snippet=OPENAI_SDK_TS_INTEGRATION_CHAT_INITIAL_SNIPPET,
        integration_chat_agent_naming_snippet=OPENAI_SDK_TS_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
        documentation_filepaths=[
            "developers/js/openai.md",
        ],
    ),
    Integration(
        integration_partner=IntegrationPartner.INSTRUCTOR,
        programming_language=ProgrammingLanguage.PYTHON,
        default_for_language=False,
        output_class="pydantic.BaseModel",
        display_name="Instructor (Python)",
        slug=IntegrationKind.INSTRUCTOR_PYTHON,
        logo_url="https://workflowai.blob.core.windows.net/workflowai-public/python.png",
        landing_page_snippet=INSTRUCTOR_PYTHON_LANDING_PAGE_SNIPPET,
        landing_page_structured_generation_snippet=INSTRUCTOR_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
        integration_chat_initial_snippet=INSTRUCTOR_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
        integration_chat_agent_naming_snippet=INSTRUCTOR_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
        documentation_filepaths=[
            "developers/python/instructor.md",
        ],
    ),
]

# Build lookup maps for constant-time access. Safe because OFFICIAL_INTEGRATIONS is static.
DEFAULT_INTEGRATIONS_BY_LANGUAGE: dict[ProgrammingLanguage, Integration] = {
    integration.programming_language: integration
    for integration in OFFICIAL_INTEGRATIONS
    if integration.default_for_language
}

INTEGRATIONS_BY_KIND: dict[IntegrationKind, Integration] = {
    integration.slug: integration for integration in OFFICIAL_INTEGRATIONS
}


def default_integration_for_language(language: ProgrammingLanguage) -> Integration:
    try:
        return DEFAULT_INTEGRATIONS_BY_LANGUAGE[language]
    except KeyError as exc:
        raise ValueError(f"No default integration found for language: {language}") from exc


def get_integration_by_kind(kind: IntegrationKind) -> Integration:
    try:
        return INTEGRATIONS_BY_KIND[kind]
    except KeyError as exc:
        raise ValueError(f"No integration found for kind: {kind}") from exc
