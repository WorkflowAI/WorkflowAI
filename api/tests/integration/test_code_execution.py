import hashlib
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, NamedTuple, Optional

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

# To store generated code for debugging
DEBUG_DIR = Path("debug_generated_code")
DEBUG_DIR.mkdir(exist_ok=True)


def save_extracted_code(save_to_filename: str, code: str, file_ext: str) -> str:
    """
    Save extracted code (Python, TypeScript, etc.) to a file for debugging

    Args:
        save_to_filename: Name of the test
        code: The extracted code content
        file_ext: File extension (py, ts, sh, etc.)

    Returns:
        Path to the saved file
    """
    # Generate content hash
    content_hash = hashlib.md5(code.encode()).hexdigest()[:8]

    # Clean names for filesystem
    clean_test_name = re.sub(r"[^\w\-_]", "_", save_to_filename)

    # Create filename with "extracted" prefix
    filename = f"{clean_test_name}_{content_hash}.{file_ext}"
    filepath = DEBUG_DIR / filename

    # Save the file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)

    _logger.info("💾 Saved extracted code to: %s", filepath)
    return str(filepath)


def get_file_extension(integration_kind: IntegrationKind) -> str:
    """Get appropriate file extension for integration type"""
    if integration_kind == IntegrationKind.CURL:
        return "sh"
    if integration_kind == IntegrationKind.OPENAI_SDK_TS:
        return "ts"
    return "py"


def extract_python_code(generated_code: str) -> str:
    """Extract Python code from markdown code blocks"""
    code_match = re.search(r"```python\n(.*?)\n```", generated_code, re.DOTALL)
    if code_match:
        return code_match.group(1)
    raise ValueError("No Python code block found in generated code")


def run_generated_code(
    generated_code: str,
    save_to_filename: str | None = None,
) -> Dict[str, Any]:
    """
    Unified function to extract, optionally save, and run generated code

    Automatically detects language from markdown code blocks and handles:
    - Python: extraction, saving, and execution
    - Bash/Shell/Curl: extraction, saving, and execution
    - TypeScript/JavaScript: extraction and saving (no execution yet)

    Usage Examples:
        # Extract and run Python code with saving
        result = run_generated_code(code, save_to="enabled", test_name="openai_python_test")
        if result["execution_result"]["success"]:
            print(result["execution_result"]["stdout"])

        # Extract and run bash/curl command
        result = run_generated_code(curl_code, test_name="curl_test")
        if result["execution_result"]["success"]:
            print(result["execution_result"]["stdout"])

        # Extract TypeScript code with saving
        result = run_generated_code(ts_code, save_to="enabled", test_name="openai_ts_test")
        typescript_code = result["extracted_code"]

    Args:
        generated_code: The full generated code with markdown blocks
        save_to: Optional path info for saving - if provided, extracted code will be saved
        test_name: Name for the test (used in file naming and integration name if saving)

    Returns:
        Dict containing:
        - language: detected language ("python", "typescript", "bash", etc.)
        - extracted_code: the extracted code content
        - execution_result: execution results (for Python and bash/shell, None for others)
        - saved_file: path to saved file if save_to was provided, None otherwise
    """
    result: Dict[str, Any] = {
        "language": None,
        "extracted_code": None,
        "execution_result": None,
        "saved_file": None,
    }

    # Language detection patterns - order matters for specificity
    language_patterns = [
        (r"```python\n(.*?)\n```", "python", "py"),
        (r"```typescript\n(.*?)\n```", "typescript", "ts"),
        (r"```javascript\n(.*?)\n```", "javascript", "js"),
        (r"```bash\n(.*?)\n```", "bash", "sh"),
        (r"```shell\n(.*?)\n```", "shell", "sh"),
        (r"```sh\n(.*?)\n```", "sh", "sh"),
    ]

    # Try to detect and extract code
    for pattern, language, file_ext in language_patterns:
        match = re.search(pattern, generated_code, re.DOTALL)
        if match:
            result["language"] = language
            result["extracted_code"] = match.group(1)

            # Save extracted code if requested
            if save_to_filename:
                saved_path = save_extracted_code(
                    save_to_filename,
                    result["extracted_code"],
                    file_ext,
                )
                result["saved_file"] = saved_path

            # Execute code based on language
            if language == "python":
                result["execution_result"] = execute_python_code(result["extracted_code"])
            elif language in ["bash", "shell", "sh"]:
                result["execution_result"] = execute_bash_code(result["extracted_code"])
            else:
                _logger.info("🔄 Code extraction successful for %s, but execution not supported yet", language)

            return result

    # If no code block found, raise error
    raise ValueError(
        f"No supported code block found in generated code. Supported: {[lang for _, lang, _ in language_patterns]}",
    )


def execute_bash_code(code: str, env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Execute bash/shell code in a controlled environment and capture results

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

    # Create a temporary file with the bash script
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        # Add shebang for proper execution
        f.write("#!/bin/bash\nset -e\n")
        f.write(code)
        temp_file = f.name

    try:
        # Make the script executable
        os.chmod(temp_file, 0o755)

        # Execute the bash script
        result = subprocess.run(
            ["/bin/bash", temp_file],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,  # 30 second timeout
        )

        return {
            "success": result.returncode == 0 and "error" not in result.stdout,
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
    base_url = WORKFLOWAI_API_URL
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

    RUNNABLE_INTEGRATIONS = [
        IntegrationKind.OPENAI_SDK_PYTHON,
        IntegrationKind.LANGCHAIN_PYTHON,
        IntegrationKind.LITELLM_PYTHON,
        IntegrationKind.INSTRUCTOR_PYTHON,
        IntegrationKind.CURL,
    ]

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
            "Create a sample user with {{user_text}}",
        ),
        (
            IntegrationKind.INSTRUCTOR_PYTHON,
            "Instructor",
            "Extract: {{user_text}}",
        ),
        (IntegrationKind.LANGCHAIN_PYTHON, "LangChain", "Create user data: {{user_text}}"),
        (IntegrationKind.LITELLM_PYTHON, "LiteLLM", "Generate: {{user_text}}"),
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
    @pytest.mark.parametrize("integration_kind", RUNNABLE_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_raw_text(
        self,
        integration_kind: IntegrationKind,
        template_service: IntegrationTemplateService,
    ):
        """Test basic execution of all integrations with real API calls"""
        integration = get_integration_by_kind(integration_kind)

        if integration.only_support_structured_generation:
            pytest.skip(f"{integration.display_name} only supports structured generation, skipping test")

        # Generate the code
        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-raw-text",
            agent_schema_id=1,
            model_used="gemini-2.0-flash-001",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="Say hello")],
                ),
            ],
        )

        # Use unified code runner with optional saving
        code_result = run_generated_code(
            code,
            save_to_filename=f"test_basic_execution_{integration_kind.value}",
        )

        # Verify execution was successful
        execution_result = code_result["execution_result"]
        if not execution_result["success"]:
            _logger.error("STDOUT: %s", execution_result["stdout"])
            _logger.error("STDERR: %s", execution_result["stderr"])
            pytest.fail(f"{integration_kind.value} execution failed: {execution_result['stderr']}")

        assert "hello" in execution_result["stdout"].lower()

    @pytest.mark.parametrize("integration_kind", RUNNABLE_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_raw_text_streaming(
        self,
        integration_kind: IntegrationKind,
        template_service: IntegrationTemplateService,
    ):
        """Test basic execution of all integrations with real API calls"""
        integration = get_integration_by_kind(integration_kind)

        if integration.only_support_structured_generation:
            pytest.skip(f"{integration.display_name} only supports structured generation, skipping test")

        # Generate the code
        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-raw-text",
            agent_schema_id=1,
            model_used="gemini-2.0-flash-001",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text="Say hello")],
                ),
            ],
            is_streaming=True,
        )

        # Use unified code runner with optional saving
        code_result = run_generated_code(
            code,
            save_to_filename=f"test_raw_text_streaming_{integration_kind.value}",
        )

        assert code_result["execution_result"]["success"], {code_result["execution_result"]["stderr"]}

        assert "hello" in code_result["execution_result"]["stdout"].lower()

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.parametrize("integration_kind", RUNNABLE_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_raw_text_input_variables(
        self,
        integration_kind: IntegrationKind,
        template_service: IntegrationTemplateService,
    ):
        """Test basic execution of all integrations with real API calls"""
        integration = get_integration_by_kind(integration_kind)

        if integration.only_support_structured_generation:
            pytest.skip(f"{integration.display_name} only supports structured generation, skipping test")

        # Generate the code
        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-raw-text-input-variables",
            agent_schema_id=1,
            model_used="gemini-2.0-flash-001",
            version_messages=[
                Message(
                    role="system",
                    content=[MessageContent(text="Say hello to the user and mention")],
                ),
                Message(
                    role="user",
                    content=[MessageContent(text="The user name is {{user_name}}")],
                ),
            ],
            is_using_instruction_variables=True,
            input_variables={"user_name": "Maxime"},
        )

        # Use unified code runner with optional saving
        code_result = run_generated_code(
            code,
            save_to_filename=f"test_raw_text_input_variables_{integration_kind.value}",
        )

        # Verify execution was successful
        execution_result = code_result["execution_result"]
        assert execution_result["success"], {execution_result["stderr"]}

        assert "hello" in execution_result["stdout"].lower()
        assert "maxime" in execution_result["stdout"].lower()

    @pytest.mark.parametrize("integration_kind", RUNNABLE_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_raw_text_input_variables_deployment(
        self,
        integration_kind: IntegrationKind,
        template_service: IntegrationTemplateService,
    ):
        """Test basic execution of all integrations with real API calls"""
        integration = get_integration_by_kind(integration_kind)

        if integration.only_support_structured_generation:
            pytest.skip(f"{integration.display_name} only supports structured generation, skipping test")

        # Generate the code
        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-raw-text-input-variables",
            agent_schema_id=2,
            model_used="gemini-2.0-flash-001",
            version_messages=[],
            is_using_instruction_variables=True,
            input_variables={"user_name": "Maxime"},
            version_deployment_environment="production",
        )

        # Use unified code runner with optional saving
        code_result = run_generated_code(
            code,
            save_to_filename=f"test_raw_text_input_variables_deployment_{integration_kind.value}",
        )

        # Verify execution was successful
        execution_result = code_result["execution_result"]
        if not execution_result["success"]:
            _logger.error("STDOUT: %s", execution_result["stdout"])
            _logger.error("STDERR: %s", execution_result["stderr"])
            pytest.fail(f"{integration_kind.value} execution failed: {execution_result['stderr']}")

        assert "hello" in execution_result["stdout"].lower()
        assert "maxime" in execution_result["stdout"].lower()

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

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-structured-test",
            agent_schema_id=1,
            model_used="gemini-2.0-flash-001",
            version_messages=[
                Message(
                    role="user",
                    content=[MessageContent(text=test_message)],
                ),
            ],
            is_using_instruction_variables=True,
            input_schema=input_schema,
            is_using_structured_generation=True,
            output_schema=output_schema,
        )

        result = run_generated_code(
            code,
            save_to_filename=f"test_structured_output_execution_{display_name}",
        )

        assert result["execution_result"]["success"], {result["execution_result"]["stderr"]}

        output = result["execution_result"]["stdout"]
        assert output.strip(), f"No output from {display_name} structured execution"
        _logger.info("✅ %s Structured Output: %s...", display_name, output[:100])

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.parametrize("integration_kind", RUNNABLE_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_structured_output_execution_with_input_variables(
        self,
        integration_kind: IntegrationKind,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test structured output execution of all integrations with real API calls"""
        integration = get_integration_by_kind(integration_kind)
        input_schema, output_schema = user_info_extraction_schemas

        use_input_vars = True

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-struct-gen-input-vars",
            agent_schema_id=1,
            model_used="gemini-2.0-flash-001",
            version_messages=[
                Message(
                    role="system",
                    content=[MessageContent(text="You goal is to extract user information from a message")],
                ),
                Message(
                    role="user",
                    content=[MessageContent(text="The message is {{message}}")],
                ),
            ],
            is_using_instruction_variables=use_input_vars,
            input_schema=input_schema if use_input_vars else None,
            is_using_structured_generation=True,
            output_schema=output_schema,
            input_variables={"message": "Hello ! I'm Tom, I'm 26, my email is tom@gmail.com"},
        )

        result = run_generated_code(
            code,
            save_to_filename=f"code-gen-struct-gen-input-vars_{integration_kind.value}",
        )

        assert result["execution_result"]["success"], {result["execution_result"]["stderr"]}

        output = result["execution_result"]["stdout"]

        assert "tom" in output.lower()
        assert "26" in output.lower()
        assert "tom@gmail.com" in output.lower()

    @pytest.mark.parametrize("integration_kind", RUNNABLE_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_structured_output_execution_with_input_variables_streaming(
        self,
        integration_kind: IntegrationKind,
        template_service: IntegrationTemplateService,
        user_info_extraction_schemas: tuple[Dict[str, Any], Dict[str, Any]],
    ):
        """Test structured output execution of all integrations with real API calls"""
        integration = get_integration_by_kind(integration_kind)
        input_schema, output_schema = user_info_extraction_schemas

        use_input_vars = True

        if integration_kind == IntegrationKind.INSTRUCTOR_PYTHON:
            pytest.skip("Streaming with Pydantic response_format not yet supported.")

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-struct-gen-input-vars",
            agent_schema_id=1,
            model_used="gemini-2.0-flash-001",
            version_messages=[
                Message(
                    role="system",
                    content=[MessageContent(text="You goal is to extract user information from a message")],
                ),
                Message(
                    role="user",
                    content=[MessageContent(text="The message is {{message}}")],
                ),
            ],
            is_using_instruction_variables=use_input_vars,
            input_schema=input_schema if use_input_vars else None,
            is_using_structured_generation=True,
            output_schema=output_schema,
            input_variables={"message": "Hello ! I'm Tom, I'm 26, my email is tom@gmail.com"},
            is_streaming=True,
        )

        result = run_generated_code(
            code,
            save_to_filename=f"code-gen-struct-gen-input-vars-streaming-{integration_kind.value}",
        )

        assert result["execution_result"]["success"], {result["execution_result"]["stderr"]}

        output = result["execution_result"]["stdout"]

        assert "tom" in output.lower()
        assert "26" in output.lower()
        assert "tom@gmail.com" in output.lower()

    @pytest.mark.skip("Skipping real code execution tests")
    @pytest.mark.parametrize("integration_kind,display_name,test_message", STRUCTURED_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_structured_output_execution_with_deployment(
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

        use_input_vars = True

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-structured-test",
            agent_schema_id=1,
            model_used="gemini-2.0-flash-001",
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
            version_deployment_environment="production",
        )

        result = run_generated_code(
            code,
            save_to_filename=f"test_structured_output_execution_with_deployment_{display_name}",
        )

        assert result["execution_result"]["success"], {result["execution_result"]["stderr"]}

        output = result["execution_result"]["stdout"]
        assert output.strip(), f"No output from {display_name} structured execution"
        _logger.info("✅ %s Structured Output: %s...", display_name, output[:100])

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
                model_used="gemini-2.0-flash-001",
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
            model_used="gemini-2.0-flash-001",
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
            model_used="gemini-2.0-flash-001",
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
            model_used="gemini-2.0-flash-001",
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

        # Use unified code runner for curl (bash/shell) extraction and saving
        code_result = run_generated_code(
            code,
            save_to_filename=f"test_curl_generation_{scenario}_curl",
        )

        assert code_result["execution_result"]["success"], code_result["execution_result"]["stdout"]

        curl_command = code_result["extracted_code"]
        _logger.info("🔧 Extracted %s code from generated content", code_result["language"])

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
            assert "user_text" in curl_command

        elif scenario == "structured_output":
            assert '"response_format":' in curl_command
            assert '"json_schema"' in curl_command
            # Test actual schema that gets generated (UserInfo schema)
            assert '"name"' in curl_command or '"age"' in curl_command

        elif scenario == "deployment":
            assert '"model": "code-gen-test-sentiment-analyzer/#3/production"' in curl_command
            assert '"messages": []' in curl_command

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
        (IntegrationKind.LANGCHAIN_PYTHON, "LangChain Python"),
        (IntegrationKind.LITELLM_PYTHON, "LiteLLM Python"),
    ]

    @pytest.mark.parametrize("integration_kind", RUNNABLE_INTEGRATIONS)
    @pytest.mark.asyncio
    async def test_tools_execution(
        self,
        integration_kind: IntegrationKind,
        template_service: IntegrationTemplateService,
        sample_tools_list: list[Tool | ToolKind],
    ):
        """Test actual execution of integrations with tools - should call tools when appropriate"""
        integration = get_integration_by_kind(integration_kind)

        if integration.only_support_structured_generation:
            pytest.skip("Skipping tools execution for integrations that only support structured output")

        code = await template_service.generate_code(
            integration=integration,
            agent_id="code-gen-test-weather-agent",
            agent_schema_id=1,
            model_used="gemini-2.0-flash-001",
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

        result = run_generated_code(
            code,
            save_to_filename=f"test_tools_execution_{integration_kind.value}",
        )

        assert result["execution_result"]["success"], {result["execution_result"]["stderr"]}
        assert "get_weather" in result["execution_result"]["stdout"]

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
                model_used="gemini-2.0-flash-001",
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
            model_used="gemini-2.0-flash-001",
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
        assert '"tools":' in curl_command
        assert '"get_weather"' in curl_command
        assert "Get the current weather for a given location" in curl_command

        # Basic syntax checks
        assert curl_command.count("{") == curl_command.count("}")
        assert curl_command.count("[") == curl_command.count("]")
        assert curl_command.count('"') % 2 == 0

        _logger.info("✅ curl with tools: Format valid")

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
            model_used="gemini-2.0-flash-001",
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

        result = run_generated_code(
            code,
            save_to_filename="test_nested_schema_execution",
        )

        assert "person:" in code
        assert "company:" in code
        assert "metadata:" in code

        # Verify the code has proper imports for complex types
        assert "from pydantic import" in code and "BaseModel" in code

        result = run_generated_code(
            code,
            save_to_filename="test_nested_schema_execution",
        )

        assert result["execution_result"]["success"], {result["execution_result"]["stderr"]}

        output = result["execution_result"]["stdout"]
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
                model_used="gemini-2.0-flash-001",
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
            model_used="gemini-2.0-flash-001",
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

        # Save generated code for debugging
        file_ext = get_file_extension(integration.slug)
        save_extracted_code(
            "test_typescript_nested_schema_generation" + integration.display_name,
            code,
            file_ext,
        )

        # Extract TypeScript code from markdown
        ts_match = re.search(r"```typescript\n(.*?)\n```", code, re.DOTALL)
        assert ts_match, "No TypeScript code block found in generated code"

        typescript_code = ts_match.group(1)

        # Save extracted TypeScript code for debugging
        save_extracted_code(
            "test_typescript_nested_schema_generation" + integration.display_name,
            typescript_code,
            "ts",
        )

        # Verify TypeScript contains proper nested types
        assert "const ExtractedDataSchema = z.object({" in typescript_code
        assert "person: z.object({" in typescript_code
        assert "company: z.object({" in typescript_code
        assert "metadata: z.object({" in typescript_code

        # Verify arrays of objects are handled
        assert "z.array(" in typescript_code

        _logger.info("✅ TypeScript nested schema generation successful")
