from typing import Any, Dict

import pytest

from core.domain.integration.integration_domain import (
    Integration,
    IntegrationKind,
    IntegrationPartner,
    ProgrammingLanguage,
)
from core.domain.message import Message, MessageContent
from core.domain.tool import Tool
from core.services.integration_template_service import IntegrationTemplateService
from core.tools import ToolKind


@pytest.fixture
def openai_python_integration():
    return Integration(
        integration_partner=IntegrationPartner.OPENAI_SDK,
        programming_language=ProgrammingLanguage.PYTHON,
        completion_client="openai.OpenAI",
        completion_client_structured_output="openai.OpenAI.beta.chat.completions.parse",
        default_for_language=True,
        logo_url="",
        landing_page_snippet="",
        slug=IntegrationKind.OPENAI_SDK_PYTHON,
        display_name="OpenAI SDK Python",
        documentation_filepaths=[],
        integration_chat_initial_snippet="",
        integration_chat_agent_naming_snippet="",
        output_class="OutputData",
    )


@pytest.fixture
def openai_ts_integration():
    return Integration(
        integration_partner=IntegrationPartner.OPENAI_SDK_TS,
        programming_language=ProgrammingLanguage.TYPESCRIPT,
        completion_client="openai.OpenAI",
        completion_client_structured_output="openai.OpenAI.beta.chat.completions.parse",
        default_for_language=True,
        logo_url="",
        landing_page_snippet="",
        slug=IntegrationKind.OPENAI_SDK_TS,
        display_name="OpenAI SDK TypeScript",
        documentation_filepaths=[],
        integration_chat_initial_snippet="",
        integration_chat_agent_naming_snippet="",
        output_class="OutputData",
    )


@pytest.fixture
def instructor_integration():
    return Integration(
        integration_partner=IntegrationPartner.INSTRUCTOR,
        programming_language=ProgrammingLanguage.PYTHON,
        completion_client="instructor.from_openai",
        completion_client_structured_output="instructor.from_openai",
        default_for_language=False,
        logo_url="",
        landing_page_snippet="",
        slug=IntegrationKind.INSTRUCTOR_PYTHON,
        display_name="Instructor Python",
        documentation_filepaths=[],
        integration_chat_initial_snippet="",
        integration_chat_agent_naming_snippet="",
        output_class="OutputData",
    )


@pytest.fixture
def curl_integration():
    return Integration(
        integration_partner=IntegrationPartner.CURL,
        programming_language=ProgrammingLanguage.CURL,
        completion_client="curl",
        completion_client_structured_output="curl",
        default_for_language=False,
        logo_url="",
        landing_page_snippet="",
        slug=IntegrationKind.CURL,
        display_name="curl",
        documentation_filepaths=[],
        integration_chat_initial_snippet="",
        integration_chat_agent_naming_snippet="",
        output_class="OutputData",
    )


@pytest.fixture
def dspy_integration():
    return Integration(
        integration_partner=IntegrationPartner.DSPY,
        programming_language=ProgrammingLanguage.PYTHON,
        completion_client="dspy.LM",
        completion_client_structured_output="dspy.LM",
        default_for_language=False,
        logo_url="",
        landing_page_snippet="",
        slug=IntegrationKind.DSPY_PYTHON,
        display_name="DSPy Python",
        documentation_filepaths=[],
        integration_chat_initial_snippet="",
        integration_chat_agent_naming_snippet="",
        output_class="OutputData",
    )


@pytest.fixture
def langchain_integration():
    return Integration(
        integration_partner=IntegrationPartner.LANGCHAIN,
        programming_language=ProgrammingLanguage.PYTHON,
        completion_client="langchain_openai.ChatOpenAI",
        completion_client_structured_output="langchain_openai.ChatOpenAI.with_structured_output",
        default_for_language=False,
        logo_url="",
        landing_page_snippet="",
        slug=IntegrationKind.LANGCHAIN_PYTHON,
        display_name="LangChain Python",
        documentation_filepaths=[],
        integration_chat_initial_snippet="",
        integration_chat_agent_naming_snippet="",
        output_class="OutputData",
    )


@pytest.fixture
def litellm_integration():
    return Integration(
        integration_partner=IntegrationPartner.LITELLM,
        programming_language=ProgrammingLanguage.PYTHON,
        completion_client="litellm.completion",
        completion_client_structured_output="litellm.completion",
        default_for_language=False,
        logo_url="",
        landing_page_snippet="",
        slug=IntegrationKind.LITELLM_PYTHON,
        display_name="LiteLLM Python",
        documentation_filepaths=[],
        integration_chat_initial_snippet="",
        integration_chat_agent_naming_snippet="",
        output_class="OutputData",
    )


@pytest.fixture
def template_service():
    return IntegrationTemplateService()


@pytest.fixture
def sample_schemas():
    """Sample input and output schemas for testing"""
    input_schema = {
        "type": "object",
        "properties": {
            "user_text": {
                "type": "string",
                "description": "Text containing user information",
            },
            "extract_email": {
                "type": "boolean",
                "description": "Whether to extract email",
            },
        },
        "required": ["user_text"],
    }

    output_schema = {
        "type": "object",
        "title": "UserInfo",
        "properties": {
            "name": {"type": "string", "description": "The user's full name"},
            "age": {"type": "integer", "description": "The user's age"},
            "email": {"type": "string", "description": "The user's email address"},
            "status": {
                "type": "string",
                "enum": ["active", "inactive"],
                "description": "The user's status",
            },
        },
        "required": ["name", "age"],
    }

    return input_schema, output_schema


@pytest.fixture
def sample_input_schema():
    """Sample input schema for testing"""
    return {
        "type": "object",
        "properties": {
            "user_text": {
                "type": "string",
                "description": "Text containing user information",
            },
            "extract_email": {
                "type": "boolean",
                "description": "Whether to extract email",
            },
        },
        "required": ["user_text"],
    }


@pytest.fixture
def sample_output_schema():
    """Sample output schema for testing"""
    return {
        "type": "object",
        "title": "UserInfo",
        "properties": {
            "name": {"type": "string", "description": "The user's full name"},
            "age": {"type": "integer", "description": "The user's age"},
            "email": {"type": "string", "description": "The user's email address"},
            "status": {
                "type": "string",
                "enum": ["active", "inactive"],
                "description": "The user's status",
            },
        },
        "required": ["name", "age"],
    }


@pytest.fixture
def sample_tools():
    """Sample tools for testing"""

    weather_tool = Tool(
        name="get_weather",
        description="Get the current weather for a given location",
        input_schema={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "The temperature unit",
                    "default": "fahrenheit",
                },
            },
            "required": ["location"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "temperature": {"type": "number"},
                "condition": {"type": "string"},
                "humidity": {"type": "number"},
            },
        },
    )

    # Also include a hosted tool
    return [weather_tool, ToolKind.WEB_SEARCH_GOOGLE]


class TestIntegrationTemplateService:
    """Test the integration template service with all supported integrations"""

    @pytest.mark.asyncio
    async def test_openai_python_basic_generation(
        self,
        template_service: IntegrationTemplateService,
        openai_python_integration: Integration,
    ) -> None:
        """Test basic OpenAI Python SDK code generation"""
        code = await template_service.generate_code(
            integration=openai_python_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
        )

        assert "```python" in code
        assert "import openai" in code
        assert "client = openai.OpenAI(" in code
        assert 'model="test-agent/gpt-4o"' in code
        assert "chat.completions.create" in code
        assert "response.choices[0].message.content" in code

    @pytest.mark.asyncio
    async def test_openai_ts_basic_generation(
        self,
        template_service: IntegrationTemplateService,
        openai_ts_integration: Integration,
    ) -> None:
        """Test basic OpenAI TypeScript SDK code generation"""
        code = await template_service.generate_code(
            integration=openai_ts_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
        )

        assert "```typescript" in code
        assert "import OpenAI from 'openai';" in code
        assert "const client = new OpenAI({" in code
        assert 'model: "test-agent/gpt-4o"' in code
        assert "await client.chat.completions.create" in code
        assert "response.choices[0].message.content" in code

    @pytest.mark.asyncio
    async def test_instructor_basic_generation(
        self,
        template_service: IntegrationTemplateService,
        instructor_integration: Integration,
    ) -> None:
        """Test basic Instructor Python code generation"""
        code = await template_service.generate_code(
            integration=instructor_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
        )

        assert "```python" in code
        assert "import instructor" in code
        assert "from openai import OpenAI" in code
        assert "instructor.from_openai(" in code
        assert "mode=instructor.Mode.OPENROUTER_STRUCTURED_OUTPUTS" in code
        assert 'model="test-agent/gpt-4o"' in code

    @pytest.mark.asyncio
    async def test_curl_basic_generation(
        self,
        template_service: IntegrationTemplateService,
        curl_integration: Integration,
    ) -> None:
        """Test basic curl code generation"""
        code = await template_service.generate_code(
            integration=curl_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
        )

        assert "```bash" in code
        assert "curl -X POST https://run.workflowai.com/v1/chat/completions" in code
        assert "Authorization: Bearer $WORKFLOWAI_API_KEY" in code
        assert '"model": "test-agent/gpt-4o"' in code
        assert '"messages":' in code

    @pytest.mark.asyncio
    async def test_openai_python_structured_output(
        self,
        template_service: IntegrationTemplateService,
        openai_python_integration: Integration,
        sample_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ) -> None:
        """Test OpenAI Python SDK with structured output"""
        _, output_schema = sample_schemas
        code = await template_service.generate_code(
            integration=openai_python_integration,
            agent_id="user-extractor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Extract user info")])],
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        assert "```python" in code
        # Enhanced code generation uses proper Enum classes instead of Literal
        assert "from pydantic import BaseModel, Field" in code or "from enum import Enum" in code
        assert "class UserInfo(BaseModel):" in code
        assert "name: str = Field(description=" in code
        assert "age: int = Field(description=" in code
        # Status can be either Literal or Enum (enhanced version uses Enum)
        assert "status: Literal" in code or "status: Optional[Status]" in code
        assert "beta.chat.completions.parse" in code
        assert "response_format=UserInfo" in code
        assert "parsed_output: UserInfo = response.choices[0].message.parsed" in code

    @pytest.mark.asyncio
    async def test_openai_ts_structured_output(
        self,
        template_service: IntegrationTemplateService,
        openai_ts_integration: Integration,
        sample_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ) -> None:
        """Test OpenAI TypeScript SDK with structured output"""
        _, output_schema = sample_schemas
        code = await template_service.generate_code(
            integration=openai_ts_integration,
            agent_id="user-extractor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Extract user info")])],
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        assert "```typescript" in code
        assert 'import { zodResponseFormat } from "openai/helpers/zod";' in code
        assert "import { z } from 'zod';" in code
        assert "const UserInfoSchema = z.object({" in code
        assert "name: z.string().describe(" in code
        assert "age: z.number().int().describe(" in code
        assert 'status: z.enum(["active", "inactive"])' in code
        assert "beta.chat.completions.parse" in code
        assert "zodResponseFormat(UserInfoSchema," in code
        assert "const result: z.infer<typeof UserInfoSchema>" in code

    @pytest.mark.asyncio
    async def test_instructor_structured_output(
        self,
        template_service: IntegrationTemplateService,
        instructor_integration: Integration,
        sample_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ) -> None:
        """Test Instructor with structured output (response_model)"""
        _, output_schema = sample_schemas
        code = await template_service.generate_code(
            integration=instructor_integration,
            agent_id="user-extractor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Extract user info")])],
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        assert "```python" in code
        assert "class UserInfo(BaseModel):" in code
        assert "response_model=UserInfo" in code
        assert "client.chat.completions.create" in code  # Instructor always uses create
        assert "print(response)" in code  # Direct response, already parsed

    @pytest.mark.asyncio
    async def test_curl_structured_output(
        self,
        template_service: IntegrationTemplateService,
        curl_integration: Integration,
        sample_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ) -> None:
        """Test curl with structured output (JSON schema)"""
        _, output_schema = sample_schemas
        code = await template_service.generate_code(
            integration=curl_integration,
            agent_id="user-extractor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Extract user info")])],
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        assert "```bash" in code
        assert '"response_format":' in code
        assert '"type": "json_schema"' in code
        assert '"name": "UserInfo"' in code
        assert '"schema":' in code

    @pytest.mark.asyncio
    async def test_input_variables_python(
        self,
        template_service: IntegrationTemplateService,
        openai_python_integration: Integration,
        sample_input_schema: Dict[str, Any],
    ) -> None:
        """Test input variables with Python integrations"""
        code = await template_service.generate_code(
            integration=openai_python_integration,
            agent_id="text-processor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Process: {{user_text}}")])],
            is_using_instruction_variables=True,
            input_schema=sample_input_schema,
        )

        assert "```python" in code
        assert "extra_body={" in code
        assert '"input":' in code
        assert '"user_text": "example_user_text"' in code
        assert '"extract_email": True' in code

    @pytest.mark.asyncio
    async def test_input_variables_typescript(
        self,
        template_service: IntegrationTemplateService,
        openai_ts_integration: Integration,
        sample_input_schema: Dict[str, Any],
    ) -> None:
        """Test input variables with TypeScript integration"""
        code = await template_service.generate_code(
            integration=openai_ts_integration,
            agent_id="text-processor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Process: {{user_text}}")])],
            is_using_instruction_variables=True,
            input_schema=sample_input_schema,
        )

        assert "```typescript" in code
        assert "// @ts-expect-error input is specific to the WorkflowAI implementation" in code
        assert "input:" in code
        assert '"user_text": "example_user_text"' in code

    @pytest.mark.asyncio
    async def test_input_variables_curl(
        self,
        template_service: IntegrationTemplateService,
        curl_integration: Integration,
        sample_input_schema: Dict[str, Any],
    ) -> None:
        """Test input variables with curl"""
        code = await template_service.generate_code(
            integration=curl_integration,
            agent_id="text-processor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Process: {{user_text}}")])],
            is_using_instruction_variables=True,
            input_schema=sample_input_schema,
        )

        assert "```bash" in code
        assert '"input": {' in code
        assert '"user_text": "example_user_text"' in code

    @pytest.mark.asyncio
    async def test_deployment_environment(
        self,
        template_service: IntegrationTemplateService,
        openai_python_integration: Integration,
    ) -> None:
        """Test deployment environment handling"""
        code = await template_service.generate_code(
            integration=openai_python_integration,
            agent_id="my-agent",
            agent_schema_id=5,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
            version_deployment_environment="production",
        )

        assert "```python" in code
        assert 'model="my-agent/#5/production"' in code
        assert "messages=[]" in code  # Empty for deployments

    @pytest.mark.asyncio
    async def test_full_featured_generation(
        self,
        template_service: IntegrationTemplateService,
        openai_python_integration: Integration,
        sample_input_schema: Dict[str, Any],
        sample_output_schema: Dict[str, Any],
    ) -> None:
        """Test generation with all features enabled"""
        code = await template_service.generate_code(
            integration=openai_python_integration,
            agent_id="full-agent",
            agent_schema_id=3,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Process {{user_text}}")])],
            is_using_instruction_variables=True,
            input_schema=sample_input_schema,
            is_using_structured_generation=True,
            output_schema=sample_output_schema,
        )

        assert "```python" in code
        # Enhanced code generation may use Enum classes instead of Literal
        assert "from pydantic import BaseModel, Field" in code or "from enum import Enum" in code
        assert "class UserInfo(BaseModel):" in code
        assert "beta.chat.completions.parse" in code
        assert "response_format=UserInfo" in code
        assert "extra_body={" in code
        assert "parsed_output: UserInfo" in code

    @pytest.mark.asyncio
    async def test_supports_integration(self, template_service: IntegrationTemplateService) -> None:
        """Test integration support detection"""
        openai_python = Integration(
            slug=IntegrationKind.OPENAI_SDK_PYTHON,
            integration_partner=IntegrationPartner.OPENAI_SDK,
            programming_language=ProgrammingLanguage.PYTHON,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=True,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        openai_ts = Integration(
            slug=IntegrationKind.OPENAI_SDK_TS,
            integration_partner=IntegrationPartner.OPENAI_SDK_TS,
            programming_language=ProgrammingLanguage.TYPESCRIPT,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=True,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        instructor = Integration(
            slug=IntegrationKind.INSTRUCTOR_PYTHON,
            integration_partner=IntegrationPartner.INSTRUCTOR,
            programming_language=ProgrammingLanguage.PYTHON,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=False,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        curl = Integration(
            slug=IntegrationKind.CURL,
            integration_partner=IntegrationPartner.CURL,
            programming_language=ProgrammingLanguage.CURL,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=False,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        dspy = Integration(
            slug=IntegrationKind.DSPY_PYTHON,
            integration_partner=IntegrationPartner.DSPY,
            programming_language=ProgrammingLanguage.PYTHON,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=False,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        langchain = Integration(
            slug=IntegrationKind.LANGCHAIN_PYTHON,
            integration_partner=IntegrationPartner.LANGCHAIN,
            programming_language=ProgrammingLanguage.PYTHON,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=False,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        litellm = Integration(
            slug=IntegrationKind.LITELLM_PYTHON,
            integration_partner=IntegrationPartner.LITELLM,
            programming_language=ProgrammingLanguage.PYTHON,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=False,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        # Test all supported integrations
        assert template_service.supports_integration(openai_python)
        assert template_service.supports_integration(openai_ts)
        assert template_service.supports_integration(instructor)
        assert template_service.supports_integration(curl)
        assert template_service.supports_integration(dspy)
        assert template_service.supports_integration(langchain)
        assert template_service.supports_integration(litellm)

    @pytest.mark.asyncio
    async def test_whitespace_handling(
        self,
        template_service: IntegrationTemplateService,
        openai_python_integration: Integration,
    ) -> None:
        """Test that generated code has proper whitespace formatting"""
        code = await template_service.generate_code(
            integration=openai_python_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
        )

        # Split into lines and check for excessive empty lines
        lines = code.split("\n")
        empty_line_count = 0
        max_consecutive_empty = 0

        for line in lines:
            if line.strip() == "":
                empty_line_count += 1
                max_consecutive_empty = max(max_consecutive_empty, empty_line_count)
            else:
                empty_line_count = 0

        # Should not have more than 2 consecutive empty lines
        assert max_consecutive_empty <= 2

        # Should not have excessive empty lines (>50% of total lines)
        total_lines = len(lines)
        total_empty_lines = sum(1 for line in lines if line.strip() == "")
        assert total_empty_lines < total_lines * 0.5

    @pytest.mark.asyncio
    async def test_dspy_basic_generation(
        self,
        template_service: IntegrationTemplateService,
        dspy_integration: Integration,
    ) -> None:
        """Test basic DSPy code generation"""
        code = await template_service.generate_code(
            integration=dspy_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
        )

        assert "```python" in code
        assert "import dspy" in code
        assert "lm = dspy.LM(" in code
        assert '"openai/test-agent/gpt-4o"' in code
        assert "dspy.configure(lm=lm)" in code

    @pytest.mark.asyncio
    async def test_langchain_basic_generation(
        self,
        template_service: IntegrationTemplateService,
        langchain_integration: Integration,
    ) -> None:
        """Test basic LangChain code generation"""
        code = await template_service.generate_code(
            integration=langchain_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
        )

        assert "```python" in code
        assert "from langchain_openai import ChatOpenAI" in code
        assert "from pydantic import SecretStr" in code
        assert "llm = ChatOpenAI(" in code
        assert 'model="test-agent/gpt-4o"' in code

    @pytest.mark.asyncio
    async def test_litellm_basic_generation(
        self,
        template_service: IntegrationTemplateService,
        litellm_integration: Integration,
    ) -> None:
        """Test basic LiteLLM code generation"""
        code = await template_service.generate_code(
            integration=litellm_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
        )

        assert "```python" in code
        assert "import litellm" in code
        assert "litellm.api_base" in code
        assert "litellm.completion(" in code
        assert 'model="openai/test-agent/gpt-4o"' in code

    @pytest.mark.asyncio
    async def test_dspy_structured_output(
        self,
        template_service: IntegrationTemplateService,
        dspy_integration: Integration,
        sample_output_schema: Dict[str, Any],
    ) -> None:
        """Test DSPy with structured output (Signature)"""
        code = await template_service.generate_code(
            integration=dspy_integration,
            agent_id="user-extractor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Extract user info")])],
            is_using_structured_generation=True,
            output_schema=sample_output_schema,
        )

        assert "```python" in code
        assert "from typing import Literal" in code
        assert "class UserInfo(dspy.Signature):" in code
        assert "dspy.OutputField()" in code
        assert "predict = dspy.Predict(UserInfo)" in code
        assert "result = predict(" in code

    @pytest.mark.asyncio
    async def test_langchain_structured_output(
        self,
        template_service: IntegrationTemplateService,
        langchain_integration: Integration,
        sample_output_schema: Dict[str, Any],
    ) -> None:
        """Test LangChain with structured output (.with_structured_output)"""
        code = await template_service.generate_code(
            integration=langchain_integration,
            agent_id="user-extractor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Extract user info")])],
            is_using_structured_generation=True,
            output_schema=sample_output_schema,
        )

        assert "```python" in code
        assert "class UserInfo(BaseModel):" in code
        assert ".with_structured_output(UserInfo)" in code
        assert "result = llm.invoke(" in code
        assert "print(result)" in code  # Direct structured output

    @pytest.mark.asyncio
    async def test_langchain_message_format(
        self,
        template_service: IntegrationTemplateService,
        langchain_integration: Integration,
    ) -> None:
        """Test that LangChain uses proper message classes (HumanMessage, SystemMessage) instead of raw dictionaries"""
        code = await template_service.generate_code(
            integration=langchain_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[
                Message(role="system", content=[MessageContent(text="You are a helpful assistant.")]),
                Message(role="user", content=[MessageContent(text="Analyze the sentiment of: {{text}}")]),
            ],
        )

        assert "```python" in code
        # Should import proper message classes
        assert "from langchain_core.messages import AIMessage, HumanMessage, SystemMessage" in code
        # Should use proper message classes instead of raw dictionaries
        assert "SystemMessage(content=" in code
        assert "HumanMessage(content=" in code
        # Should NOT use raw dictionary format
        assert '"role": "system"' not in code
        assert '"role": "user"' not in code
        # Check that messages are formatted as a proper Python list
        assert "messages = [" in code

    @pytest.mark.asyncio
    async def test_litellm_structured_output(
        self,
        template_service: IntegrationTemplateService,
        litellm_integration: Integration,
        sample_output_schema: Dict[str, Any],
    ) -> None:
        """Test LiteLLM with structured output (response_format)"""
        code = await template_service.generate_code(
            integration=litellm_integration,
            agent_id="user-extractor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Extract user info")])],
            is_using_structured_generation=True,
            output_schema=sample_output_schema,
        )

        assert "```python" in code
        assert "litellm.enable_json_schema_validation = True" in code
        assert "class UserInfo(BaseModel):" in code
        assert "response_format=UserInfo" in code
        assert "UserInfo.model_validate_json(" in code

    @pytest.mark.asyncio
    async def test_custom_base_url(self, dspy_integration: Integration) -> None:
        """Test configurable base URL"""
        custom_base_url = "http://localhost:8000/v1"
        template_service = IntegrationTemplateService(base_url=custom_base_url)

        code = await template_service.generate_code(
            integration=dspy_integration,
            agent_id="test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
        )

        assert custom_base_url in code
        assert "http://localhost:8000/v1" in code

    @pytest.mark.asyncio
    async def test_dspy_input_variables(
        self,
        template_service: IntegrationTemplateService,
        dspy_integration: Integration,
        sample_input_schema: Dict[str, Any],
    ) -> None:
        """Test DSPy with input variables"""
        code = await template_service.generate_code(
            integration=dspy_integration,
            agent_id="text-processor",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Process: {{user_text}}")])],
            is_using_instruction_variables=True,
            input_schema=sample_input_schema,
        )

        assert "```python" in code
        assert "predict = dspy.Predict(" in code
        assert "result = predict(" in code

    @pytest.mark.asyncio
    async def test_tools_support_openai_python(
        self,
        template_service: IntegrationTemplateService,
        openai_python_integration: Integration,
        sample_tools: list[Tool | ToolKind],
    ) -> None:
        """Test tools support with OpenAI Python SDK"""
        code = await template_service.generate_code(
            integration=openai_python_integration,
            agent_id="weather-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="What's the weather like?")])],
            enabled_tools=sample_tools,
        )

        assert "```python" in code
        # Check that tools are defined
        assert "tools = [" in code
        assert '"get_weather"' in code
        assert '"Get the current weather for a given location"' in code
        assert '"search-google"' in code
        # Check that tools parameter is passed
        assert "tools=tools" in code
        # Check tool call handling in output
        assert "tool_calls" in code
        assert "tool_call.function.name" in code

    @pytest.mark.asyncio
    async def test_tools_support_openai_ts(
        self,
        template_service: IntegrationTemplateService,
        openai_ts_integration: Integration,
        sample_tools: list[Tool | ToolKind],
    ) -> None:
        """Test tools support with OpenAI TypeScript SDK"""
        code = await template_service.generate_code(
            integration=openai_ts_integration,
            agent_id="weather-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="What's the weather like?")])],
            enabled_tools=sample_tools,
        )

        assert "```typescript" in code
        # Check that tools are defined
        assert "const tools = [" in code
        assert '"get_weather"' in code
        assert '"Get the current weather for a given location"' in code
        # Check that tools parameter is passed
        assert "tools: tools" in code
        # Check tool call handling in output
        assert "tool_calls" in code
        assert "toolCall.function.name" in code

    @pytest.mark.asyncio
    async def test_tools_support_curl(
        self,
        template_service: IntegrationTemplateService,
        curl_integration: Integration,
        sample_tools: list[Tool | ToolKind],
    ) -> None:
        """Test tools support with curl"""
        code = await template_service.generate_code(
            integration=curl_integration,
            agent_id="weather-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="What's the weather like?")])],
            enabled_tools=sample_tools,
        )

        assert "```bash" in code
        # Check that tools are included in the request
        assert '"tools":' in code
        assert '"get_weather"' in code
        assert '"Get the current weather for a given location"' in code

    @pytest.mark.asyncio
    async def test_tools_support_langchain(
        self,
        template_service: IntegrationTemplateService,
        langchain_integration: Integration,
        sample_tools: list[Tool | ToolKind],
    ) -> None:
        """Test tools support with LangChain"""
        code = await template_service.generate_code(
            integration=langchain_integration,
            agent_id="weather-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="What's the weather like?")])],
            enabled_tools=sample_tools,
        )

        assert "```python" in code
        # Check that tools are defined
        assert "tools = [" in code
        assert '"get_weather"' in code
        # Check that tools are bound to LLM
        assert "bind_tools(tools)" in code
        assert "llm_with_tools" in code
        # Check tool call handling
        assert "tool_calls" in code

    @pytest.mark.asyncio
    async def test_tools_with_structured_output(
        self,
        template_service: IntegrationTemplateService,
        openai_python_integration: Integration,
        sample_schemas: tuple[Dict[str, Any], Dict[str, Any]],
        sample_tools: list[Tool | ToolKind],
    ) -> None:
        """Test that tools and structured output can work together"""
        _, output_schema = sample_schemas

        code = await template_service.generate_code(
            integration=openai_python_integration,
            agent_id="weather-user-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Get weather and extract user info")])],
            is_using_structured_generation=True,
            output_schema=output_schema,
            enabled_tools=sample_tools,
        )

        assert "```python" in code
        # Check structured output
        assert "class UserInfo(BaseModel):" in code
        assert "beta.chat.completions.parse" in code
        assert "response_format=UserInfo" in code
        # Check tools
        assert "tools = [" in code
        assert '"get_weather"' in code
        assert "tools=tools" in code
        # Check that structured output takes precedence in output handling
        assert "parsed_output: UserInfo" in code

    @pytest.mark.asyncio
    async def test_extended_supports_integration(self, template_service: IntegrationTemplateService) -> None:
        """Test integration support detection for all new integrations"""
        dspy = Integration(
            slug=IntegrationKind.DSPY_PYTHON,
            integration_partner=IntegrationPartner.DSPY,
            programming_language=ProgrammingLanguage.PYTHON,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=False,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        langchain = Integration(
            slug=IntegrationKind.LANGCHAIN_PYTHON,
            integration_partner=IntegrationPartner.LANGCHAIN,
            programming_language=ProgrammingLanguage.PYTHON,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=False,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        litellm = Integration(
            slug=IntegrationKind.LITELLM_PYTHON,
            integration_partner=IntegrationPartner.LITELLM,
            programming_language=ProgrammingLanguage.PYTHON,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=False,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )

        assert template_service.supports_integration(dspy)
        assert template_service.supports_integration(langchain)
        assert template_service.supports_integration(litellm)

    @pytest.mark.asyncio
    async def test_dspy_full_featured(
        self,
        template_service: IntegrationTemplateService,
        dspy_integration: Integration,
        sample_input_schema: Dict[str, Any],
        sample_output_schema: Dict[str, Any],
    ) -> None:
        """Test DSPy with all features (structured output + input variables)"""
        code = await template_service.generate_code(
            integration=dspy_integration,
            agent_id="advanced-agent",
            agent_schema_id=3,
            model_used="gpt-4o",
            version_messages=[Message(role="user", content=[MessageContent(text="Process {{user_text}}")])],
            is_using_instruction_variables=True,
            input_schema=sample_input_schema,
            is_using_structured_generation=True,
            output_schema=sample_output_schema,
        )

        assert "```python" in code
        assert "from typing import Literal" in code
        assert "class UserInfo(dspy.Signature):" in code
        assert "user_text: str = dspy.InputField()" in code
        assert "status: Literal" in code
        assert "predict = dspy.Predict(UserInfo)" in code
        assert 'user_text="example_user_text"' in code
        assert "extract_email=True" in code

    @pytest.mark.asyncio
    async def test_deployment_environments_all_integrations(self, template_service: IntegrationTemplateService) -> None:
        """Test deployment environment handling across all integrations"""
        integrations = [
            ("DSPy", self._create_test_integration(IntegrationKind.DSPY_PYTHON)),
            ("LangChain", self._create_test_integration(IntegrationKind.LANGCHAIN_PYTHON)),
            ("LiteLLM", self._create_test_integration(IntegrationKind.LITELLM_PYTHON)),
        ]

        for name, integration in integrations:
            code = await template_service.generate_code(
                integration=integration,
                agent_id="my-agent",
                agent_schema_id=5,
                model_used="gpt-4o",
                version_messages=[Message(role="user", content=[MessageContent(text="Hello")])],
                version_deployment_environment="production",
            )

            # Should reference deployment, not direct model
            if name == "DSPy":
                assert '"openai/my-agent/#5/production"' in code
            elif name == "LangChain":
                assert 'model="my-agent/#5/production"' in code
            elif name == "LiteLLM":
                assert '"openai/my-agent/#5/production"' in code

    def _create_test_integration(self, integration_kind: IntegrationKind) -> Integration:
        """Helper to create test integrations"""
        partner_map = {
            IntegrationKind.DSPY_PYTHON: IntegrationPartner.DSPY,
            IntegrationKind.LANGCHAIN_PYTHON: IntegrationPartner.LANGCHAIN,
            IntegrationKind.LITELLM_PYTHON: IntegrationPartner.LITELLM,
        }

        return Integration(
            slug=integration_kind,
            integration_partner=partner_map[integration_kind],
            programming_language=ProgrammingLanguage.PYTHON,
            completion_client="",
            completion_client_structured_output="",
            default_for_language=False,
            logo_url="",
            landing_page_snippet="",
            display_name="",
            documentation_filepaths=[],
            integration_chat_initial_snippet="",
            integration_chat_agent_naming_snippet="",
            output_class="",
        )
