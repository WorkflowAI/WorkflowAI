# pyright: reportPrivateUsage=false

import pytest

from api.routers.mcp._mcp_codegen import CodegenService
from core.domain.consts import WORKFLOWAI_RUN_URL
from core.domain.version_environment import VersionEnvironment


@pytest.fixture
def codegen_service():
    return CodegenService()


class TestCodegenPython:
    PREAMBLE = """# Instantiate a client and set the base URL and api key
# It might be possible to import an existing client instead of creating a new one
client = OpenAI(
    api_key=os.environ["WORKFLOWAI_API_KEY"],
    base_url="__WORKFLOWAI_RUN_URL__/v1",
)
# it is also possible to set default values for the the openai library
# import openai
#
# openai.api_key = os.environ["WORKFLOWAI_API_KEY"]
# openai.base_url = f"__WORKFLOWAI_RUN_URL__/v1"
"""

    OPENAI_IMPORT = """from openai import OpenAI # needed if instantiating a client
"""

    def _compare(self, result: str, expected: str):
        assert (
            result
            == expected.replace("__PREAMBLE__", self.PREAMBLE)
            .replace("__OPENAI_IMPORT__", self.OPENAI_IMPORT)
            .replace("__WORKFLOWAI_RUN_URL__", WORKFLOWAI_RUN_URL)
            .strip()
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


class TestCodegenJS:
    PREAMBLE = """// Instantiate a client and set the base URL and api key
// It might be possible to import an existing client instead of creating a new one
const client = new OpenAI({
    apiKey: process.env.WORKFLOWAI_API_KEY,
    baseURL: "__WORKFLOWAI_RUN_URL__/v1",
});
"""

    OPENAI_IMPORT = """import OpenAI from 'openai'; // needed if instantiating a client
"""

    def _compare(self, result: str, expected: str):
        assert (
            result.strip()
            == expected.replace("__PREAMBLE__", self.PREAMBLE)
            .replace("__OPENAI_IMPORT__", self.OPENAI_IMPORT)
            .replace("__WORKFLOWAI_RUN_URL__", WORKFLOWAI_RUN_URL)
            .strip()
        )

    async def test_basic(self, codegen_service: CodegenService):
        """No deployment, no structured output"""
        result = await codegen_service._generate_code_inner(
            agent_id="test",
            model="gpt-4o",
            sdk="javascript/openai-sdk",
        )
        self._compare(
            result,
            """
__OPENAI_IMPORT__


__PREAMBLE__

const completion = await client.chat.completions.create({
    // Completion request messages
    // When relevant, the text, image_url or audio data content can be a jinja2 template
    // Template variables should be passed in the input field.
    messages: [
        // Add your messages here
    ],
    model: "gpt-4o",
    metadata: {
        agent_id: "test",
    },
    input: {} // contains template variables when relevant
});

const result = completion.choices[0].message.content;
console.log(result);
""",
        )

    async def test_deployment_no_structured_output(self, codegen_service: CodegenService):
        result = await codegen_service._generate_code_inner(
            agent_id="test",
            model="gpt-4o",
            schema_id=1,
            environment=VersionEnvironment.PRODUCTION,
            sdk="javascript/openai-sdk",
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

const completion = await client.chat.completions.create({
    // When using a deployment, messages included in the deployed version should
    // not be included in the messages list. Any added message will be appended
    // to messages contained in the deployment.
    messages: [],
    model: "#1/production",
    metadata: {
        agent_id: "test",
    },
    // Input dictionary should match the following JSON schema:
    // {"type": "object", "properties": {"name": {"type": "string"}}}
    input: {
        // Input data goes here
    }
});

const result = completion.choices[0].message.content;
console.log(result);
""",
        )

    async def test_deployment_structured_output(self, codegen_service: CodegenService):
        result = await codegen_service._generate_code_inner(
            agent_id="test",
            model="gpt-4o",
            schema_id=1,
            environment=VersionEnvironment.PRODUCTION,
            sdk="javascript/openai-sdk",
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

// Import zod for structured generation
import { zodResponseFormat } from 'openai/helpers/zod';
import { z } from 'zod';


__PREAMBLE__
const TestOutput = z.object({
    // Here you should generate a Zod schema that matches the following JSON schema:
    // {"type": "object", "properties": {"greeting": {"type": "string"}}}
});

// beta is needed for using zod schema in the response format
const completion = await client.beta.chat.completions.parse({
    response_format: zodResponseFormat(TestOutput, 'TestOutput'),

// if the user does not want to use zod or the beta client, it is also
// possible to pass the json schema to the response format object.
// response_format: {
//     type: "json_schema",
//     json_schema: {
//         name: "TestOutput",
//         schema: {
//             // JSON schema should match the following:
//             // {"type": "object", "properties": {"greeting": {"type": "string"}}}
//         }
//     }
// },
    // When using a deployment, messages included in the deployed version should
    // not be included in the messages list. Any added message will be appended
    // to messages contained in the deployment.
    messages: [],
    model: "#1/production",
    metadata: {
        agent_id: "test",
    },
    // Input dictionary should match the following JSON schema:
    // {"type": "object", "properties": {"name": {"type": "string"}}}
    input: {
        // Input data goes here
    }
});

const result = completion.choices[0].message.parsed;
// If not using the beta client with `completions.parse` you will have to parse the result manually
// const result = JSON.parse(completion.choices[0].message.content);
// If you need to add typing, `https://github.com/ThomasAribart/json-schema-to-ts` is a good library
// with no overhead since it only generates types
// import { FromSchema } from "json-schema-to-ts";
// type TestOutput = FromSchema<typeof the-json-schema-from-above>;
// const result: TestOutput = JSON.parse(completion.choices[0].message.content);
console.log(result);
""",
        )
