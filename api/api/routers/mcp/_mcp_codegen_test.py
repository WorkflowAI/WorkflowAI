# pyright: reportPrivateUsage=false

import pytest

from api.routers.mcp._mcp_codegen import CodegenService
from core.domain.version_environment import VersionEnvironment


@pytest.fixture
def codegen_service():
    return CodegenService()


class TestCodegenPython:
    PREAMBLE = """# Instantiate a client and set the base URL and api key
# It might be possible to import an existing client instead of creating a new one
client = OpenAI(
    api_key=os.environ["WORKFLOWAI_API_KEY"],
    base_url="http://localhost:8000/v1",
)
# it is also possible to set default values for the the openai library
# import openai
#
# openai.api_key = os.environ["WORKFLOWAI_API_KEY"]
# openai.base_url = f"http://localhost:8000/v1"
"""

    OPENAI_IMPORT = """from openai import OpenAI # needed if instantiating a client
"""

    def _compare(self, result: str, expected: str):
        assert (
            result
            == expected.replace("__PREAMBLE__", self.PREAMBLE).replace("__OPENAI_IMPORT__", self.OPENAI_IMPORT).strip()
        )

    async def test_basic(self, codegen_service: CodegenService):
        """No deployment, no structured output"""
        result = await codegen_service._generate_code_inner(
            agent_id="test",
            model="gpt-4o",
            sdk="python/openai-sdk",
        )
        self._compare(
            result,
            """
__OPENAI_IMPORT__

__PREAMBLE__

completion = client.chat.completions.create(
    # Completion request messages
    # When relevant, the text, image_url or audio data content can be a jinja2 template
    # Template variables should be passed as extra_body in the input field.
    messages=[...]
    model="gpt-4o",
    metadata={
        "agent_id": "test",
    },
    extra_body={
        "input": {} # contains template variables when relevant
    }
)

result = completion.choices[0].message.content
print(result)
""",
        )

    async def test_deployment_no_structured_output(self, codegen_service: CodegenService):
        result = await codegen_service._generate_code_inner(
            agent_id="test",
            model="gpt-4o",
            schema_id=1,
            environment=VersionEnvironment.PRODUCTION,
            sdk="python/openai-sdk",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
            },
        )
        self._compare(
            result,
            """
__OPENAI_IMPORT__

__PREAMBLE__

completion = client.chat.completions.create(
    # When using a deployment, messages included in the deployed version should
    # not be included in the messages list. Any added message will be appended
    # to messages contained in the deployment.
    messages=[]
    model="#1/production",
    metadata={
        "agent_id": "test",
    },
    extra_body={
       "input": {
        # Input dictionary should match the following JSON schema:
        # {"type": "object", "properties": {"name": {"type": "string"}}}
       }
    }
)

result = completion.choices[0].message.content
print(result)
""",
        )

    async def test_deployment_structured_output(self, codegen_service: CodegenService):
        result = await codegen_service._generate_code_inner(
            agent_id="test",
            model="gpt-4o",
            schema_id=1,
            environment=VersionEnvironment.PRODUCTION,
            sdk="python/openai-sdk",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
            },
            response_json_schema={
                "type": "object",
                "properties": {
                    "greeting": {"type": "string"},
                },
            },
        )
        self._compare(
            result,
            """
__OPENAI_IMPORT__

# Import for pydantic for structured generation
from pydantic import BaseModel, Field

__PREAMBLE__
class TestOutput(BaseModel):
    # Here you should generate a pyndatic object that matches the following JSON schema:
    # {"type": "object", "properties": {"greeting": {"type": "string"}}}

# beta is needed for using pydantic model in the response format
completion = client.beta.chat.completions.parse(
    response_format=TestOutput,
    # When using a deployment, messages included in the deployed version should
    # not be included in the messages list. Any added message will be appended
    # to messages contained in the deployment.
    messages=[]
    model="#1/production",
    metadata={
        "agent_id": "test",
    },
    extra_body={
       "input": {
        # Input dictionary should match the following JSON schema:
        # {"type": "object", "properties": {"name": {"type": "string"}}}
       }
    }
)

result = completion.choices[0].message.parsed
print(result)
""",
        )
