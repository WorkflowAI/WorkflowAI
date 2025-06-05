"""
World-Class Integration Tests: Real API Code Execution

These tests actually execute the generated Python code with REAL API calls.
This is the ultimate validation of our templating system.

If the code runs successfully and produces real responses, our templates are perfect!
"""

import logging
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, NamedTuple, Optional

import httpx
import pytest

from core.domain.integration.integration_domain import (
    IntegrationKind,
    ProgrammingLanguage,
)
from core.domain.integration.integration_mapping import OFFICIAL_INTEGRATIONS, get_integration_by_kind
from core.domain.message import Message, MessageContent
from core.domain.tool import Tool
from core.services.integration_template_service import IntegrationTemplateService
from core.tools import ToolKind

_logger = logging.getLogger(__name__)

WORKFLOWAI_API_URL = "http://localhost:8000/v1"
WORKFLOWAI_API_KEY = ""


def extract_python_code(generated_code: str) -> str:
    """Extract Python code from markdown code blocks"""
    code_match = re.search(r"```python\n(.*?)\n```", generated_code, re.DOTALL)
    if code_match:
        return code_match.group(1)
    raise ValueError("No Python code block found in generated code")


async def check_server_health() -> bool:
    """Check if WorkflowAI server is running"""
    base_url = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
    health_url = base_url.replace("/v1", "/health")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url, follow_redirects=True)
            return response.status_code == 200
    except Exception:
        return False


def execute_python_code(code: str, env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Execute Python code in a controlled environment and capture results

    Returns:
        Dict containing execution results, any exceptions, and captured output
    """
    if env_vars is None:
        env_vars = {}

    # Set up environment
    env = os.environ.copy()
    env.update(env_vars)
    env.update(
        {
            "WORKFLOWAI_API_URL": WORKFLOWAI_API_URL,
            "WORKFLOWAI_API_KEY": WORKFLOWAI_API_KEY,
        },
    )

    # Create a temporary file with the code
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_file = f.name

    try:
        # Execute the code as a subprocess to avoid polluting current namespace
        result = subprocess.run(
            [sys.executable, temp_file],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Execution timed out after 30 seconds",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Execution failed: {str(e)}",
            "returncode": -1,
        }
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_file)
        except Exception:
            pass


@pytest.fixture
def user_info_extraction_schemas():
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


@pytest.fixture(scope="function")
def weather_info_schema():
    input_schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The message to analyze"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "temperature": {
                "type": ["number", "null"],
                "description": "The temperature in Fahrenheit",
                "default": None,
            },
            "condition": {"type": ["string", "null"], "description": "The weather condition", "default": None},
            "humidity": {"type": ["number", "null"], "description": "The humidity percentage", "default": None},
        },
    }

    return input_schema, output_schema


@pytest.fixture
def template_service():
    """Template service using environment-based configuration"""
    base_url = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
    return IntegrationTemplateService(base_url=base_url)


@pytest.fixture
def sample_weather_tool() -> Tool:
    """Sample weather tool for testing"""
    return Tool(
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


@pytest.fixture
def sample_tools_list(sample_weather_tool: Tool) -> list[Tool | ToolKind]:
    """Sample tools list including weather tool and hosted tool"""
    return [sample_weather_tool, ToolKind.WEB_SEARCH_GOOGLE]


@pytest.fixture
def nested_data_extraction_schemas():
    """Complex nested schema for testing enhanced nested object handling"""
    input_schema = {
        "type": "object",
        "properties": {
            "document_text": {
                "type": "string",
                "description": "Text containing complex nested data",
            },
            "extraction_mode": {
                "type": "string",
                "enum": ["full", "partial"],
                "description": "Whether to extract all data or partial",
            },
        },
        "required": ["document_text"],
    }

    output_schema = {
        "type": "object",
        "title": "ExtractedData",
        "properties": {
            "person": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name"},
                    "age": {"type": "integer", "description": "Age in years"},
                    "contact": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "description": "Email address"},
                            "phone": {"type": "string", "description": "Phone number"},
                            "address": {
                                "type": "object",
                                "properties": {
                                    "street": {"type": "string"},
                                    "city": {"type": "string"},
                                    "country": {"type": "string"},
                                    "postal_code": {"type": "string"},
                                },
                                "required": ["city", "country"],
                            },
                        },
                        "required": ["email"],
                    },
                },
                "required": ["name", "contact"],
            },
            "company": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Company name"},
                    "industry": {"type": "string", "description": "Industry sector"},
                    "employees": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "role": {"type": "string"},
                                "department": {"type": "string"},
                                "skills": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["name", "role"],
                        },
                    },
                    "locations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "office_name": {"type": "string"},
                                "address": {
                                    "type": "object",
                                    "properties": {
                                        "street": {"type": "string"},
                                        "city": {"type": "string"},
                                        "country": {"type": "string"},
                                    },
                                    "required": ["city", "country"],
                                },
                                "is_headquarters": {"type": "boolean"},
                            },
                            "required": ["office_name", "address"],
                        },
                    },
                },
                "required": ["name"],
            },
            "metadata": {
                "type": "object",
                "properties": {
                    "extraction_timestamp": {"type": "string", "format": "date-time"},
                    "confidence_scores": {
                        "type": "object",
                        "properties": {
                            "person_data": {"type": "number", "minimum": 0, "maximum": 1},
                            "company_data": {"type": "number", "minimum": 0, "maximum": 1},
                            "overall": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["overall"],
                    },
                    "processing_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["extraction_timestamp", "confidence_scores"],
            },
        },
        "required": ["person", "metadata"],
    }

    return input_schema, output_schema


class Scenario(NamedTuple):
    agent_name: str
    model_name: str
    messages: list[Message]
    is_structured_output: bool
    is_using_instruction_variables: bool
    version_deployment_environment: str | None = None


class TestRealCodeExecution:
    """World-class tests that execute generated Python code with REAL API calls"""

    # Define integration test parameters
    # Basic integrations that work without structured output
    BASIC_INTEGRATIONS = [
        (IntegrationKind.OPENAI_SDK_PYTHON, "OpenAI SDK"),
        (IntegrationKind.LANGCHAIN_PYTHON, "LangChain"),
        (IntegrationKind.LITELLM_PYTHON, "LiteLLM"),
    ]

    STRUCTURED_INTEGRATIONS = [
        (
            IntegrationKind.OPENAI_SDK_PYTHON,
            "OpenAI SDK",
            "Create a sample user with name John Doe, age 30, email john@example.com, status active",
        ),
        (
            IntegrationKind.INSTRUCTOR_PYTHON,
            "Instructor",
            "Extract: Jane Smith, 25 years old, jane@test.com, active user",
        ),
        (IntegrationKind.DSPY_PYTHON, "DSPy", "Process user data: {{user_text}}"),
        (IntegrationKind.LANGCHAIN_PYTHON, "LangChain", "Create user data: Bob Wilson, 35, bob@example.com, active"),
        (IntegrationKind.LITELLM_PYTHON, "LiteLLM", "Generate: Alice Brown, 28, alice@test.com, active"),
    ]

    # Curl test scenarios based on documentation examples
    CURL_SCENARIOS = [
        Scenario(
            "basic",
            "gpt-4o",
            [
                Message(
                    role="system",
                    content=[MessageContent(text="You are a helpful assistant.")],
                ),
                Message(role="user", content=[MessageContent(text="Hello!")]),
            ],
            False,
            False,
            None,
        ),
        Scenario(
            "agent_identification",
            "code-gen-test-my-agent/gpt-4o",
            [
                Message(
                    role="system",
                    content=[MessageContent(text="You are a helpful assistant.")],
                ),
                Message(role="user", content=[MessageContent(text="What is the capital of France?")]),
            ],
            False,
            False,
            None,
        ),
        Scenario(
            "different_model",
            "code-gen-test-my-agent/gemini-2.0-flash-001",
            [
                Message(
                    role="system",
                    content=[MessageContent(text="You are a helpful assistant.")],
                ),
                Message(role="user", content=[MessageContent(text="What is the capital of France?")]),
            ],
            False,
            False,
            None,
        ),
        Scenario(
            "input_variables",
            "code-gen-test-sentiment-analyzer/gemini-2.0-flash-001",
            [
                Message(
                    role="system",
                    content=[MessageContent(text="You are a sentiment analysis expert.")],
                ),
                Message(role="user", content=[MessageContent(text="Analyze: {{text}}")]),
            ],
            True,
            False,
            None,
        ),
        Scenario(
            "structured_output",
            "code-gen-test-sentiment-analyzer/gemini-2.0-flash-001",
            [
                Message(
                    role="system",
                    content=[MessageContent(text="You are a sentiment analysis expert.")],
                ),
                Message(role="user", content=[MessageContent(text="Analyze: {{text}}")]),
            ],
            True,
            True,
            None,
        ),
        Scenario(
            "deployment",
            "code-gen-test-sentiment-analyzer/#3/production",
            [],
            True,
            True,
            "production",
        ),
    ]

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.parametrize("integration_kind,display_name", BASIC_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_basic_execution(
        self,
        integration_kind: IntegrationKind,
        display_name: str,
        template_service: IntegrationTemplateService,
    ):
        """Test basic execution of all integrations with real API calls"""
        integration = get_integration_by_kind(integration_kind)

        # Generate the code
        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-integration-test",
            agent_schema_id=1,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="Say hello and tell me you are working correctly")],
                ),
            ],
        )

        # Extract and execute Python code
        python_code = extract_python_code(code)
        result = execute_python_code(python_code)

        # Verify execution was successful
        if not result["success"]:
            _logger.error("STDOUT: %s", result["stdout"])
            _logger.error("STDERR: %s", result["stderr"])
            pytest.fail(f"{display_name} execution failed: {result['stderr']}")

        # Verify there was output (response from API)
        assert result["stdout"].strip(), f"No output from {display_name} execution"
        _logger.info("✅ %s Basic Execution Output: %s...", display_name, result["stdout"][:100])

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.parametrize("integration_kind,display_name,test_message", STRUCTURED_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_structured_output_execution(
        self,
        integration_kind: IntegrationKind,
        display_name: str,
        test_message: str,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test structured output execution of all integrations with real API calls"""
        integration = get_integration_by_kind(integration_kind)
        input_schema, output_schema = user_info_extraction_schemas

        # DSPy uses input variables, others don't for this test
        use_input_vars = integration_kind == IntegrationKind.DSPY_PYTHON

        code = await template_service.generate_code(
            integration=integration,
            agent_id=f"code-gen-test-{display_name.lower()}-structured-test",
            agent_schema_id=1,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text=test_message)],
                ),
            ],
            is_using_instruction_variables=use_input_vars,
            input_schema=input_schema if use_input_vars else None,
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        python_code = extract_python_code(code)
        result = execute_python_code(python_code)

        if not result["success"]:
            _logger.error("STDOUT: %s", result["stdout"])
            _logger.error("STDERR: %s", result["stderr"])
            pytest.fail(f"{display_name} structured execution failed: {result['stderr']}")

        output = result["stdout"]
        assert output.strip(), f"No output from {display_name} structured execution"
        _logger.info("✅ %s Structured Output: %s...", display_name, output[:100])

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_all_integrations_syntax_validation(
        self,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test that all generated code has valid Python syntax"""
        input_schema, output_schema = user_info_extraction_schemas

        # Test all Python integrations from the official mapping
        python_integrations = [
            integration
            for integration in OFFICIAL_INTEGRATIONS
            if integration.programming_language == ProgrammingLanguage.PYTHON
        ]

        for integration in python_integrations:
            # Generate code with all features
            code = await template_service.generate_code(
                integration=integration,
                agent_id="code-gen-test-syntax-test",
                agent_schema_id=1,
                model_used="gpt-4o-mini",
                version_messages=[
                    Message(
                        role="user",
                        content=[MessageContent(text="Test {{user_text}}")],
                    ),
                ],
                is_using_instruction_variables=True,
                input_schema=input_schema,
                is_using_structured_generation=True,
                output_schema=output_schema,
            )

            python_code = extract_python_code(code)

            # Validate syntax by compiling (this will raise SyntaxError if invalid)
            try:
                compile(python_code, f"<{integration.display_name}_test>", "exec")
                _logger.info("✅ %s: Syntax valid", integration.display_name)
            except SyntaxError as e:
                pytest.fail(f"Generated {integration.display_name} code has syntax error: {e}\n\nCode:\n{python_code}")

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_environment_variable_configuration(
        self,
        template_service: IntegrationTemplateService,
    ):
        """Test that generated code correctly uses environment variables"""
        integration = get_integration_by_kind(IntegrationKind.OPENAI_SDK_PYTHON)

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-env-test",
            agent_schema_id=1,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="Test")],
                ),
            ],
        )

        python_code = extract_python_code(code)

        # Verify environment variable usage
        assert "WORKFLOWAI_API_KEY" in python_code
        assert "os.environ" in python_code

        # Verify the base URL is correctly configured
        base_url = os.environ.get("WORKFLOWAI_API_URL", "https://run.workflowai.com/v1")
        assert base_url in python_code

        _logger.info("✅ Environment variables correctly configured in generated code")

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_deployment_environment_configuration(
        self,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test deployment environment configuration"""
        integration = get_integration_by_kind(IntegrationKind.OPENAI_SDK_PYTHON)
        input_schema, output_schema = user_info_extraction_schemas

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-deployment-test",
            agent_schema_id=5,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="Process deployment test")],
                ),
            ],
            version_deployment_environment="production",
            is_using_instruction_variables=True,
            input_schema=input_schema,
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        python_code = extract_python_code(code)

        # Verify deployment reference in the code
        assert "code-gen-test-deployment-test/#5/production" in python_code
        _logger.info("✅ Deployment environment correctly configured")

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_input_variables_configuration(
        self,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test input variables configuration"""
        integration = get_integration_by_kind(IntegrationKind.INSTRUCTOR_PYTHON)
        input_schema, _ = user_info_extraction_schemas

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-variables-test",
            agent_schema_id=1,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="Process this text: {{user_text}}")],
                ),
            ],
            is_using_instruction_variables=True,
            input_schema=input_schema,
        )

        python_code = extract_python_code(code)

        # Verify input variables are in the code
        assert 'extra_body={"input":' in python_code
        assert '"user_text": "example_user_text"' in python_code

        _logger.info("✅ Input variables correctly configured")

    # =========================================================================
    # CURL TESTS - Based on Documentation Examples
    # =========================================================================

    def extract_curl_command(self, generated_code: str) -> str:
        """Extract curl command from markdown code blocks"""
        bash_match = re.search(r"```bash\n(.*?)\n```", generated_code, re.DOTALL)
        if bash_match:
            return bash_match.group(1)
        raise ValueError("No bash code block found in generated code")

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.parametrize(
        "scenario,model,messages,use_input_vars,use_structured,deployment_env",
        CURL_SCENARIOS,
    )
    @pytest.mark.asyncio
    async def test_curl_generation(
        self,
        scenario: Scenario,
        model: str,
        messages: list[Message],
        use_input_vars: bool,
        use_structured: bool,
        deployment_env: str | None,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test curl command generation for all documentation scenarios"""
        integration = get_integration_by_kind(IntegrationKind.CURL)
        input_schema, output_schema = user_info_extraction_schemas

        # Determine agent_id and schema_id based on scenario
        if "sentiment" in model:
            agent_id = "code-gen-test-sentiment-analyzer"
            agent_schema_id = 3 if deployment_env else 1
        elif "my-agent" in model:
            agent_id = "code-gen-test-my-agent"
            agent_schema_id = 1
        else:
            agent_id = "code-gen-test-basic-test"
            agent_schema_id = 1

        code = await template_service.generate_code(
            integration=integration,
            agent_id=agent_id,
            agent_schema_id=agent_schema_id,
            model_used=model.split("/")[-1] if "/" in model else model,
            version_messages=messages,
            version_deployment_environment=deployment_env,
            is_using_instruction_variables=use_input_vars,
            input_schema=input_schema if use_input_vars else None,
            is_using_structured_generation=use_structured,
            output_schema=output_schema if use_structured else None,
        )

        curl_command = self.extract_curl_command(code)

        # Validate curl command structure
        assert "curl -X POST" in curl_command
        assert "https://run.workflowai.com/v1/chat/completions" in curl_command
        assert "Authorization: Bearer $WORKFLOWAI_API_KEY" in curl_command
        assert "Content-Type: application/json" in curl_command

        # Scenario-specific validations
        if scenario == "basic":
            assert '"model": "code-gen-test-basic-test/gpt-4o"' in curl_command  # Service prefixes with agent_id
            assert '"You are a helpful assistant."' in curl_command
            assert '"Hello!"' in curl_command

        elif scenario == "agent_identification":
            assert '"model": "code-gen-test-my-agent/gpt-4o"' in curl_command
            assert '"What is the capital of France?"' in curl_command

        elif scenario == "different_model":
            assert '"model": "code-gen-test-my-agent/gemini-2.0-flash-001"' in curl_command

        elif scenario == "input_variables":
            assert '"model": "code-gen-test-sentiment-analyzer/gemini-2.0-flash-001"' in curl_command
            assert '"input":' in curl_command
            # Test actual schema fields that get generated
            assert '"user_text":' in curl_command or '"extract_email":' in curl_command

        elif scenario == "structured_output":
            assert '"response_format":' in curl_command
            assert '"json_schema"' in curl_command
            # Test actual schema that gets generated (UserInfo schema)
            assert '"name"' in curl_command or '"age"' in curl_command

        elif scenario == "deployment":
            assert '"model": "code-gen-test-sentiment-analyzer/#3/production"' in curl_command
            assert '"messages": []' in curl_command

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_curl_syntax_validation(
        self,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test that all generated curl commands have valid syntax"""
        integration = get_integration_by_kind(IntegrationKind.CURL)
        input_schema, output_schema = user_info_extraction_schemas

        for scenario_params in self.CURL_SCENARIOS:
            _, model, messages, use_input_vars, use_structured, deployment_env = scenario_params

            agent_id = "code-gen-test-test-agent"
            agent_schema_id = 1

            code = await template_service.generate_code(
                integration=integration,
                agent_id=agent_id,
                agent_schema_id=agent_schema_id,
                model_used=model.split("/")[-1] if "/" in model else model,
                version_messages=messages,
                version_deployment_environment=deployment_env,
                is_using_instruction_variables=use_input_vars,
                input_schema=input_schema if use_input_vars else None,
                is_using_structured_generation=use_structured,
                output_schema=output_schema if use_structured else None,
            )

            curl_command = self.extract_curl_command(code)

            # Basic syntax checks
            assert curl_command.count("{") == curl_command.count("}")
            assert curl_command.count("[") == curl_command.count("]")
            assert curl_command.count('"') % 2 == 0  # Even number of quotes

            # Must contain essential curl elements
            assert "curl" in curl_command
            assert "-X POST" in curl_command
            assert "-H" in curl_command
            assert "-d" in curl_command

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_curl_documentation_compatibility(
        self,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test that generated curl matches documentation examples structure"""
        integration = get_integration_by_kind(IntegrationKind.CURL)
        input_schema, output_schema = user_info_extraction_schemas

        # Test structured output scenario (matches curl.md structured example)
        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-sentiment-analyzer",
            agent_schema_id=1,
            model_used="gemini-2.0-flash-001",
            version_messages=[
                Message(
                    role="system",
                    content=[MessageContent(text="You are a sentiment analysis expert.")],
                ),
                Message(role="user", content=[MessageContent(text="Analyze: {{text}}")]),
            ],
            is_using_instruction_variables=True,
            input_schema=input_schema,
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        curl_command = self.extract_curl_command(code)

        # Verify it matches the documentation pattern
        expected_elements = [
            "curl -X POST https://run.workflowai.com/v1/chat/completions",
            '"Authorization: Bearer $WORKFLOWAI_API_KEY"',
            '"Content-Type: application/json"',
            '"model": "code-gen-test-sentiment-analyzer/gemini-2.0-flash-001"',
            '"response_format"',
            '"type": "json_schema"',
            '"input":',
        ]

        for element in expected_elements:
            assert element in curl_command, f"Missing expected element: {element}"

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_curl_environment_variables(
        self,
        template_service: IntegrationTemplateService,
    ):
        """Test that curl commands correctly use environment variables"""
        integration = get_integration_by_kind(IntegrationKind.CURL)

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-test-agent",
            agent_schema_id=1,
            model_used="gpt-4o",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="Test")],
                ),
            ],
        )

        curl_command = self.extract_curl_command(code)

        # Verify environment variable usage
        assert "$WORKFLOWAI_API_KEY" in curl_command
        assert "Bearer $WORKFLOWAI_API_KEY" in curl_command

    # Define integrations that support tools
    TOOLS_INTEGRATIONS = [
        (IntegrationKind.OPENAI_SDK_PYTHON, "OpenAI SDK Python"),
        (IntegrationKind.LANGCHAIN_PYTHON, "LangChain Python"),
        (IntegrationKind.LITELLM_PYTHON, "LiteLLM Python"),
    ]

    # Integrations that support both tools AND structured output
    TOOLS_WITH_STRUCTURED_OUTPUT_INTEGRATIONS = [
        (IntegrationKind.INSTRUCTOR_PYTHON, "Instructor Python"),
        (IntegrationKind.OPENAI_SDK_PYTHON, "OpenAI SDK Python"),
        (IntegrationKind.DSPY_PYTHON, "DSPy Python"),
        (IntegrationKind.LANGCHAIN_PYTHON, "LangChain Python"),
        (IntegrationKind.LITELLM_PYTHON, "LiteLLM Python"),
    ]

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.parametrize("integration_kind,display_name", TOOLS_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_tools_execution(
        self,
        integration_kind: IntegrationKind,
        display_name: str,
        template_service: IntegrationTemplateService,
        sample_tools_list: list[Tool | ToolKind],
    ):
        """Test actual execution of integrations with tools - should call tools when appropriate"""
        integration = get_integration_by_kind(integration_kind)

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-weather-agent",
            agent_schema_id=1,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[
                        MessageContent(
                            text="What's the weather like in San Francisco? Use the get_weather tool if available.",
                        ),
                    ],
                ),
            ],
            enabled_tools=sample_tools_list,
        )

        python_code = extract_python_code(code)
        result = execute_python_code(python_code)

        # Verify execution was successful
        if not result["success"]:
            _logger.error("STDOUT: %s", result["stdout"])
            _logger.error("STDERR: %s", result["stderr"])
            pytest.fail(f"{display_name} tools execution failed: {result['stderr']}")

        # Verify there was output (response from API)
        assert result["stdout"].strip(), f"No output from {display_name} tools execution"

        # Check if tools were called (should appear in output based on our templates)
        output = result["stdout"]

        # Log the full output for inspection
        _logger.info("✅ %s Tools Execution Output: %s", display_name, output)

        # The templates include tool call handling, so we should see either:
        # 1. Tool calls being detected and logged
        # 2. Regular response content if no tools were called
        # This is a success as long as the code executed without errors

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_tools_syntax_validation(
        self,
        template_service: IntegrationTemplateService,
        sample_tools_list: list[Tool | ToolKind],
    ):
        """Test that all generated code with tools has valid syntax"""
        python_integrations = [
            integration
            for integration in OFFICIAL_INTEGRATIONS
            if integration.programming_language == ProgrammingLanguage.PYTHON
        ]

        # Integrations that actually support tools (based on integration_template_service.py)
        tools_supported_integrations = {
            IntegrationKind.OPENAI_SDK_PYTHON,
            IntegrationKind.DSPY_PYTHON,
            IntegrationKind.LANGCHAIN_PYTHON,
            IntegrationKind.LITELLM_PYTHON,
        }

        for integration in python_integrations:
            code = await template_service.generate_code(
                integration=integration,
                agent_id="code-gen-test-syntax-test",
                agent_schema_id=1,
                model_used="gpt-4o-mini",
                version_messages=[
                    Message(
                        role="user",
                        content=[MessageContent(text="Test weather in San Francisco")],
                    ),
                ],
                enabled_tools=sample_tools_list,
            )

            python_code = extract_python_code(code)

            # Validate syntax by compiling
            try:
                compile(python_code, f"<{integration.display_name}_tools_test>", "exec")
                _logger.info("✅ %s with tools: Syntax valid", integration.display_name)
            except SyntaxError as e:
                pytest.fail(
                    f"Generated {integration.display_name} code with tools has syntax error: {e}\n\nCode:\n{python_code}",
                )

            # Verify tool-specific content is present only for integrations that support tools
            if integration.slug in tools_supported_integrations:
                assert '"get_weather"' in python_code, f"Weather tool not found in {integration.display_name} code"
            else:
                _logger.info("⚠️  %s does not support tools - skipping tool content check", integration.display_name)

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_curl_tools_format(
        self,
        template_service: IntegrationTemplateService,
        sample_tools_list: list[Tool | ToolKind],
    ):
        """Test that curl command with tools is properly formatted"""
        integration = get_integration_by_kind(IntegrationKind.CURL)

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-weather-agent",
            agent_schema_id=1,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="What's the weather like in San Francisco?")],
                ),
            ],
            enabled_tools=sample_tools_list,
        )

        curl_command = self.extract_curl_command(code)

        # Validate curl command structure
        assert "curl -X POST" in curl_command
        assert "https://run.workflowai.com/v1/chat/completions" in curl_command
        assert '"tools":' in curl_command
        assert '"get_weather"' in curl_command
        assert "Get the current weather for a given location" in curl_command

        # Basic syntax checks
        assert curl_command.count("{") == curl_command.count("}")
        assert curl_command.count("[") == curl_command.count("]")
        assert curl_command.count('"') % 2 == 0

        _logger.info("✅ curl with tools: Format valid")

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.parametrize("integration_kind,display_name", TOOLS_WITH_STRUCTURED_OUTPUT_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_tools_with_structured_output_execution(
        self,
        integration_kind: IntegrationKind,
        display_name: str,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
        sample_tools_list: list[Tool | ToolKind],
    ):
        """Test actual execution of tools combined with structured output"""
        integration = get_integration_by_kind(integration_kind)
        input_schema, output_schema = user_info_extraction_schemas

        # DSPy uses input variables differently, others use them consistently
        use_input_vars = True
        test_message = "Check weather for {{user_text}} and return structured user info"
        if integration_kind == IntegrationKind.DSPY_PYTHON:
            test_message = "Process weather data: {{user_text}}"

        code = await template_service.generate_code(
            integration=integration,
            agent_id=f"code-gen-test-{display_name.lower().replace(' ', '-')}-weather-user-agent",
            agent_schema_id=1,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text=test_message)],
                ),
            ],
            is_using_instruction_variables=use_input_vars,
            input_schema=input_schema,
            is_using_structured_generation=True,
            output_schema=output_schema,
            enabled_tools=sample_tools_list,
        )

        python_code = extract_python_code(code)
        result = execute_python_code(python_code)

        # Verify execution was successful
        if not result["success"]:
            _logger.error("STDOUT: %s", result["stdout"])
            _logger.error("STDERR: %s", result["stderr"])
            pytest.fail(f"{display_name} Tools + Structured Output execution failed: {result['stderr']}")

        # Verify there was output
        assert result["stdout"].strip(), f"No output from {display_name} Tools + Structured Output execution"

        _logger.info("✅ %s Tools + Structured Output Execution Output: %s", display_name, result["stdout"])

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_nested_schema_execution(
        self,
        template_service: IntegrationTemplateService,
        nested_data_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test execution with complex nested schemas to verify enhanced parsing"""
        input_schema, output_schema = nested_data_extraction_schemas

        # Test with OpenAI SDK Python (most comprehensive integration)
        integration = get_integration_by_kind(IntegrationKind.OPENAI_SDK_PYTHON)

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-nested-schema-test",
            agent_schema_id=1,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="Extract complex nested data from: {{document_text}}")],
                ),
            ],
            is_using_instruction_variables=True,
            input_schema=input_schema,
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        python_code = extract_python_code(code)

        # Verify that the code contains proper nested class definitions
        assert "class ExtractedData(BaseModel):" in python_code

        # Check for nested class handling - should have proper typing for nested objects
        # The enhanced parser should generate proper nested classes or at least proper type hints
        assert "person:" in python_code
        assert "company:" in python_code
        assert "metadata:" in python_code

        # Verify the code has proper imports for complex types
        assert "from pydantic import" in python_code and "BaseModel" in python_code

        # Test execution
        result = execute_python_code(python_code)

        if not result["success"]:
            _logger.error("STDOUT: %s", result["stdout"])
            _logger.error("STDERR: %s", result["stderr"])
            pytest.fail(f"Nested schema execution failed: {result['stderr']}")

        output = result["stdout"]
        assert output.strip(), "No output from nested schema execution"
        _logger.info("✅ Nested Schema Execution Output: %s...", output[:200])

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_nested_schema_syntax_validation(
        self,
        template_service: IntegrationTemplateService,
        nested_data_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test that complex nested schemas generate valid syntax for all integrations"""
        input_schema, output_schema = nested_data_extraction_schemas

        # Test Python integrations that support structured output
        python_integrations = [
            IntegrationKind.OPENAI_SDK_PYTHON,
            IntegrationKind.INSTRUCTOR_PYTHON,
            IntegrationKind.LANGCHAIN_PYTHON,
            IntegrationKind.LITELLM_PYTHON,
        ]

        for integration_kind in python_integrations:
            integration = get_integration_by_kind(integration_kind)

            code = await template_service.generate_code(
                integration=integration,
                agent_id="code-gen-test-nested-syntax-test",
                agent_schema_id=1,
                model_used="gpt-4o-mini",
                version_messages=[
                    Message(
                        role="user",
                        content=[MessageContent(text="Extract: {{document_text}}")],
                    ),
                ],
                is_using_instruction_variables=True,
                input_schema=input_schema,
                is_using_structured_generation=True,
                output_schema=output_schema,
            )

            python_code = extract_python_code(code)

            # Validate syntax by compiling
            try:
                compile(python_code, f"<{integration.display_name}_nested_test>", "exec")
                _logger.info("✅ %s: Complex nested schema syntax valid", integration.display_name)
            except SyntaxError as e:
                pytest.fail(
                    f"Generated {integration.display_name} code with nested schema has syntax error: {e}\n\nCode:\n{python_code}",
                )

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.asyncio
    async def test_typescript_nested_schema_generation(
        self,
        template_service: IntegrationTemplateService,
        nested_data_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test TypeScript nested schema generation"""
        input_schema, output_schema = nested_data_extraction_schemas

        integration = get_integration_by_kind(IntegrationKind.OPENAI_SDK_TS)

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-typescript-nested-test",
            agent_schema_id=1,
            model_used="gpt-4o-mini",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="Extract: {{document_text}}")],
                ),
            ],
            is_using_instruction_variables=True,
            input_schema=input_schema,
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        # Extract TypeScript code from markdown
        ts_match = re.search(r"```typescript\n(.*?)\n```", code, re.DOTALL)
        assert ts_match, "No TypeScript code block found in generated code"

        typescript_code = ts_match.group(1)

        # Verify TypeScript contains proper nested types
        assert "const ExtractedDataSchema = z.object({" in typescript_code
        assert "person: z.object({" in typescript_code
        assert "company: z.object({" in typescript_code
        assert "metadata: z.object({" in typescript_code

        # Verify arrays of objects are handled
        assert "z.array(" in typescript_code

        _logger.info("✅ TypeScript nested schema generation successful")
