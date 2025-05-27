from core.domain.integration.integration_domain import (
    Integration,
    IntegrationKind,
    IntegrationPartner,
    ProgrammingLanguage,
)
from core.domain.integration.snippets.curl_snippets import (
    CURL_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
    CURL_INTEGRATION_CHAT_INITIAL_SNIPPET,
    CURL_LANDING_PAGE_SNIPPET,
    CURL_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
)
from core.domain.integration.snippets.dspy_python_snippets import (
    DSPY_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
    DSPY_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
    DSPY_PYTHON_LANDING_PAGE_SNIPPET,
    DSPY_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
)
from core.domain.integration.snippets.instructor_python_snippets import (
    INSTRUCTOR_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
    INSTRUCTOR_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
    INSTRUCTOR_PYTHON_LANDING_PAGE_SNIPPET,
    INSTRUCTOR_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
)
from core.domain.integration.snippets.langchain_python_snippets import (
    LANGCHAIN_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
    LANGCHAIN_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
    LANGCHAIN_PYTHON_LANDING_PAGE_SNIPPET,
    LANGCHAIN_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
)
from core.domain.integration.snippets.litellm_python_snippets import (
    LITELLM_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
    LITELLM_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
    LITELLM_PYTHON_LANDING_PAGE_SNIPPET,
    LITELLM_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
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
        completion_client="client.chat.completions.create",
        completion_client_structured_output="client.beta.chat.completions.parse",
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
        completion_client="client.chat.completions.create",
        completion_client_structured_output="client.beta.chat.completions.parse",
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
        completion_client="client.chat.completions.create",
        completion_client_structured_output="client.chat.completions.create",
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
    Integration(
        integration_partner=IntegrationPartner.LITELLM,
        programming_language=ProgrammingLanguage.PYTHON,
        default_for_language=False,
        model_name_prefix="openai/",
        output_class="pydantic.BaseModel",
        display_name="LiteLLM (Python)",
        completion_client="litellm.completion",
        completion_client_structured_output="litellm.completion",
        slug=IntegrationKind.LITELLM_PYTHON,
        logo_url="https://workflowai.blob.core.windows.net/workflowai-public/python.png",
        landing_page_snippet=LITELLM_PYTHON_LANDING_PAGE_SNIPPET,
        landing_page_structured_generation_snippet=LITELLM_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
        integration_chat_initial_snippet=LITELLM_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
        integration_chat_agent_naming_snippet=LITELLM_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
        documentation_filepaths=[
            "developers/python/litellm.md",
        ],
    ),
    Integration(
        integration_partner=IntegrationPartner.LANGCHAIN,
        programming_language=ProgrammingLanguage.PYTHON,
        default_for_language=False,
        output_class="pydantic.BaseModel",
        display_name="LangChain (Python)",
        completion_client="invoke",
        completion_client_structured_output="invoke",
        slug=IntegrationKind.LANGCHAIN_PYTHON,
        logo_url="https://workflowai.blob.core.windows.net/workflowai-public/python.png",
        landing_page_snippet=LANGCHAIN_PYTHON_LANDING_PAGE_SNIPPET,
        landing_page_structured_generation_snippet=LANGCHAIN_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
        integration_chat_initial_snippet=LANGCHAIN_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
        integration_chat_agent_naming_snippet=LANGCHAIN_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
        documentation_filepaths=[
            "developers/python/langchain.md",
        ],
    ),
    Integration(
        integration_partner=IntegrationPartner.DSPY,
        programming_language=ProgrammingLanguage.PYTHON,
        default_for_language=False,
        use_version_messages=False,
        output_class="dspy.Signature",
        display_name="DSPy (Python)",
        model_name_prefix="openai/",
        completion_client="dspy.Predict",
        completion_client_structured_output="dspy.Predict",
        slug=IntegrationKind.DSPY_PYTHON,
        logo_url="https://workflowai.blob.core.windows.net/workflowai-public/python.png",
        landing_page_snippet=DSPY_PYTHON_LANDING_PAGE_SNIPPET,
        landing_page_structured_generation_snippet=DSPY_PYTHON_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
        integration_chat_initial_snippet=DSPY_PYTHON_INTEGRATION_CHAT_INITIAL_SNIPPET,
        integration_chat_agent_naming_snippet=DSPY_PYTHON_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
        documentation_filepaths=[
            "developers/python/dspy.md",
        ],
    ),
    Integration(
        integration_partner=IntegrationPartner.CURL,
        programming_language=ProgrammingLanguage.CURL,
        default_for_language=True,
        output_class="JSON schema",
        display_name="Curl (curl)",
        completion_client="curl",
        completion_client_structured_output="curl",
        slug=IntegrationKind.CURL,
        logo_url="https://workflowai.blob.core.windows.net/workflowai-public/http.png",
        landing_page_snippet=CURL_LANDING_PAGE_SNIPPET,
        landing_page_structured_generation_snippet=CURL_LANDING_PAGE_STRUCTURED_GENERATION_SNIPPET,
        integration_chat_initial_snippet=CURL_INTEGRATION_CHAT_INITIAL_SNIPPET,
        integration_chat_agent_naming_snippet=CURL_INTEGRATION_CHAT_AGENT_NAMING_SNIPPET,
        documentation_filepaths=[
            "developers/curl/curl.md",
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
