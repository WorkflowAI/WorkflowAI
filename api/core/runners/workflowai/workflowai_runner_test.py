# pyright: reportPrivateUsage=false

import json
import re
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from PIL import Image
from pydantic import BaseModel
from pytest_httpx import HTTPXMock

from core.domain.errors import (
    JSONSchemaValidationError,
    ProviderDoesNotSupportModelError,
)
from core.domain.fields.file import File
from core.domain.fields.image_options import ImageOptions
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.message import Message, MessageContent, MessageDeprecated, Messages
from core.domain.metrics import Metric
from core.domain.models import Model, Provider
from core.domain.models.model_data import (
    FinalModelData,
    LatestModel,
    MaxTokensData,
    ModelData,
    QualityData,
    SpeedData,
    SpeedIndex,
)
from core.domain.models.model_data_mapping import MODEL_DATAS, DisplayedProvider
from core.domain.run_output import RunOutput
from core.domain.structured_output import StructuredOutput
from core.domain.task_group_properties import FewShotConfiguration, FewShotExample, TaskGroupProperties
from core.domain.task_io import RawJSONMessageSchema, RawMessagesSchema, RawStringMessageSchema, SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tool import Tool
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.domain.types import AgentOutput
from core.providers.base.abstract_provider import AbstractProvider
from core.providers.base.provider_error import (
    AgentRunFailedError,
    MaxToolCallIterationError,
    ModelDoesNotSupportMode,
    ProviderInternalError,
    ProviderUnavailableError,
    StructuredGenerationError,
)
from core.providers.base.provider_options import ProviderOptions
from core.runners.workflowai.internal_tool import InternalTool
from core.runners.workflowai.templates import TemplateName
from core.runners.workflowai.utils import FileWithKeyPath, ToolCallRecursionError
from core.runners.workflowai.workflowai_options import WorkflowAIRunnerOptions
from core.runners.workflowai.workflowai_runner import (
    MAX_TOOL_CALL_ITERATIONS,
    WorkflowAIRunner,
)
from core.tools import ToolKind
from tests import models as test_models
from tests.utils import mock_aiter


class _HelloTaskInput(BaseModel):
    input: str


def _build_runner(
    properties: TaskGroupProperties | None = None,
    model: Model = Model.GPT_4O_2024_11_20,
    task: SerializableTaskVariant | None = None,
    input_model: type[BaseModel] | None = None,
    output_model: type[BaseModel] | None = None,
):
    return WorkflowAIRunner(
        task or test_models.task_variant(input_model=input_model, output_model=output_model or input_model),
        properties=properties or TaskGroupProperties(model=model),
    )


# TODO: merge with _build_runner
def _build_runner2(
    mock_provider_factory: Mock,
    input_schema: dict[str, Any] | SerializableTaskIO,
    output_schema: dict[str, Any] | SerializableTaskIO,
    instructions: str | None = None,
    model: Model = Model.GPT_4O_2024_08_06,
    has_templated_instructions: bool = False,
    is_chain_of_thought_enabled: bool | None = None,
    enabled_tools: list[ToolKind | Tool] | None = None,
    messages: list[Message] | None = None,
):
    runner = WorkflowAIRunner(
        task=SerializableTaskVariant(
            id="test",
            task_id="h",
            task_schema_id=1,
            name="test",
            description="test",
            input_schema=input_schema
            if isinstance(input_schema, SerializableTaskIO)
            else SerializableTaskIO.from_json_schema(
                input_schema,
                streamline=True,
            ),
            output_schema=output_schema
            if isinstance(output_schema, SerializableTaskIO)
            else SerializableTaskIO.from_json_schema(
                output_schema,
                streamline=True,
            ),
        ),
        options=WorkflowAIRunnerOptions(
            instructions=instructions,
            model=model,
            has_templated_instructions=has_templated_instructions,
            is_chain_of_thought_enabled=is_chain_of_thought_enabled,
            enabled_tools=enabled_tools,
            provider=None,
            messages=messages,
        ),
    )
    runner.provider_factory = mock_provider_factory
    return runner


@pytest.fixture
def mock_provider():
    mock = Mock(spec=AbstractProvider)
    mock.requires_downloading_file.return_value = False
    mock.max_number_of_file_urls = None
    mock.sanitize_agent_instructions.return_value = "sanitized"
    mock.sanitize_template.side_effect = lambda template: template  # type:ignore
    return mock


@pytest.fixture
def mock_tool_fn(patched_runner: WorkflowAIRunner):
    mock_tool = AsyncMock()
    mock_tool.return_value = "success"
    with patch.dict(
        patched_runner._enabled_internal_tools,  # pyright: ignore[reportPrivateUsage]
        {
            "test_tool": InternalTool(_tool("test_tool"), mock_tool),
        },
    ):
        yield mock_tool


@pytest.fixture
def model_data():
    return ModelData(
        display_name="GPT-4o (2024-11-20)",
        supports_json_mode=True,
        supports_input_image=True,
        supports_input_pdf=False,
        supports_input_audio=False,
        supports_structured_output=True,
        max_tokens_data=MaxTokensData(
            max_tokens=128_000,
            max_output_tokens=16_384,
            source="https://platform.openai.com/docs/models",
        ),
        icon_url="https://workflowai.blob.core.windows.net/workflowai-public/openai.svg",
        latest_model=Model.GPT_4O_LATEST,
        release_date=date(2024, 11, 20),
        quality_data=QualityData(index=100),
        speed_data=SpeedData(index=SpeedIndex(value=500)),  # Default speed index, can be updated with real data later
        provider_name=DisplayedProvider.OPEN_AI.value,
        supports_tool_calling=True,
        fallback=None,
    )


@pytest.fixture(scope="function")
def mock_task():
    # Can't really use a wrap here since we use properties
    mock = Mock(spec=SerializableTaskVariant)
    mock.input_schema = SerializableTaskIO(json_schema={"properties": {}}, version="v1")
    mock.output_schema = SerializableTaskIO(json_schema={"properties": {}}, version="v1")
    mock.name = "mock_task_name"
    mock.id = "task_version_id"
    mock.task_id = "task_id"
    mock.task_schema_id = 1
    mock.tenant = "tenant1"

    def _validate_output(output: Any, *args: Any, **kwargs: Any):
        # Not performing any validation
        return output

    mock.validate_output.side_effect = _validate_output
    mock.compute_input_hash.return_value = "input_hash"
    mock.compute_output_hash.return_value = "output_hash"

    return mock


@pytest.fixture
def mock_build_properties():
    with patch.object(
        WorkflowAIRunner,
        "_build_properties",
        return_value=TaskGroupProperties(enabled_tools=[]),
    ) as mock:
        yield mock


@pytest.fixture(scope="function")
def patched_runner(mock_task: Mock, mock_build_properties: Mock):
    yield WorkflowAIRunner(
        mock_task,
        options=WorkflowAIRunnerOptions(
            instructions="",
            model=Model.GPT_4O_2024_11_20,
            provider=Provider.OPEN_AI,
            template_name=TemplateName.V1,
        ),
    )


class TestWorkflowAIRunnerMessages:
    async def test_default(self, mock_provider: Mock, model_data: ModelData):
        runner = _build_runner()
        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            {"input": "cool cool cool"},
            mock_provider,
            model_data,
        )
        assert len(messages) == 2

        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert (
            messages[0].content
            == """<instructions>

</instructions>

Input will be provided in the user message using a JSON following the schema:
```json
{
  "type": "object",
  "properties": {
    "input": {
      "type": "string"
    }
  },
  "required": [
    "input"
  ]
}
```

Return a single JSON object enforcing the following schema:
```json
{
  "type": "object",
  "properties": {
    "output": {
      "type": "integer"
    }
  },
  "required": [
    "output"
  ]
}
```"""
        )

        assert messages[1].role == MessageDeprecated.Role.USER
        assert (
            messages[1].content
            == """Input is:
```json
{
  "input": "cool cool cool"
}
```"""
        )

    async def test_with_examples(self, mock_provider: Mock, model_data: ModelData):
        runner = _build_runner(
            properties=TaskGroupProperties(
                model=Model.GPT_3_5_TURBO_1106,
                few_shot=FewShotConfiguration(
                    examples=[
                        FewShotExample(task_input={"input": "h"}, task_output={"input": "w"}),
                        FewShotExample(task_input={"input": "h1"}, task_output={"input": "w1"}),
                    ],
                ),
            ),
        )

        assert runner._options.examples and len(runner._options.examples) == 2  # pyright: ignore [reportPrivateUsage]

        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            {"input": "cool cool cool"},
            mock_provider,
            model_data,
        )

        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert (
            messages[0].content
            == """<instructions>

</instructions>

Input will be provided in the user message using a JSON following the schema:
```json
{
  "type": "object",
  "properties": {
    "input": {
      "type": "string"
    }
  },
  "required": [
    "input"
  ]
}
```

Return a single JSON object enforcing the following schema:
```json
{
  "type": "object",
  "properties": {
    "output": {
      "type": "integer"
    }
  },
  "required": [
    "output"
  ]
}
```"""
        )

        assert messages[1].role == MessageDeprecated.Role.USER
        assert (
            messages[1].content
            == """Input is:
```json
{
  "input": "cool cool cool"
}
```

Examples:

Input:
```json
{
  "input": "h"
}
```
Output:
```json
{
  "input": "w"
}
```

Input:
```json
{
  "input": "h1"
}
```
Output:
```json
{
  "input": "w1"
}
```"""
        )

    async def test_with_messages(self, mock_provider: Mock):
        runner = _build_runner(
            properties=TaskGroupProperties(
                model=Model.GPT_3_5_TURBO_1106,
            ),
            # Input schema has messages but they are a different case than StoredMessages
            task=test_models.task_variant(
                input_schema={
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            ),
        )

        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            {"messages": ["hello", "world"]},
            mock_provider,
            test_models.model_data(),
        )
        assert messages
        assert messages[1].role == MessageDeprecated.Role.USER
        assert (
            messages[1].content
            == """Input is:
```json
{
  "messages": [
    "hello",
    "world"
  ]
}
```"""
        )


class TestInlineMessages:
    async def test_inlined_structured_output(self, mock_provider_factory_full: Mock):
        runner = _build_runner2(
            mock_provider_factory=mock_provider_factory_full,
            input_schema=RawMessagesSchema,
            output_schema={"properties": {"output": {"type": "string"}}},
        )
        messages = await runner._inline_messages(
            [Message(role="user", content=[MessageContent(text="cool cool cool")])],
            Mock(),
            True,
            False,
        )
        assert len(messages) == 1
        assert messages[0].role == MessageDeprecated.Role.USER
        assert messages[0].content == "cool cool cool"

    async def test_inlined_raw_json(self, mock_provider_factory_full: Mock):
        runner = _build_runner2(
            mock_provider_factory=mock_provider_factory_full,
            input_schema=RawMessagesSchema,
            output_schema=RawJSONMessageSchema,
        )
        messages = await runner._inline_messages(
            [Message(role="user", content=[MessageContent(text="cool cool cool")])],
            Mock(),
            False,
            False,
        )
        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert messages[0].content == """Return a single JSON object"""
        assert messages[1].role == MessageDeprecated.Role.USER
        assert messages[1].content == "cool cool cool"

    async def test_inlined_no_structured_output_with_tool_use(self, patched_runner: WorkflowAIRunner):
        messages = await patched_runner._inline_messages(  # pyright: ignore [reportPrivateUsage]
            [Message(role="user", content=[MessageContent(text="cool cool cool")])],
            Mock(),
            False,
            True,
        )
        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert (
            messages[0].content
            == """Return either tool call(s) or a single JSON object enforcing the following schema:
```json
{
  "properties": {}
}
```"""
        )
        assert messages[1].role == MessageDeprecated.Role.USER
        assert messages[1].content == "cool cool cool"

    @pytest.mark.parametrize(
        "system_message",
        [
            ("here is a JSON schema"),
            ("I have a json-schema"),
            ("objects in json that match the following json_schema"),
        ],
    )
    async def test_no_addition_if_already_present(self, patched_runner: WorkflowAIRunner, system_message: str):
        messages = await patched_runner._inline_messages(  # pyright: ignore [reportPrivateUsage]
            [Message(role="system", content=[MessageContent(text=system_message)])],
            Mock(),
            False,
            False,
        )
        assert len(messages) == 1
        assert messages[0].content == system_message


def test_init() -> None:
    runner = WorkflowAIRunner(
        test_models.task_variant(),
        properties=TaskGroupProperties(
            model=Model.GPT_4O_MINI_2024_07_18,
            instructions="Hello, world!",
        ),
    )
    assert runner.properties.model_dump(exclude_none=True) == {
        "model": Model.GPT_4O_MINI_2024_07_18.value,
        "temperature": 0.0,
        "instructions": "Hello, world!",
        "runner_name": "WorkflowAI",
        "runner_version": "v0.1.0",
        "task_variant_id": "task_version_id",
        "has_templated_instructions": False,
    }


class TestStreamTaskOutputFromMessages:
    async def test_validate(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
        mock_task: Mock,
    ):
        mock_provider.stream.return_value = mock_aiter(
            StructuredOutput({"1": "a"}),
            StructuredOutput({"1": "a", "2": "b"}),
            StructuredOutput({"1": "a", "2": "b", "3": "c", "output": "hello"}),
            # Last one is validated
            StructuredOutput({"1": "a", "2": "b", "3": "c", "output": "hello"}, final=True),
        )

        patched_runner.properties.enabled_tools = []
        yielded: list[AgentOutput] = [
            chunk.task_output
            async for chunk in patched_runner._stream_task_output_from_messages(  # pyright: ignore [reportPrivateUsage]
                mock_provider,
                ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
                [],
            )
        ]

        assert yielded == [
            # First ones are not validated so they are returned as is
            {"1": "a"},
            {"1": "a", "2": "b"},
            {"1": "a", "2": "b", "3": "c", "output": "hello"},
            {"1": "a", "2": "b", "3": "c", "output": "hello"},
        ]


@pytest.fixture(autouse=True)
def mock_download_file():
    with patch("core.runners.workflowai.workflowai_runner.download_file", return_value=None) as mock:
        yield mock


class TestBuildMessages:
    @patch("pdf2image.convert_from_bytes")
    async def test_run_with_pdf_and_unsupported_images(
        self,
        mock_convert_from_bytes: Mock,
        mock_provider: Mock,
        model_data: ModelData,
    ) -> None:
        class PdfSummaryTaskInput(BaseModel):
            file: File

        task = test_models.task_variant(input_model=PdfSummaryTaskInput, output_model=PdfSummaryTaskInput)

        runner = _build_runner(task=task, model=Model.LLAMA_3_1_8B)

        model_data.display_name = "Llama 3.1 (8B)"
        model_data.supports_input_image = False

        with pytest.raises(
            ModelDoesNotSupportMode,
            match=re.escape("Llama 3.1 (8B) is unable to process images"),
        ):
            await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
                TemplateName.V2_DEFAULT,
                {"file": {"content_type": "application/pdf", "data": "some_data"}},
                mock_provider,
                model_data,
            )

        mock_convert_from_bytes.assert_not_called()

    @patch("pdf2image.convert_from_bytes")
    async def test_run_with_pdf_and_supported_images(
        self,
        mock_convert_from_bytes: Mock,
        mock_provider: Mock,
        model_data: ModelData,
    ) -> None:
        class PdfSummaryTaskInput(BaseModel):
            file: File

        task = test_models.task_variant(input_model=PdfSummaryTaskInput, output_model=PdfSummaryTaskInput)

        runner = _build_runner(task=task, model=Model.LLAMA_3_1_8B)

        model_data.display_name = "Llama 3.1 (8B)"
        model_data.supports_input_image = False

        with pytest.raises(
            ModelDoesNotSupportMode,
            match=re.escape("Llama 3.1 (8B) is unable to process images"),
        ):
            await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
                TemplateName.V2_DEFAULT,
                {"file": {"content_type": "application/pdf", "data": "some_data"}},
                mock_provider,
                model_data,
            )

        mock_convert_from_bytes.assert_not_called()

    @patch("pdf2image.convert_from_bytes")
    async def test_with_converted_pdf(
        self,
        mock_convert_from_bytes: Mock,
        mock_provider: Mock,
        model_data: ModelData,
    ) -> None:
        class PdfSummaryTaskInput(BaseModel):
            file: File

        task = test_models.task_variant(input_model=PdfSummaryTaskInput, output_model=PdfSummaryTaskInput)

        runner = _build_runner(task=task, model=Model.GPT_4O_2024_11_20)

        model_data.display_name = "Llama 3.1 (8B)"
        model_data.supports_input_image = True

        mock_convert_from_bytes.return_value = [
            Image.new("RGB", (1, 1), color="red"),
            Image.new("RGB", (1, 1), color="blue"),
        ]

        msgs = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            {"file": {"content_type": "application/pdf", "data": "some_data"}},
            mock_provider,
            model_data,
        )

        assert len(msgs) == 2
        assert msgs[1].files is not None and len(msgs[1].files) == 2
        assert msgs[1].files[0].content_type == "image/jpeg"
        assert msgs[1].files[1].content_type == "image/jpeg"
        assert msgs[1].files[0].data
        assert msgs[1].files[1].data

        mock_convert_from_bytes.assert_called_once()

    async def test_with_text_files(
        self,
        httpx_mock: HTTPXMock,
        mock_download_file: AsyncMock,
        mock_provider: Mock,
        model_data: ModelData,
    ) -> None:
        # Resetting the download file mock because we will be using httpx mock
        from core.runners.workflowai.utils import download_file

        mock_download_file.side_effect = download_file

        def _requires_downloading_file_side_effect(file: File, model: Model):
            return not file.is_image

        mock_provider.requires_downloading_file.side_effect = _requires_downloading_file_side_effect

        class SummaryTaskInput(BaseModel):
            files: list[File]

        task = test_models.task_variant(input_model=SummaryTaskInput, output_model=SummaryTaskInput)

        runner = _build_runner(task=task, model=Model.GPT_4O_2024_11_20)

        httpx_mock.add_response(url="https://mock_url_1.com/some.txt", content=b"some_data")

        msgs = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            {
                "files": [
                    {"url": "https://mock_url_1.com/hello.png"},
                    {"url": "https://mock_url_1.com/some.txt"},
                ],
            },
            mock_provider,
            model_data,
        )
        assert len(msgs) == 2
        assert msgs[1].files == [
            FileWithKeyPath(content_type="image/png", url="https://mock_url_1.com/hello.png", key_path=["files", 0]),
        ]
        assert "some_data" in msgs[1].content

    async def test_input_schema_removal_with_single_file(
        self,
        mock_provider: Mock,
        model_data: ModelData,
    ) -> None:
        """Test that input schema is removed when there's a single file input"""

        class SingleFileTaskInput(BaseModel):
            file: File

        task = test_models.task_variant(input_model=SingleFileTaskInput, output_model=SingleFileTaskInput)

        runner = _build_runner(task=task, model=Model.GPT_4O_2024_11_20)

        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            {"file": {"content_type": "image/png", "data": "some_data"}},
            mock_provider,
            model_data,
        )

        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert "Input will be provided in the user message" not in messages[0].content
        assert messages[1].role == MessageDeprecated.Role.USER
        assert messages[1].content == "Input is a single file"
        assert messages[1].files is not None and len(messages[1].files) == 1

    async def test_input_schema_removal_with_array_of_file(
        self,
        mock_provider: Mock,
        model_data: ModelData,
    ) -> None:
        """Test that input schema is removed when there's a single file input"""

        class ArrayOfFileTaskInput(BaseModel):
            files: list[File]

        runner = _build_runner(
            task=test_models.task_variant(input_model=ArrayOfFileTaskInput, output_model=ArrayOfFileTaskInput),
        )

        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            ArrayOfFileTaskInput(files=[File(content_type="image/png", data="some_data")]).model_dump(),
            mock_provider,
            model_data,
        )

        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert "Input will be provided in the user message" not in messages[0].content
        assert messages[1].role == MessageDeprecated.Role.USER
        assert messages[1].content == "Input is an array of files"
        assert messages[1].files is not None and len(messages[1].files) == 1

    async def test_input_schema_kept_with_array_of_files_and_other_fields(
        self,
        mock_provider: Mock,
        model_data: ModelData,
    ) -> None:
        """Test that input schema is kept when there are multiple files"""

        class MultiFileTaskInput(BaseModel):
            files: list[File]
            description: str

        runner = _build_runner(task=test_models.task_variant(input_model=MultiFileTaskInput))

        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            MultiFileTaskInput(
                files=[
                    File(content_type="image/png", data="dat1"),
                    File(content_type="image/png", data="dat2"),
                ],
                description="test",
            ).model_dump(),
            mock_provider,
            model_data,
        )

        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert "Input will be provided in the user message" in messages[0].content
        assert messages[1].role == MessageDeprecated.Role.USER
        assert messages[1].content.startswith("Input is:")
        assert messages[1].files is not None and len(messages[1].files) == 2

    async def test_input_schema_kept_with_single_file_and_other_fields(
        self,
        mock_provider: Mock,
        model_data: ModelData,
    ) -> None:
        """Test that input schema is kept when there's a single file but also other fields"""

        class ComplexFileTaskInput(BaseModel):
            file: File
            description: str

        runner = _build_runner(task=test_models.task_variant(input_model=ComplexFileTaskInput))

        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            ComplexFileTaskInput(
                file=File(content_type="image/png", data="some_data"),
                description="test description",
            ).model_dump(),
            mock_provider,
            model_data,
        )

        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert "Input will be provided in the user message" in messages[0].content
        assert messages[1].role == MessageDeprecated.Role.USER
        assert messages[1].content.startswith("Input is:")
        assert messages[1].files is not None and len(messages[1].files) == 1

    async def test_input_schema_kept_with_text_files(
        self,
        mock_provider: Mock,
        model_data: ModelData,
    ) -> None:
        """Test that input schema is kept when files are inlined"""

        class TextFileTaskInput(BaseModel):
            file: File

        runner = _build_runner(task=test_models.task_variant(input_model=TextFileTaskInput))

        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            TextFileTaskInput(
                file=File(content_type="text/plain", data="dGV4dF9kYXRh"),
            ).model_dump(),  # "text_data" in base64
            mock_provider,
            model_data,
        )

        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert "Input will be provided in the user message" in messages[0].content
        assert messages[1].role == MessageDeprecated.Role.USER
        assert messages[1].content.startswith("Input is:")
        assert messages[1].files is None

    async def test_templated_instructions_all_consumed(self, mock_provider: Mock, model_data: ModelData):
        runner = _build_runner(
            properties=TaskGroupProperties(model=Model.GPT_4O_LATEST, instructions="Hello, {{ input }}!"),
        )
        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            _HelloTaskInput(input="world").model_dump(),
            mock_provider,
            model_data,
        )
        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert (
            messages[0].content
            == """<instructions>
Hello, world!
</instructions>

Return a single JSON object enforcing the following schema:
```json
{
  "type": "object",
  "properties": {
    "output": {
      "type": "integer"
    }
  },
  "required": [
    "output"
  ]
}
```"""
        )
        assert messages[1].role == MessageDeprecated.Role.USER
        assert messages[1].content == "Follow the instructions"

    async def test_templated_instructions_some_consumed(self, mock_provider: Mock, model_data: ModelData):
        class _TestInput(_HelloTaskInput):
            other_field: str

        runner = _build_runner(
            task=test_models.task_variant(input_model=_TestInput),
            properties=TaskGroupProperties(model=Model.GPT_4O_LATEST, instructions="Hello, {{ input }}!"),
        )

        messages = await runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            _TestInput(input="world", other_field="other").model_dump(),
            mock_provider,
            model_data,
        )

        assert len(messages) == 2
        assert messages[0].role == MessageDeprecated.Role.SYSTEM
        assert (
            messages[0].content
            == """<instructions>
Hello, world!
</instructions>

Input will be provided in the user message using a JSON following the schema:
```json
{
  "properties": {
    "other_field": {
      "title": "Other Field",
      "type": "string"
    }
  },
  "required": [
    "other_field"
  ],
  "title": "_TestInput",
  "type": "object"
}
```

Return a single JSON object enforcing the following schema:
```json
{
  "type": "object",
  "properties": {
    "output": {
      "type": "integer"
    }
  },
  "required": [
    "output"
  ]
}
```"""
        )
        assert messages[1].role == MessageDeprecated.Role.USER
        assert (
            messages[1].content
            == """Input is:
```json
{
  "other_field": "other"
}
```"""
        )


@pytest.mark.parametrize("require_download", [True, False])
async def test_download_file_before_request(
    patched_runner: WorkflowAIRunner,
    mock_download_file: AsyncMock,
    mock_task: Mock,
    mock_provider: Mock,
    require_download: bool,
    model_data: ModelData,
):
    mock_task.input_schema.json_schema = {
        "$defs": {
            "File": {"type": "object", "properties": {"url": {"type": "string"}}},
        },
        "properties": {
            "file": {"$ref": "#/$defs/File"},
        },
    }

    mock_provider.requires_downloading_file.return_value = require_download

    def download_side_effect(file: File) -> None:
        assert file == FileWithKeyPath(content_type="image/png", url="some_url", key_path=["file"])
        file.data = "some_data"

    mock_download_file.side_effect = download_side_effect

    with patch.object(patched_runner, "_check_support_for_files", return_value=None):
        await patched_runner._build_messages(  # pyright: ignore [reportPrivateUsage]
            TemplateName.V2_DEFAULT,
            {"file": {"content_type": "image/png", "url": "some_url"}},
            mock_provider,
            model_data,
        )

    if require_download:
        mock_download_file.assert_awaited_once()
    else:
        mock_download_file.assert_not_called()


class TestStreamTaskOutputFromToolCalls:
    async def test_non_streamable_provider(self, patched_runner: WorkflowAIRunner, mock_provider: Mock):
        """Test when provider doesn't support streaming"""
        mock_provider.is_streamable.return_value = False
        mock_output = {"output": "test"}

        with patch.object(
            patched_runner,
            "_build_task_output_from_messages",
            return_value=mock_output,
        ):
            results = [
                output
                async for output in patched_runner._stream_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
                    mock_provider,
                    ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
                    [],
                )
            ]

        assert results == [mock_output]
        mock_provider.stream.assert_not_called()

    async def test_stream_without_tool_calls(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
    ):
        """Test normal streaming without tool calls"""
        mock_provider.is_streamable.return_value = True
        mock_provider.stream.return_value = mock_aiter(
            StructuredOutput({"partial": "test"}),
            StructuredOutput({"output": "final"}, final=True),
        )

        results = [
            output
            async for output in patched_runner._stream_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
                mock_provider,
                ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
                [],
            )
        ]

        assert results == [
            RunOutput({"partial": "test"}),
            RunOutput({"output": "final"}, final=True),
        ]
        mock_provider.stream.assert_called_once()

    async def test_stream_with_tool_calls(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
        mock_tool_fn: Mock,
    ):
        mock_provider.is_streamable.return_value = True

        # First iteration: returns tool calls
        tool_call = ToolCallRequestWithID(tool_name="test_tool", tool_input_dict={"arg": "value"})
        mock_provider.stream.side_effect = [
            mock_aiter(StructuredOutput({}, [tool_call])),
            mock_aiter(StructuredOutput({"output": "final"}, final=True)),
        ]

        # Mock tool call execution

        results = [
            output
            async for output in patched_runner._stream_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
                mock_provider,
                ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
                [
                    MessageDeprecated(role=MessageDeprecated.Role.USER, content="test"),
                    MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="test"),
                ],
            )
        ]

        assert results == [
            # First stream we got the tool call but it has not been executed yet
            RunOutput({}, [ToolCall(tool_name="test_tool", tool_input_dict={"arg": "value"})]),
            RunOutput(
                {"output": "final"},
                [
                    ToolCall(
                        tool_name="test_tool",
                        tool_input_dict={"arg": "value"},
                        id="test_tool_e312bc5d1e6d438ef797c2ad859dc6f4",
                        result="success",
                        error=None,
                    ),
                ],
                final=True,
            ),
        ]
        assert mock_provider.stream.call_count == 2

    async def test_max_tool_call_iterations(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
        mock_tool_fn: Mock,
    ):
        """Test that exceeding max tool call iterations raises error"""
        mock_provider.is_streamable.return_value = True

        # Always return a tool call to force iteration

        def _tool_call(idx: int):
            return ToolCallRequestWithID(tool_name="test_tool", tool_input_dict={"arg": f"value_{idx}"})

        mock_provider.stream.side_effect = [
            mock_aiter(StructuredOutput({}, [_tool_call(i)])) for i in range(MAX_TOOL_CALL_ITERATIONS)
        ]

        # Mock tool call execution

        with pytest.raises(MaxToolCallIterationError):
            async for _ in patched_runner._stream_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
                mock_provider,
                ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
                [
                    MessageDeprecated(role=MessageDeprecated.Role.USER, content="test"),
                    MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="test"),
                ],
            ):
                pass

        # Should be called MAX_TOOL_CALL_ITERATIONS times
        assert mock_provider.stream.call_count == 10  # Assuming MAX_TOOL_CALL_ITERATIONS = 10


class TestBuildTaskOutputFromMessages:
    async def test_without_tool_calls(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
    ):
        """Test completion without any tool calls"""
        mock_provider.complete.return_value = StructuredOutput({"output": "test"})

        result = await patched_runner._build_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
            mock_provider,
            ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
            [],
        )

        assert result == RunOutput({"output": "test"}, final=True)
        mock_provider.complete.assert_called_once()

    async def test_with_tool_calls(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
        mock_tool_fn: Mock,
    ):
        """Test completion with tool calls that eventually succeed"""
        # First call returns tool calls, second call returns final output

        tool_call = ToolCallRequestWithID(tool_name="test_tool", tool_input_dict={"arg": "value"})

        mock_provider.complete.side_effect = [
            StructuredOutput({}, [tool_call]),
            StructuredOutput({"output": "final"}),
        ]

        # Mock tool call execution

        result = await patched_runner._build_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
            mock_provider,
            ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
            [
                MessageDeprecated(role=MessageDeprecated.Role.USER, content="test"),
                MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="test"),
            ],
        )

        assert result == RunOutput(
            task_output={"output": "final"},
            tool_calls=[
                ToolCall(tool_name="test_tool", tool_input_dict={"arg": "value"}, result="success"),
            ],
            final=True,
        )
        assert mock_provider.complete.call_count == 2

    async def test_max_iterations_exceeded(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
        mock_tool_fn: Mock,
    ):
        """Test that exceeding max tool call iterations raises error"""

        # Always return a tool call to force iteration
        def _tool_call(idx: int):
            return ToolCallRequestWithID(tool_name="test_tool", tool_input_dict={"arg": f"value_{idx}"})

        mock_provider.complete.side_effect = [
            StructuredOutput({}, [_tool_call(idx)]) for idx in range(MAX_TOOL_CALL_ITERATIONS)
        ]

        # Mock tool call execution
        with pytest.raises(MaxToolCallIterationError):
            await patched_runner._build_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
                mock_provider,
                ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
                [
                    MessageDeprecated(role=MessageDeprecated.Role.USER, content="test"),
                    MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="test"),
                ],
            )

        assert mock_provider.complete.call_count == MAX_TOOL_CALL_ITERATIONS
        assert mock_tool_fn.call_count == MAX_TOOL_CALL_ITERATIONS


def _tool(name: str):
    return Tool(name=name, input_schema={}, output_schema={}, description="")


@pytest.fixture
def mock_failing_tool() -> Mock:
    return AsyncMock(side_effect=RuntimeError("runtime error"))


class TestRunToolCalls:
    @pytest.fixture
    def mock_success_tool(self) -> Mock:
        return AsyncMock(return_value="success")

    @pytest.fixture(autouse=True)
    def patched_enabled_tools(
        self,
        patched_runner: WorkflowAIRunner,
        mock_success_tool: Mock,
        mock_failing_tool: Mock,
    ):
        tools = {
            "success_tool": InternalTool(_tool("success_tool"), mock_success_tool),
            "failing_tool": InternalTool(_tool("failing_tool"), mock_failing_tool),
        }
        with patch.object(
            patched_runner,
            "_enabled_internal_tools",
            new=tools,  # pyright: ignore[reportUnknownLambdaType]
        ):
            yield tools

    async def test_successful_tool_execution(
        self,
        patched_runner: WorkflowAIRunner,
        mock_success_tool: Mock,
    ):
        """Test successful execution of tool calls"""

        tool_call = ToolCallRequestWithID(tool_name="success_tool", tool_input_dict={"arg": "value"})

        results = await patched_runner._run_tool_calls([tool_call], messages=[])  # pyright: ignore[reportPrivateUsage]

        assert len(results) == 1
        assert results[0].tool_name == "success_tool"
        assert results[0].tool_input_dict == {"arg": "value"}
        assert results[0].result == "success"
        assert results[0].error is None

        mock_success_tool.assert_called_once_with(arg="value")

    async def test_failed_tool_execution(
        self,
        patched_runner: WorkflowAIRunner,
        mock_failing_tool: Mock,
    ):
        """Test handling of failed tool execution"""

        tool_call = ToolCallRequestWithID(tool_name="failing_tool", tool_input_dict={"arg": "value"})

        results = await patched_runner._run_tool_calls([tool_call], messages=[])  # pyright: ignore[reportPrivateUsage]

        assert len(results) == 1
        assert results[0].tool_name == "failing_tool"
        assert results[0].tool_input_dict == {"arg": "value"}
        assert results[0].result is None
        assert results[0].error == "RuntimeError: runtime error"

        mock_failing_tool.assert_called_once_with(arg="value")

    async def test_tool_not_found(self, patched_runner: WorkflowAIRunner):
        """Test handling of non-existent tool"""
        tool_call = ToolCallRequestWithID(tool_name="nonexistent_tool", tool_input_dict={"arg": "value"})

        results = await patched_runner._run_tool_calls([tool_call], messages=[])  # pyright: ignore[reportPrivateUsage]

        assert len(results) == 1
        assert results[0].tool_name == "nonexistent_tool"
        assert results[0].tool_input_dict == {"arg": "value"}
        assert results[0].result is None
        assert (
            results[0].error == "Tool 'nonexistent_tool' does not exist. Existing tools are: success_tool, failing_tool"
        )

    async def test_multiple_tool_calls(
        self,
        patched_runner: WorkflowAIRunner,
        mock_success_tool: Mock,
        mock_failing_tool: Mock,
    ):
        """Test execution of multiple tool calls with mixed results"""

        tool_calls = [
            ToolCallRequestWithID(tool_name="success_tool", tool_input_dict={"arg": "value1"}),
            ToolCallRequestWithID(tool_name="failing_tool", tool_input_dict={"arg": "value2"}),
            ToolCallRequestWithID(tool_name="success_tool", tool_input_dict={"arg": "value3"}),
        ]

        results = await patched_runner._run_tool_calls(tool_calls, messages=[])  # pyright: ignore[reportPrivateUsage]

        assert len(results) == 3

        # First tool call - success
        assert results[0].tool_name == "success_tool"
        assert results[0].tool_input_dict == {"arg": "value1"}
        assert results[0].result == "success"
        assert results[0].error is None

        # Second tool call - failure
        assert results[1].tool_name == "failing_tool"
        assert results[1].tool_input_dict == {"arg": "value2"}
        assert results[1].result is None
        assert results[1].error == "RuntimeError: runtime error"

        # Third tool call - success
        assert results[2].tool_name == "success_tool"
        assert results[2].tool_input_dict == {"arg": "value3"}
        assert results[2].result == "success"
        assert results[2].error is None

        assert mock_success_tool.call_count == 2
        call_args = sorted(mock_success_tool.call_args_list, key=lambda x: x[1]["arg"])
        assert call_args[0][1] == {"arg": "value1"}
        assert call_args[1][1] == {"arg": "value3"}

        mock_failing_tool.assert_called_once_with(arg="value2")

    async def test_tool_call_repeated_tool_calls(
        self,
        patched_runner: WorkflowAIRunner,
        mock_success_tool: Mock,
        patched_enabled_tools: None,
    ):
        tool_calls = [ToolCallRequestWithID(tool_name="success_tool", tool_input_dict={"arg": "value1"})]

        results = await patched_runner._run_tool_calls(tool_calls, messages=[])  # pyright: ignore[reportPrivateUsage]
        assert len(results) == 1
        assert results[0].tool_name == "success_tool"
        assert results[0].tool_input_dict == {"arg": "value1"}
        assert results[0].result == "success"
        assert results[0].error is None
        mock_success_tool.assert_called_once_with(arg="value1")

        mock_success_tool.reset_mock()
        # Now call the same tool again but with a different input
        tool_calls = [
            ToolCallRequestWithID(tool_name="success_tool", tool_input_dict={"arg": "value1"}),
            ToolCallRequestWithID(tool_name="success_tool", tool_input_dict={"arg": "value2"}),
        ]

        mock_success_tool.return_value = "success2"

        results = await patched_runner._run_tool_calls(tool_calls, messages=[])  # pyright: ignore[reportPrivateUsage]
        assert len(results) == 2

        assert results[0].result == "success"
        assert results[1].result == "success2"

        # The first tool call should be cached, so it should only have been called once
        mock_success_tool.assert_called_once_with(arg="value2")

        # Now try again, we should get a ToolCallRecursionError
        with pytest.raises(ToolCallRecursionError):
            await patched_runner._run_tool_calls(tool_calls, messages=[])  # pyright: ignore[reportPrivateUsage]


class TestOutputFactory:
    def test_output_factory(self, patched_runner: WorkflowAIRunner, mock_task: Mock):
        """Test that the output factory correctly handles invalid jsons"""

        txt = '{"meal_plan": "**Petit-déjeuner**\\n•\tAvoine avec des baies et du beurre d\'amande\\n•\t1/2 tasse de flocons d\'avoine (150 kcal, 27g de glucides, 5g de protéines, 3g de lipides)\\n•\t1/2 tasse de baies mélangées (40 kcal, 10g de glucides, 0,5g de protéines, 0,5g de lipides)\\n•\t1 cuillère à soupe de beurre d\'amande (100 kcal, 3g de glucides, 2g de protéines, 9g de lipides)\\n•\t1 tasse de lait écrémé (90 kcal, 12g de glucides, 8g de protéines, 0g de lipides)\\nTotal : 380 kcal, 52g de glucides, 15,5g de protéines, 12,5g de lipides\\n\\n**Déjeuner**\\n•\tSalade de quinoa avec des légumes rôtis\\n•\t1 tasse de quinoa cuit (220 kcal, 40g de glucides, 8g de protéines, 2g de lipides)\\n•\t1 tasse de légumes rôtis (100 kcal, 10g de glucides, 2g de protéines, 2g de lipides)\\n•\t2 cuillères à soupe de vinaigrette (100 kcal, 5g de glucides, 0g de protéines, 10g de lipides)\\nTotal : 420 kcal, 55g de glucides, 10g de protéines, 14g de lipides\\n\\n**Dîner**\\n•\tCurry de lentilles avec du riz brun\\n•\t1 tasse de lentilles cuites (230 kcal, 40g de glucides, 18g de protéines, 1g de lipides)\\n•\t1 tasse de riz brun cuit (220 kcal, 45g de glucides, 5g de protéines, 1g de lipides)\\n•\t1 tasse de curry de légumes (200 kcal, 20g de glucides, 5g de protéines, 5g de lipides)\\nTotal : 650 kcal, 105g de glucides, 28g de protéines, 7g de lipides"}\n'

        output = patched_runner.output_factory(txt)
        assert output.output == {
            "meal_plan": """**Petit-déjeuner**
•	Avoine avec des baies et du beurre d'amande
•	1/2 tasse de flocons d'avoine (150 kcal, 27g de glucides, 5g de protéines, 3g de lipides)
•	1/2 tasse de baies mélangées (40 kcal, 10g de glucides, 0,5g de protéines, 0,5g de lipides)
•	1 cuillère à soupe de beurre d'amande (100 kcal, 3g de glucides, 2g de protéines, 9g de lipides)
•	1 tasse de lait écrémé (90 kcal, 12g de glucides, 8g de protéines, 0g de lipides)
Total : 380 kcal, 52g de glucides, 15,5g de protéines, 12,5g de lipides

**Déjeuner**
•	Salade de quinoa avec des légumes rôtis
•	1 tasse de quinoa cuit (220 kcal, 40g de glucides, 8g de protéines, 2g de lipides)
•	1 tasse de légumes rôtis (100 kcal, 10g de glucides, 2g de protéines, 2g de lipides)
•	2 cuillères à soupe de vinaigrette (100 kcal, 5g de glucides, 0g de protéines, 10g de lipides)
Total : 420 kcal, 55g de glucides, 10g de protéines, 14g de lipides

**Dîner**
•	Curry de lentilles avec du riz brun
•	1 tasse de lentilles cuites (230 kcal, 40g de glucides, 18g de protéines, 1g de lipides)
•	1 tasse de riz brun cuit (220 kcal, 45g de glucides, 5g de protéines, 1g de lipides)
•	1 tasse de curry de légumes (200 kcal, 20g de glucides, 5g de protéines, 5g de lipides)
Total : 650 kcal, 105g de glucides, 28g de protéines, 7g de lipides""",
        }

        assert mock_task.validate_output.call_count == 1
        assert mock_task.validate_output.call_args[0][0] == output.output

    def test_invalid_json(self, patched_runner: WorkflowAIRunner, mock_task: Mock):
        """Test that we raise the correct error when the json is invalid"""

        txt = '{"meal_plan: "hello"}'
        with pytest.raises(JSONSchemaValidationError):
            patched_runner.output_factory(txt)

        mock_task.validate_output.assert_not_called()

    def test_dirty_json(self, patched_runner: WorkflowAIRunner, mock_task: Mock):
        txt = '{\\n  "filtered_contacts": [\\n    {\\n      "contact_user_id": "USR82132"\\n     },\\n    {\\n      "contact_user_id": "USR90234"\\n    }\\n  ]\\n}'

        raw = patched_runner.output_factory(txt)
        assert raw.output == {"filtered_contacts": [{"contact_user_id": "USR82132"}, {"contact_user_id": "USR90234"}]}
        assert raw.tool_calls is None
        assert raw.reasoning_steps is None
        assert raw.agent_run_result is None

    def test_invalid_unicode_chars(self, patched_runner: WorkflowAIRunner):
        txt = '{"hello": "hello\\u000009"}'
        output = patched_runner.output_factory(txt)
        assert output.output == {"hello": "hello\t"}


class TestInit:
    def test_raises_error_if_provider_does_not_support_model(self, mock_task: Mock):
        with pytest.raises(ProviderDoesNotSupportModelError):
            WorkflowAIRunner(
                task=mock_task,
                properties=TaskGroupProperties(model=Model.GPT_4O_MINI_2024_07_18, provider=Provider.GOOGLE),
            )

    # TODO[models]: this test relies on actual model data. it should be patched instead
    def test_deprecated_model(self, mock_task: Mock):
        # Check that when we init the runner with a deprecated model, the replacement model is used
        # in its place
        runner = WorkflowAIRunner(
            task=mock_task,
            properties=TaskGroupProperties(model=Model.GPT_3_5_TURBO_1106),
        )
        assert runner._options.model == Model.GPT_4O_MINI_2024_07_18  # pyright: ignore[reportPrivateUsage]
        assert runner.properties.model == Model.GPT_4O_MINI_2024_07_18  # pyright: ignore[reportPrivateUsage]

    # TODO[models]: this test relies on actual model data. it should be patched instead
    def test_latest_model(self, mock_task: Mock):
        # Check that when we init the runner with a latest model, the value remains
        # the latest model
        runner = WorkflowAIRunner(
            task=mock_task,
            properties=TaskGroupProperties(model=Model.GPT_4O_LATEST),
        )
        assert runner._options.model == Model.GPT_4O_LATEST  # pyright: ignore[reportPrivateUsage]
        assert runner.properties.model == Model.GPT_4O_LATEST  # pyright: ignore[reportPrivateUsage]


@pytest.fixture()
def mock_provider_factory_full(mock_provider_factory: Mock):
    from core.providers.base.abstract_provider import AbstractProvider

    def _mock_provider(name: Provider):
        m = Mock(spec=AbstractProvider)
        m.config_id = None
        m.requires_downloading_file.return_value = False
        m.sanitize_template.side_effect = lambda x: x  # pyright: ignore[reportUnknownLambdaType]
        m.sanitize_agent_instructions.side_effect = lambda x: x  # pyright: ignore[reportUnknownLambdaType]
        m.name.return_value = name
        m.max_number_of_file_urls = None
        return m

    google = _mock_provider(Provider.GOOGLE)
    google_imagen = _mock_provider(Provider.GOOGLE_IMAGEN)
    gemini = _mock_provider(Provider.GOOGLE_GEMINI)
    openai = _mock_provider(Provider.OPEN_AI)
    anthropic = _mock_provider(Provider.ANTHROPIC)
    bedrock = _mock_provider(Provider.AMAZON_BEDROCK)
    azure_openai = _mock_provider(Provider.AZURE_OPEN_AI)

    def _side_effect(provider: Provider):
        if provider == Provider.GOOGLE:
            return google
        if provider == Provider.GOOGLE_GEMINI:
            return gemini
        if provider == Provider.OPEN_AI:
            return openai
        if provider == Provider.ANTHROPIC:
            return anthropic
        if provider == Provider.AMAZON_BEDROCK:
            return bedrock
        if provider == Provider.AZURE_OPEN_AI:
            return azure_openai
        if provider == Provider.GOOGLE_IMAGEN:
            return google_imagen
        assert False, "Invalid provider"

    mock_provider_factory.get_provider.side_effect = _side_effect
    mock_provider_factory.get_providers.side_effect = lambda p: [_side_effect(p)]  # pyright: ignore
    mock_provider_factory.google = google
    mock_provider_factory.gemini = gemini
    mock_provider_factory.openai = openai
    mock_provider_factory.anthropic = anthropic
    mock_provider_factory.bedrock = bedrock
    mock_provider_factory.azure_openai = azure_openai
    mock_provider_factory.google_imagen = google_imagen

    return mock_provider_factory


@pytest.fixture()
def patched_provider_factory(mock_provider_factory_full: Mock, patched_runner: WorkflowAIRunner):
    with patch.object(patched_runner, "provider_factory", new=mock_provider_factory_full):
        yield mock_provider_factory_full


class TestBuildTaskOutput:
    # TODO: this test relies actual model data. it should be patched instead
    # Otherwise we will have to change it every time we change the model data

    async def test_provider_failover(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
    ):
        patched_runner._options.model = Model.GEMINI_1_5_FLASH_002  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.google.complete.side_effect = ProviderInternalError()
        patched_provider_factory.gemini.complete.return_value = StructuredOutput(
            {"output": "final"},
        )

        result = await patched_runner._build_task_output({"input": "test"})  # pyright: ignore[reportPrivateUsage]
        assert result == RunOutput({"output": "final"}, final=True)

        patched_provider_factory.google.complete.assert_awaited_once()
        first_opts = patched_provider_factory.google.complete.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        # Google does not support structured generation
        assert first_opts.structured_generation is False

        patched_provider_factory.gemini.complete.assert_awaited_once()

    async def test_provider_failover_with_structured_generation(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
    ):
        # OpenAI supports structured generation
        patched_runner._options.model = Model.GPT_4O_MINI_2024_07_18  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.is_structured_generation_enabled = None  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.openai.complete.side_effect = [
            StructuredGenerationError(),
            StructuredOutput({"output": "final"}),
        ]

        result = await patched_runner._build_task_output({"input": "test"})  # pyright: ignore[reportPrivateUsage]
        assert result == RunOutput({"output": "final"}, final=True)

        assert patched_provider_factory.openai.complete.await_count == 2

        first_opts = patched_provider_factory.openai.complete.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        assert first_opts.structured_generation is True

        second_opts = patched_provider_factory.openai.complete.call_args_list[1].args[1]
        assert isinstance(second_opts, ProviderOptions), "sanity check"
        assert second_opts.structured_generation is False

    async def test_provider_failover_with_structured_generation_forced(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
    ):
        # OpenAI supports structured generation
        patched_runner._options.model = Model.GPT_4O_MINI_2024_07_18  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.is_structured_generation_enabled = True  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.openai.complete.side_effect = [
            StructuredGenerationError(),
            StructuredOutput({"output": "final"}),
        ]

        with pytest.raises(StructuredGenerationError):
            await patched_runner._build_task_output({"input": "test"})  # pyright: ignore[reportPrivateUsage]

        assert patched_provider_factory.openai.complete.await_count == 1

        first_opts = patched_provider_factory.openai.complete.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        assert first_opts.structured_generation is True

    async def test_provider_failover_with_structured_generation_disabled(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
    ):
        # OpenAI supports structured generation
        patched_runner._options.model = Model.GPT_4O_MINI_2024_07_18  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.is_structured_generation_enabled = False  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.openai.complete.return_value = StructuredOutput({"output": "final"})
        result = await patched_runner._build_task_output({"input": "test"})  # pyright: ignore[reportPrivateUsage]
        assert result == RunOutput({"output": "final"}, final=True)

        assert patched_provider_factory.openai.complete.await_count == 1

        first_opts = patched_provider_factory.openai.complete.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        assert first_opts.structured_generation is False

    async def test_provider_sanitizes_template(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
    ):
        patched_runner._options.model = Model.GPT_4O_MINI_2024_07_18  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]

        def _sanitize_template(template: TemplateName):
            assert template != TemplateName.V1, "sanity check"
            return TemplateName.V1

        patched_provider_factory.openai.sanitize_template.side_effect = _sanitize_template  # pyright: ignore[reportUnknownLambdaType]
        patched_provider_factory.openai.complete.return_value = StructuredOutput(
            {"output": "final"},
        )

        result = await patched_runner._build_task_output({"input": "test"})  # pyright: ignore[reportPrivateUsage]
        assert result == RunOutput({"output": "final"}, final=True)

        patched_provider_factory.openai.sanitize_template.assert_called_once()
        messages = patched_provider_factory.openai.complete.call_args_list[0].args[0]
        # As a genius expert is not in not v1 tempaltes
        assert "<instructions>" in messages[0].content

    async def test_provider_failover_with_different_modes(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        mock_task: Mock,
    ):
        mock_task.input_schema.json_schema = {
            "$defs": {
                "File": File.model_json_schema(),
            },
            "type": "object",
            "properties": {
                "file": {"$ref": "#/$defs/File"},
            },
        }
        # Sonnet supports PDFs on Anthropic but not bedrock
        patched_runner._options.model = Model.CLAUDE_3_5_SONNET_20241022  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.anthropic.complete.return_value = StructuredOutput(
            {"output": "final"},
        )

        result = await patched_runner._build_task_output(  # pyright: ignore[reportPrivateUsage]
            {
                "file": {
                    "content_type": "application/pdf",
                    "data": "test",
                },
            },
        )
        assert result == RunOutput({"output": "final"}, final=True)
        patched_provider_factory.anthropic.complete.assert_called_once()
        patched_provider_factory.bedrock.complete.assert_not_called()

    async def test_with_latest_model(self, patched_runner: WorkflowAIRunner, patched_provider_factory: Mock):
        patched_runner._options.model = Model.GPT_4O_LATEST  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.openai.complete.return_value = StructuredOutput(
            {"output": "final"},
        )

        result = await patched_runner._build_task_output({"input": "test"})  # pyright: ignore[reportPrivateUsage]
        assert result == RunOutput({"output": "final"}, final=True)

        patched_provider_factory.openai.complete.assert_called_once()
        first_opts = patched_provider_factory.openai.complete.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        assert first_opts.model != Model.GPT_4O_LATEST, "sanity check"
        latest_model_data = MODEL_DATAS[Model.GPT_4O_LATEST]
        assert isinstance(latest_model_data, LatestModel), "sanity check"
        # Avoiding hardcoding the latest model data to avoid breaking the test when the model data changes
        assert first_opts.model == latest_model_data.model

    async def test_tool_calls(
        self,
        patched_runner: WorkflowAIRunner,
        mock_tool_fn: Mock,
        patched_provider_factory: Mock,
    ):
        patched_runner._options.model = Model.GPT_4O_LATEST  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.openai.complete.side_effect = [
            StructuredOutput({}, [ToolCallRequestWithID(tool_name="test_tool", tool_input_dict={"input": "test"})]),
            StructuredOutput({"output": "final"}),
        ]

        result = await patched_runner._build_task_output({"input": "test"})  # pyright: ignore[reportPrivateUsage]
        assert result == RunOutput(
            {"output": "final"},
            tool_calls=[
                ToolCall(tool_name="test_tool", tool_input_dict={"input": "test"}, result="success"),
            ],
            final=True,
        )

        mock_tool_fn.assert_called_once_with(input="test")
        assert patched_provider_factory.openai.complete.call_count == 2

        messages: list[MessageDeprecated] = patched_provider_factory.openai.complete.call_args_list[0].args[0]
        assert len(messages) == 2

        # TODO[tools]: change to account for assistant message
        messages: list[MessageDeprecated] = patched_provider_factory.openai.complete.call_args_list[1].args[0]
        assert len(messages) == 4
        assert messages[-1].tool_call_results == [
            ToolCall(
                id="test_tool_1083d5219ffb2795075d79acf18e7a46",
                tool_name="test_tool",
                tool_input_dict={"input": "test"},
                result="success",
                error=None,
            ),
        ]

    async def test_message_appending(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
        mock_tool_fn: Mock,
    ):
        """Test that messages are correctly appended with tool calls and results"""
        initial_messages = [
            MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="system message"),
            MessageDeprecated(role=MessageDeprecated.Role.USER, content="user message"),
        ]

        tool_call = ToolCallRequestWithID(tool_name="test_tool", tool_input_dict={"arg": "value"})
        mock_provider.complete.side_effect = [
            StructuredOutput({}, [tool_call]),
            StructuredOutput({"output": "final"}),
        ]

        await patched_runner._build_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
            mock_provider,
            ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
            initial_messages,
        )

        # Check first complete call - should be with initial messages
        first_call_messages = mock_provider.complete.call_args_list[0].args[0]
        assert len(first_call_messages) == 2
        assert first_call_messages == initial_messages

        # Check second complete call - should include tool call and result
        second_call_messages = mock_provider.complete.call_args_list[1].args[0]
        assert len(second_call_messages) == 4
        assert second_call_messages[0:2] == initial_messages  # Original messages preserved

        # Verify tool call message (assistant)
        assert second_call_messages[2].role == MessageDeprecated.Role.ASSISTANT
        assert len(second_call_messages[2].tool_call_requests) == 1
        assert second_call_messages[2].tool_call_requests[0].tool_name == "test_tool"
        assert second_call_messages[2].tool_call_requests[0].tool_input_dict == {"arg": "value"}

        # Verify tool result message (user)
        assert second_call_messages[3].role == MessageDeprecated.Role.USER
        assert len(second_call_messages[3].tool_call_results) == 1
        assert second_call_messages[3].tool_call_results[0].tool_name == "test_tool"
        assert second_call_messages[3].tool_call_results[0].tool_input_dict == {"arg": "value"}
        assert second_call_messages[3].tool_call_results[0].result == "success"
        assert second_call_messages[3].tool_call_results[0].error is None

    async def test_message_appending_multiple_tool_calls(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
        mock_tool_fn: Mock,
    ):
        """Test that multiple tool calls and results are correctly appended"""
        initial_messages = [
            MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="system message"),
            MessageDeprecated(role=MessageDeprecated.Role.USER, content="user message"),
        ]

        tool_calls = [
            ToolCallRequestWithID(tool_name="test_tool", tool_input_dict={"arg": "value1"}),
            ToolCallRequestWithID(tool_name="test_tool", tool_input_dict={"arg": "value2"}),
        ]
        mock_provider.complete.side_effect = [
            StructuredOutput({}, tool_calls),
            StructuredOutput({"output": "final"}),
        ]

        await patched_runner._build_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
            mock_provider,
            ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
            initial_messages,
        )

        # Check first complete call - should be with initial messages
        first_call_messages = mock_provider.complete.call_args_list[0].args[0]
        assert len(first_call_messages) == 2
        assert first_call_messages == initial_messages

        # Check second complete call - should include tool calls and results
        second_call_messages = mock_provider.complete.call_args_list[1].args[0]
        assert len(second_call_messages) == 4
        assert second_call_messages[0:2] == initial_messages  # Original messages preserved

        # Verify tool calls message (assistant)
        assert second_call_messages[2].role == MessageDeprecated.Role.ASSISTANT
        assert len(second_call_messages[2].tool_call_requests) == 2
        assert second_call_messages[2].tool_call_requests[0].tool_name == "test_tool"
        assert second_call_messages[2].tool_call_requests[0].tool_input_dict == {"arg": "value1"}
        assert second_call_messages[2].tool_call_requests[1].tool_name == "test_tool"
        assert second_call_messages[2].tool_call_requests[1].tool_input_dict == {"arg": "value2"}

        # Verify tool results message (user)
        assert second_call_messages[3].role == MessageDeprecated.Role.USER
        assert len(second_call_messages[3].tool_call_results) == 2
        assert second_call_messages[3].tool_call_results[0].tool_name == "test_tool"
        assert second_call_messages[3].tool_call_results[0].tool_input_dict == {"arg": "value1"}
        assert second_call_messages[3].tool_call_results[0].result == "success"
        assert second_call_messages[3].tool_call_results[0].error is None
        assert second_call_messages[3].tool_call_results[1].tool_name == "test_tool"
        assert second_call_messages[3].tool_call_results[1].tool_input_dict == {"arg": "value2"}

    async def test_message_appending_with_failed_tool(
        self,
        patched_runner: WorkflowAIRunner,
        mock_provider: Mock,
        mock_failing_tool: Mock,
    ):
        """Test that failed tool calls are correctly appended with error messages"""
        initial_messages = [
            MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="system message"),
            MessageDeprecated(role=MessageDeprecated.Role.USER, content="user message"),
        ]

        # Set up a failing tool
        patched_runner._enabled_internal_tools = {  # pyright: ignore[reportPrivateUsage]
            "failing_tool": InternalTool(_tool("failing_tool"), mock_failing_tool),
        }

        tool_call = ToolCallRequestWithID(tool_name="failing_tool", tool_input_dict={"arg": "value"})
        mock_provider.complete.side_effect = [
            StructuredOutput({}, [tool_call]),
            StructuredOutput({"output": "final"}),
        ]

        await patched_runner._build_task_output_from_messages(  # pyright: ignore[reportPrivateUsage]
            mock_provider,
            ProviderOptions(model=Model.GPT_4O_MINI_2024_07_18),
            initial_messages,
        )

        # Check second complete call - should include tool call and error result
        second_call_messages = mock_provider.complete.call_args_list[1].args[0]
        assert len(second_call_messages) == 4

        # Verify tool call message (assistant)
        assert second_call_messages[2].role == MessageDeprecated.Role.ASSISTANT
        assert len(second_call_messages[2].tool_call_requests) == 1
        assert second_call_messages[2].tool_call_requests[0].tool_name == "failing_tool"
        assert second_call_messages[2].tool_call_requests[0].tool_input_dict == {"arg": "value"}

        # Verify tool result message with error (user)
        assert second_call_messages[3].role == MessageDeprecated.Role.USER
        assert len(second_call_messages[3].tool_call_results) == 1
        assert second_call_messages[3].tool_call_results[0].tool_name == "failing_tool"
        assert second_call_messages[3].tool_call_results[0].tool_input_dict == {"arg": "value"}
        assert second_call_messages[3].tool_call_results[0].result is None
        assert second_call_messages[3].tool_call_results[0].error == "RuntimeError: runtime error"


class TestBuildProviderData:
    @pytest.fixture
    def model_data(self) -> FinalModelData:
        return FinalModelData(
            model=Model.GPT_4O_MINI_2024_07_18,
            supports_structured_output=True,
            supports_json_mode=True,
            supports_input_image=True,
            supports_input_pdf=True,
            supports_input_audio=True,
            display_name="Test GPT-4O Mini",
            icon_url="http://test.icon",
            max_tokens_data=MaxTokensData(source="test", max_tokens=1000),
            providers=[],
            release_date=date(2024, 1, 1),
            quality_index=100,
            speed_index=500,
            quality_data=QualityData(index=100),
            speed_data=SpeedData(
                index=SpeedIndex(value=500),
            ),
            provider_name=DisplayedProvider.OPEN_AI.value,
            supports_tool_calling=True,
            fallback=None,
        )

    def test_model_data_is_copied(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        model_data: FinalModelData,
    ):
        def side_effect(model_data: ModelData):
            model_data.supports_structured_output = False

        patched_provider_factory.azure_openai.sanitize_model_data.side_effect = side_effect
        patched_provider_factory.azure_openai.sanitize_template.side_effect = lambda x: x  # pyright: ignore[reportUnknownLambdaType]

        with patch.object(
            patched_runner,
            "_pick_template",
            return_value=TemplateName.V2_DEFAULT,
        ) as mock_pick_template:
            _, _, _, model_data_copy = patched_runner._build_provider_data(  # pyright: ignore[reportPrivateUsage]
                patched_provider_factory.azure_openai,
                model_data,
                True,
            )
        assert model_data_copy.supports_structured_output is False
        assert model_data.supports_structured_output is True
        assert mock_pick_template.call_args_list[0].args[2] is False

    async def test_build_provider_data_with_chain_of_thought_and_tools(
        self,
        mock_provider_factory_full: Mock,
        model_data: FinalModelData,
    ) -> None:
        """
        Test that build_provider_data adapts the output_schema to include reasoning steps (COT)
        and tool usage when the runner has chain_of_thought and tools enabled.
        """

        # Enable chain of thought and tool usage
        runner = _build_runner2(
            mock_provider_factory_full,
            {},
            {"properties": {}},
            "test",
            Model.GPT_4O_MINI_2024_07_18,
            is_chain_of_thought_enabled=True,
            enabled_tools=[ToolKind.WEB_SEARCH_GOOGLE],
        )

        runner._check_tool_calling_support = Mock()  # pyright: ignore[reportPrivateUsage]

        # Act: build provider data
        provider, _, provider_options, _ = runner._build_provider_data(  # pyright: ignore[reportPrivateUsage]
            mock_provider_factory_full.openai,
            model_data,
            is_structured_generation_enabled=True,
        )

        # Assert: provider should be instantiated, and output_schema should contain "steps" and "tools"
        assert provider is not None
        output_schema = provider_options.output_schema
        assert isinstance(output_schema, dict)
        assert "internal_reasoning_steps" in output_schema["properties"], (
            "Expected 'internal_reasoning_steps' property for chain-of-thought"
        )

    async def test_build_provider_data_without_chain_of_thought_and_tools(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        model_data: FinalModelData,
    ) -> None:
        """
        Test that build_provider_data does not modify the output_schema when chain_of_thought and tools are disabled.
        """

        # Disable chain of thought and tool usage
        patched_runner.properties.is_chain_of_thought_enabled = False
        patched_runner.properties.enabled_tools = []

        # Act: build provider data
        provider, _, provider_options, _ = patched_runner._build_provider_data(  # pyright: ignore[reportPrivateUsage]
            patched_provider_factory.openai,
            model_data,
            is_structured_generation_enabled=True,
        )

        # Assert: provider should be instantiated, and output_schema should contain "steps" and "tools"
        assert provider is not None
        output_schema = provider_options.output_schema
        assert isinstance(output_schema, dict)
        assert "internal_reasoning_steps" not in output_schema["properties"]
        assert "internal_tool_calls" not in output_schema["properties"]

    def test_all_provider_options_fields_are_set(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        model_data: FinalModelData,
    ):
        """Test that all fields are set in the provider options"""
        _, _, provider_options, _ = patched_runner._build_provider_data(  # pyright: ignore[reportPrivateUsage]
            patched_provider_factory.openai,
            model_data,
            is_structured_generation_enabled=True,
        )
        assert provider_options.model_fields_set == set(ProviderOptions.model_fields.keys())


class TestStreamTaskOutput:
    @pytest.fixture
    def stream_fn(self, patched_runner: WorkflowAIRunner):
        async def _stream_fn():
            return [
                c
                async for c in patched_runner._stream_task_output(  # pyright: ignore[reportPrivateUsage]
                    {"input": "test"},
                )
            ]

        return _stream_fn

    async def test_provider_failover(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        stream_fn: Callable[[], Awaitable[Any]],
    ):
        patched_runner._options.model = Model.GEMINI_1_5_FLASH_002  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.google.stream.side_effect = ProviderInternalError()
        patched_provider_factory.gemini.stream.return_value = mock_aiter(
            StructuredOutput({"output": "final"}, final=True),
        )

        results = await stream_fn()
        assert results == [RunOutput({"output": "final"}, final=True)]

        patched_provider_factory.google.stream.assert_called_once()
        first_opts = patched_provider_factory.google.stream.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        # Google does not support structured generation
        assert first_opts.structured_generation is False

        patched_provider_factory.gemini.stream.assert_called_once()

    async def test_provider_failover_with_structured_generation(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        stream_fn: Callable[[], Awaitable[Any]],
    ):
        # OpenAI supports structured generation
        patched_runner._options.model = Model.GPT_4O_MINI_2024_07_18  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.is_structured_generation_enabled = None  # pyright: ignore[reportPrivateUsage]

        def _side_effect(*args: Any, **kwargs: Any):
            assert isinstance(args[1], ProviderOptions), "sanity check"
            if args[1].structured_generation is True:
                raise StructuredGenerationError()
            return mock_aiter(StructuredOutput({"output": "final"}, final=True))

        patched_provider_factory.openai.stream.side_effect = _side_effect

        results = await stream_fn()
        assert results == [RunOutput({"output": "final"}, final=True)]

        assert patched_provider_factory.openai.stream.call_count == 2

        first_opts = patched_provider_factory.openai.stream.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        assert first_opts.structured_generation is True

        second_opts = patched_provider_factory.openai.stream.call_args_list[1].args[1]
        assert isinstance(second_opts, ProviderOptions), "sanity check"
        assert second_opts.structured_generation is False

    async def test_provider_failover_with_structured_generation_forced(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        stream_fn: Callable[[], Awaitable[Any]],
    ):
        # OpenAI supports structured generation
        patched_runner._options.model = Model.GPT_4O_MINI_2024_07_18  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.is_structured_generation_enabled = True  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.openai.stream.side_effect = StructuredGenerationError()

        with pytest.raises(StructuredGenerationError):
            await stream_fn()

        assert patched_provider_factory.openai.stream.call_count == 1

        first_opts = patched_provider_factory.openai.stream.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        assert first_opts.structured_generation is True

    async def test_provider_failover_with_structured_generation_disabled(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        stream_fn: Callable[[], Awaitable[Any]],
    ):
        # OpenAI supports structured generation
        patched_runner._options.model = Model.GPT_4O_MINI_2024_07_18  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.is_structured_generation_enabled = False  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.openai.stream.return_value = mock_aiter(
            StructuredOutput({"output": "final"}, final=True),
        )

        result = await stream_fn()  # pyright: ignore[reportPrivateUsage]
        assert result == [RunOutput({"output": "final"}, final=True)]

        assert patched_provider_factory.openai.stream.call_count == 1

        first_opts = patched_provider_factory.openai.stream.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        assert first_opts.structured_generation is False

    async def test_stream_task_output_with_multiple_providers(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        stream_fn: Callable[[], Awaitable[Any]],
    ):
        # Check that we stop at the first provider that succeeds

        patched_runner._options.model = Model.GEMINI_1_5_FLASH_002  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.google.stream.return_value = mock_aiter(
            StructuredOutput({"output": "final"}, final=False),
            StructuredOutput({"output": "final1"}, final=True),
        )
        patched_provider_factory.gemini.stream.return_value = mock_aiter(
            StructuredOutput({"output": "final2"}, final=True),
        )

        results = await stream_fn()
        assert results == [
            RunOutput({"output": "final"}),
            RunOutput({"output": "final1"}, final=True),
        ]

        patched_provider_factory.google.stream.assert_called_once()
        first_opts = patched_provider_factory.google.stream.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        # Google does not support structured generation
        assert first_opts.structured_generation is False

        patched_provider_factory.gemini.stream.assert_not_called()

    async def test_no_provider_available(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        stream_fn: Callable[[], Awaitable[Any]],
    ):
        # Check that we raise the first error
        patched_runner._options.model = Model.GEMINI_1_5_FLASH_002  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]

        patched_provider_factory.google.stream.side_effect = ProviderUnavailableError()
        patched_provider_factory.gemini.stream.side_effect = ProviderInternalError()
        # Model will fallback to OpenAI
        patched_provider_factory.openai.stream.side_effect = ProviderInternalError()

        with pytest.raises(ProviderUnavailableError):
            await stream_fn()


class TestBuildUserMessageContent:
    def test_with_regular_schema(self, patched_runner: WorkflowAIRunner):
        """Test that regular schema uses the template"""
        input_schema = {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "number": {"type": "integer"},
            },
        }
        input_copy = {"text": "hello", "number": 42}
        user_template = "Input is:\n{{input_data}}"

        result = patched_runner._build_user_message_content(  # pyright: ignore[reportPrivateUsage]
            user_template,
            input_copy,
            input_schema,
            has_inlined_files=False,
        )

        assert result.content == 'Input is:\n{\n  "text": "hello",\n  "number": 42\n}'
        assert result.should_remove_input_schema is False

    def test_with_single_file_schema(self, patched_runner: WorkflowAIRunner):
        """Test that schema with single file property returns simple prompt"""
        input_schema = {
            "type": "object",
            "properties": {
                "file": {"$ref": "#/$defs/File"},
            },
            "$defs": {
                "File": File.model_json_schema(),
            },
        }
        input_copy = {"file": {"content_type": "text/plain", "data": "some data"}}
        user_template = "Input is:\n{{input_data}}"

        result = patched_runner._build_user_message_content(  # pyright: ignore[reportPrivateUsage]
            user_template,
            input_copy,
            input_schema,
            has_inlined_files=False,
        )

        assert result.content == "Input is a single file"
        assert result.should_remove_input_schema is True

    def test_with_single_file_schema_with_inlined_files(self, patched_runner: WorkflowAIRunner):
        """Test that schema with single file property and inlined filess uses the template"""
        input_schema = {
            "type": "object",
            "properties": {
                "file": {"$ref": "#/$defs/File"},
            },
            "$defs": {
                "File": File.model_json_schema(),
            },
        }
        input_copy = {"file": {"content_type": "text/plain", "data": "some data"}}
        user_template = "Input is:\n{{input_data}}"

        result = patched_runner._build_user_message_content(  # pyright: ignore[reportPrivateUsage]
            user_template,
            input_copy,
            input_schema,
            has_inlined_files=True,
        )

        assert result.content.startswith("Input is:\n{")
        assert result.should_remove_input_schema is False

    def test_with_multiple_file_schema(self, patched_runner: WorkflowAIRunner):
        """Test that schema with multiple file properties uses the template"""
        input_schema = {
            "type": "object",
            "properties": {
                "file1": {"$ref": "#/$defs/File"},
                "file2": {"$ref": "#/$defs/File"},
            },
            "$defs": {
                "File": File.model_json_schema(),
            },
        }
        input_copy = {
            "file1": {"content_type": "text/plain", "data": "data1"},
            "file2": {"content_type": "text/plain", "data": "data2"},
        }
        user_template = "Input is:\n{{input_data}}"

        result = patched_runner._build_user_message_content(  # pyright: ignore[reportPrivateUsage]
            user_template,
            input_copy,
            input_schema,
            has_inlined_files=False,
        )

        assert result.content.startswith("Input is:\n{")
        assert '"file1"' in result.content
        assert '"file2"' in result.content
        assert result.should_remove_input_schema is False


class TestInlineTextFiles:
    def test_no_text_files(self, patched_runner: WorkflowAIRunner):
        """Test that non-text files are returned unchanged"""
        files = [
            FileWithKeyPath(content_type="image/png", data="some_data", key_path=["file1"]),
            FileWithKeyPath(content_type="application/pdf", data="some_data", key_path=["file2"]),
        ]
        input_dict: dict[str, Any] = {}

        result_files, has_inlined = patched_runner._inline_text_files(files, input_dict)  # pyright: ignore[reportPrivateUsage]

        assert not has_inlined
        assert result_files == files
        assert input_dict == {}

    def test_text_files_are_inlined(self, patched_runner: WorkflowAIRunner):
        """Test that text files are inlined into the input dictionary"""
        files = [
            FileWithKeyPath(
                content_type="text/plain",
                data="dGV4dF9kYXRh",
                key_path=["file1"],
            ),  # "text_data" in base64
            FileWithKeyPath(
                content_type="text/markdown",
                data="bWFya2Rvd25fZGF0YQ==",
                key_path=["nested", "file2"],
            ),  # "markdown_data" in base64
        ]
        input_dict: dict[str, Any] = {}

        result_files, has_inlined = patched_runner._inline_text_files(files, input_dict)  # pyright: ignore[reportPrivateUsage]

        assert has_inlined
        assert result_files == []  # All files were inlined
        assert input_dict == {
            "file1": "text_data",
            "nested": {"file2": "markdown_data"},
        }

    def test_mixed_files(self, patched_runner: WorkflowAIRunner):
        """Test handling of mixed text and non-text files"""
        files = [
            FileWithKeyPath(
                content_type="text/plain",
                data="dGV4dF9kYXRh",
                key_path=["file1"],
            ),  # "text_data" in base64
            FileWithKeyPath(content_type="image/png", data="imagedat", key_path=["file2"]),
            FileWithKeyPath(
                content_type="text/markdown",
                data="bWFya2Rvd25fZGF0YQ==",
                key_path=["file3"],
            ),  # "markdown_data" in base64
        ]
        input_dict: dict[str, Any] = {"existing": "value"}

        result_files, has_inlined = patched_runner._inline_text_files(files, input_dict)  # pyright: ignore[reportPrivateUsage]

        assert has_inlined
        assert len(result_files) == 1
        assert result_files[0].content_type == "image/png"
        assert input_dict == {
            "existing": "value",
            "file1": "text_data",
            "file3": "markdown_data",
        }

    def test_empty_input(self, patched_runner: WorkflowAIRunner):
        """Test handling of empty inputs"""
        empty_dict: dict[str, Any] = {}
        assert patched_runner._inline_text_files([], empty_dict) == ([], False)  # pyright: ignore[reportPrivateUsage]

    def test_existing_nested_structure(self, patched_runner: WorkflowAIRunner):
        """Test inlining into existing nested dictionary structure"""
        files = [
            FileWithKeyPath(
                content_type="text/plain",
                data="dGV4dF9kYXRh",
                key_path=["nested", "deep", "file1"],
            ),  # "text_data" in base64
        ]
        input_dict: dict[str, Any] = {
            "nested": {
                "existing": "value",
                "deep": {
                    "other": "data",
                },
            },
        }

        result_files, has_inlined = patched_runner._inline_text_files(files, input_dict)  # pyright: ignore[reportPrivateUsage]

        assert has_inlined
        assert result_files == []
        assert input_dict == {
            "nested": {
                "existing": "value",
                "deep": {
                    "other": "data",
                    "file1": "text_data",
                },
            },
        }


class TestBuildStructuredOutput:
    def test_raises_on_agent_failure_status(self, patched_runner: WorkflowAIRunner):
        output = {
            "internal_agent_run_result": {
                "status": "failure",
                "error": None,
            },
        }

        with pytest.raises(AgentRunFailedError, match="Agent run failed"):
            patched_runner.build_structured_output(output, partial=False)

    def test_no_raise_on_success_status(self, patched_runner: WorkflowAIRunner):
        """Test that it doesn't raise when status is success"""
        output = {
            "internal_agent_run_result": {
                "status": "success",
                "error": None,
            },
            "bla": "bla",
        }
        result = patched_runner.build_structured_output(output, partial=False)
        assert result.output == {"bla": "bla"}

    def test_no_raise_on_missing_result(self, patched_runner: WorkflowAIRunner):
        """Test that it doesn't raise when internal_agent_run_result is None"""
        output = {"bla": "bla"}
        result = patched_runner.build_structured_output(output, partial=False)
        assert result.output == {"bla": "bla"}

    def test_validate_output_with_null_reasoning_steps(self, patched_runner: WorkflowAIRunner):
        output_dict = {
            "meal_plan": "Plan with null reasoning steps",
            "internal_reasoning_steps": [None, {"explaination": "valid_step"}],
        }

        output = patched_runner.build_structured_output(output_dict, partial=False)

        assert output.output == {"meal_plan": "Plan with null reasoning steps"}
        assert output.reasoning_steps and len(output.reasoning_steps) == 1
        assert output.reasoning_steps[0].explaination == "valid_step"

    def test_with_steps_and_run_result(self, patched_runner: WorkflowAIRunner):
        json_dict = {
            "meal_plan": "Sample meal plan",
            "internal_reasoning_steps": [
                {
                    "title": "First step",
                    "explaination": "Planning breakfast",
                    "output": "Breakfast plan",
                },
                {
                    "title": "Second step",
                    "explaination": "Planning lunch",
                    "output": "Lunch plan",
                },
            ],
            "internal_agent_run_result": {
                "status": "success",
                "error": None,
            },
        }

        output = patched_runner.build_structured_output(json_dict, partial=False)

        assert output.output == {"meal_plan": "Sample meal plan"}
        assert output.reasoning_steps and len(output.reasoning_steps) == 2
        assert output.reasoning_steps[0].title == "First step"
        assert output.reasoning_steps[0].explaination == "Planning breakfast"
        assert output.reasoning_steps[0].output == "Breakfast plan"
        assert output.agent_run_result is not None
        assert output.agent_run_result.status == "success"
        assert output.agent_run_result.error is None
        assert output.tool_calls is None

    def test_partial_deltas(self, patched_runner: WorkflowAIRunner):
        patched_runner._stream_deltas = True  # pyright: ignore[reportPrivateUsage]
        output = patched_runner.build_structured_output(
            "hello",
            partial=True,
        )
        assert output.output == "hello"
        assert output.reasoning_steps is None
        assert output.agent_run_result is None
        assert output.tool_calls is None


class TestAppendToolCallsToMessages:
    def test_append_tool_calls_to_messages(self, patched_runner: WorkflowAIRunner):
        messages = [
            MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="system message"),
            MessageDeprecated(role=MessageDeprecated.Role.USER, content="user message"),
        ]
        tool_calls = [
            ToolCallRequestWithID(
                tool_name="test_tool",
                tool_input_dict={"arg1": "value1"},
            ),
            ToolCallRequestWithID(
                tool_name="test_tool2",
                tool_input_dict={"arg2": "value2"},
            ),
        ]

        result = patched_runner._append_tool_call_requests_to_messages(messages, tool_calls)  # pyright: ignore[reportPrivateUsage]

        assert len(result) == 3
        assert result[0] == messages[0]  # System message unchanged
        assert result[1] == messages[1]  # User message unchanged
        assert result[2].role == MessageDeprecated.Role.ASSISTANT

        assert result[2].tool_call_requests == [
            ToolCallRequestWithID(
                tool_name="test_tool",
                tool_input_dict={"arg1": "value1"},
                id="test_tool_5a416d41cb16840102e2706db21a5c18",
            ),
            ToolCallRequestWithID(
                tool_name="test_tool2",
                tool_input_dict={"arg2": "value2"},
                id="test_tool2_3835b114763f63d4660d2ad37f296f66",
            ),
        ]

    def test_append_tool_calls_to_messages_empty_tool_calls(self, patched_runner: WorkflowAIRunner):
        messages = [
            MessageDeprecated(role=MessageDeprecated.Role.SYSTEM, content="system message"),
            MessageDeprecated(role=MessageDeprecated.Role.USER, content="user message"),
        ]
        tool_calls: list[ToolCallRequestWithID] = []

        result = patched_runner._append_tool_call_requests_to_messages(messages, tool_calls)  # pyright: ignore[reportPrivateUsage]

        assert len(result) == 3
        assert result[0] == messages[0]  # System message unchanged
        assert result[1] == messages[1]  # User message unchanged
        assert result[2].role == MessageDeprecated.Role.ASSISTANT
        assert result[2].tool_call_requests == []


class TestSafeExecuteTool:
    async def test_cache_hit(self, patched_runner: "WorkflowAIRunner"):
        from core.domain.tool_call import ToolCallRequestWithID

        # Create a tool call
        tool_call = ToolCallRequestWithID(tool_name="dummy_tool", tool_input_dict={"x": 1})
        # Create a cached result using with_result
        cached_result = tool_call.with_result("cached result")
        # Patch the internal tool cache get method
        patched_runner._internal_tool_cache.get = AsyncMock(return_value=cached_result)  # pyright: ignore[reportPrivateUsage]
        # Call _safe_execute_tool
        result, is_cached = await patched_runner._safe_execute_tool(tool_call, messages=[])  # pyright: ignore[reportPrivateUsage]
        assert is_cached is True
        assert result == cached_result

    async def test_found_in_messages(self, patched_runner: "WorkflowAIRunner"):
        from core.domain.tool_call import ToolCallRequestWithID

        tool_call = ToolCallRequestWithID(tool_name="dummy_tool", tool_input_dict={"x": 1})
        patched_runner._internal_tool_cache.get = AsyncMock(return_value=None)  # pyright: ignore[reportPrivateUsage]
        # Create a message that contains the tool_call id
        from core.domain.message import MessageDeprecated

        message = MessageDeprecated(role=MessageDeprecated.Role.USER, content=f"Previous call with id: {tool_call.id}")
        result, is_cached = await patched_runner._safe_execute_tool(tool_call, messages=[message])  # pyright: ignore[reportPrivateUsage]
        assert is_cached is True
        expected = tool_call.with_result("Please refer to the previous messages for the result of this tool call")
        assert result == expected

    async def test_tool_not_found(self, patched_runner: "WorkflowAIRunner"):
        from core.domain.tool_call import ToolCallRequestWithID

        # Set enabled internal tools to empty dict to simulate tool not found
        patched_runner._enabled_internal_tools = {}  # pyright: ignore[reportPrivateUsage]
        tool_call = ToolCallRequestWithID(tool_name="nonexistent_tool", tool_input_dict={"x": 1})
        result, is_cached = await patched_runner._safe_execute_tool(tool_call, messages=[])  # pyright: ignore[reportPrivateUsage]
        assert is_cached is False
        assert result.error is not None
        assert "Tool 'nonexistent_tool' does not exist" in result.error

    async def test_success_execution(self, patched_runner: "WorkflowAIRunner"):
        from core.domain.tool_call import ToolCallRequestWithID

        # Prepare a dummy tool that returns success
        dummy_tool = AsyncMock(return_value="success result")
        from core.runners.workflowai.internal_tool import InternalTool

        patched_runner._enabled_internal_tools = {  # pyright: ignore[reportPrivateUsage]
            "dummy_tool": InternalTool(_tool("dummy_tool"), dummy_tool),
        }
        patched_runner._internal_tool_cache.get = AsyncMock(return_value=None)  # pyright: ignore[reportPrivateUsage]
        patched_runner._internal_tool_cache.set = AsyncMock()  # pyright: ignore[reportPrivateUsage]
        tool_call = ToolCallRequestWithID(tool_name="dummy_tool", tool_input_dict={"x": 10})
        result, is_cached = await patched_runner._safe_execute_tool(tool_call, messages=[])  # pyright: ignore[reportPrivateUsage]
        assert is_cached is False
        expected = tool_call.with_result("success result")
        assert result == expected
        dummy_tool.assert_awaited_once_with(x=10)
        patched_runner._internal_tool_cache.set.assert_awaited_once_with("dummy_tool", {"x": 10}, "success result")  # pyright: ignore[reportPrivateUsage]

    async def test_execution_exception(self, patched_runner: "WorkflowAIRunner"):
        from core.domain.tool_call import ToolCallRequestWithID

        # Prepare a dummy tool that raises an exception
        async def failing_tool(**kwargs: Any) -> Any:
            raise ValueError("failure")

        failing_tool_mock = AsyncMock(side_effect=failing_tool)
        from core.runners.workflowai.internal_tool import InternalTool

        patched_runner._enabled_internal_tools = {  # pyright: ignore[reportPrivateUsage]
            "dummy_tool": InternalTool(_tool("dummy_tool"), failing_tool_mock),
        }
        patched_runner._internal_tool_cache.get = AsyncMock(return_value=None)  # pyright: ignore[reportPrivateUsage]
        patched_runner._internal_tool_cache.set = AsyncMock()  # pyright: ignore[reportPrivateUsage]
        tool_call = ToolCallRequestWithID(tool_name="dummy_tool", tool_input_dict={"x": 10})
        result, is_cached = await patched_runner._safe_execute_tool(tool_call, messages=[])  # pyright: ignore[reportPrivateUsage]
        assert is_cached is False
        # The error message should indicate a ValueError
        assert result.error == "ValueError: failure"
        failing_tool_mock.assert_awaited_once_with(x=10)
        patched_runner._internal_tool_cache.set.assert_not_awaited()  # pyright: ignore[reportPrivateUsage]


class TestBuildOptions:
    def test_build_options_with_deprecated_tools(self):
        deprecated_tools_properties = TaskGroupProperties.model_validate(
            {
                "model": "gemini-1.5-pro-latest",
                "temperature": 0,
                "instructions": "You are a helpful assistant.",
                "runner_name": "WorkflowAI",
                "runner_version": "v0.1.0",
                "is_chain_of_thought_enabled": False,
                "enabled_tools": [
                    "whatever",  # will be skipped
                    "WEB_BROWSER_TEXT",
                    "WEB_SEARCH_GOOGLE",
                    {
                        "name": "test_tool",
                        "description": "test tool",
                        "input_schema": {"type": "object", "properties": {"arg1": {"type": "string"}}},
                        "output_schema": {"type": "object", "properties": {"arg2": {"type": "string"}}},
                    },
                ],
                "task_variant_id": "7b0d19c962a285fcd8139372ecadc89e",
            },
        )
        options = WorkflowAIRunner._build_options(
            task=test_models.task_variant(),
            properties=deprecated_tools_properties,
        )  # pyright: ignore[reportPrivateUsage]
        assert options.model == "gemini-1.5-pro-latest"
        assert options.instructions == "You are a helpful assistant."


class TestExtractAllInternalKeys:
    @pytest.fixture
    def patched_logger(self):
        with patch("core.runners.workflowai.workflowai_runner.logger", autospec=True) as mock_logger:
            yield mock_logger

    def test_extract_all_internal_keys(self, patched_logger: Mock):
        json_dict = {
            "internal_reasoning_steps": [
                {
                    "title": "First step",
                    "explaination": "Planning breakfast",
                    "output": "Breakfast plan",
                },
            ],
            "bla": "bla",
        }
        result = WorkflowAIRunner._extract_all_internal_keys(json_dict, partial=False)  # pyright: ignore[reportPrivateUsage]
        assert result[0] is None
        assert result[1] == [
            InternalReasoningStep(
                title="First step",
                explaination="Planning breakfast",
                output="Breakfast plan",
            ),
        ]
        assert json_dict == {"bla": "bla"}

        patched_logger.exception.assert_not_called()

    def test_extract_all_internal_keys_errors_with_partial(self, patched_logger: Mock):
        # We don't call the logger on partial mode since we want to ignore partial outputs
        json_dict: dict[str, Any] = {}
        result = WorkflowAIRunner._extract_all_internal_keys(json_dict, partial=True)  # pyright: ignore[reportPrivateUsage]
        assert result[0] is None
        assert result[1] is None
        patched_logger.exception.assert_not_called()


class TestRun:
    async def test_requires_downloading_file(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        mock_task: Mock,
    ):
        """Check that requires_downloading_file is called with the correct FileWithKeyPath object when:
        - the schema refers to an Image via the named def (not the File with format)
        - the input contains a URL without an extension and without a content type

        note: Tests uses a mocked openai provider but is not specific to openai
        """
        # Return false for downloading files, not really important here since we just want to check the arguments
        patched_provider_factory.openai.requires_downloading_file.return_value = False
        # Input schema with a named def for Image
        mock_task.input_schema = SerializableTaskIO.from_json_schema(
            {
                "type": "object",
                "properties": {
                    "image": {
                        "$ref": "#/$defs/Image",
                    },
                },
                "$defs": {
                    "Image": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                    },
                },
            },
        )
        # Mock the openai complete method to return a structured output
        patched_provider_factory.openai.complete.return_value = StructuredOutput({"hello": "world"})

        # Input with a URL without an extension and without a content type
        # Default builder will use openai
        builder = await patched_runner.task_run_builder(
            {
                "image": {
                    "url": "https://example.com/image",
                },
            },
            start_time=0,
        )

        run = await patched_runner.run(builder)
        assert run.task_output == {"hello": "world"}

        # Check that the FileWithKeyPath object was correctly passed to requires_downloading_file
        patched_provider_factory.openai.requires_downloading_file.assert_called_once_with(
            # format=image is what we want, the file with keypath is passed to
            # the provider to decide whether to download or not
            FileWithKeyPath(url="https://example.com/image", format="image", key_path=["image"]),
            Model.GPT_4O_2024_11_20,
        )

    async def test_provider_failover(
        self,
        patched_runner: WorkflowAIRunner,
        patched_provider_factory: Mock,
        patch_metric_send: Mock,
    ):
        """Test that the correct metric is sent when a provider fails"""
        patched_runner._options.model = Model.GEMINI_1_5_FLASH_002  # pyright: ignore[reportPrivateUsage]
        patched_runner._options.provider = None  # pyright: ignore[reportPrivateUsage]
        patched_runner.properties.model = Model.GEMINI_1_5_FLASH_002

        patched_provider_factory.google.complete.side_effect = ProviderInternalError()
        patched_provider_factory.gemini.complete.return_value = StructuredOutput(
            {"output": "final"},
        )
        builder = await patched_runner.task_run_builder({}, start_time=0)

        run = await patched_runner.run(builder)
        assert run.task_output == {"output": "final"}

        patched_provider_factory.google.complete.assert_awaited_once()
        first_opts = patched_provider_factory.google.complete.call_args_list[0].args[1]
        assert isinstance(first_opts, ProviderOptions), "sanity check"
        # Google does not support structured generation
        assert first_opts.structured_generation is False

        patched_provider_factory.gemini.complete.assert_awaited_once()
        patch_metric_send.assert_called_once()

        metric = patch_metric_send.call_args_list[0].args[0]
        assert isinstance(metric, Metric)
        assert metric.name == "workflowai_inference"
        assert metric.tags == {
            "model": "gemini-1.5-flash-002",
            "provider": "workflowai",
            "tenant": "tenant1",
            "status": "success",
        }

    async def test_templated_instructions(self, mock_provider_factory_full: Mock):
        """Check that the input schema is not sent when templated instructions are used with all fields"""
        runner = _build_runner2(
            mock_provider_factory_full,
            {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "count": {"type": "integer"},
                },
            },
            {"type": "object", "properties": {"greeting": {"type": "string"}}},
            "Generate a greeting of {{count}} {{description}}",
            Model.GPT_41_LATEST,
            has_templated_instructions=True,
        )

        mock_provider_factory_full.openai.complete.return_value = StructuredOutput(
            output={"greeting": "Hello, world!"},
        )

        builder = await runner.task_run_builder(
            {"description": "A beautiful sunset over a calm ocean", "count": 1},
            start_time=0,
        )

        run = await runner.run(builder)

        assert run.task_output == {"greeting": "Hello, world!"}

        messages = mock_provider_factory_full.openai.complete.call_args_list[0].args[0]
        assert len(messages) == 2
        assert (
            messages[0].content
            == "<instructions>\nGenerate a greeting of 1 A beautiful sunset over a calm ocean\n</instructions>"
        )
        assert messages[1].content == "Follow the instructions"

    async def test_image_output(self, mock_provider_factory_full: Mock):
        runner = _build_runner2(
            mock_provider_factory_full,
            {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "shape": {"type": "string"},
                },
            },
            {"type": "object", "properties": {"image": {"$ref": "#/$defs/Image"}}},
            "Generate a {{shape}} image of {{description}}",
            Model.IMAGEN_3_0_002,
            has_templated_instructions=True,
        )

        builder = await runner.task_run_builder(
            {"description": "A beautiful sunset over a calm ocean", "shape": "landscape"},
            start_time=0,
        )

        mock_provider_factory_full.google_imagen.sanitize_template.side_effect = (
            lambda _: TemplateName.V2_NO_INPUT_OR_OUTPUT_SCHEMA  # pyright: ignore[reportUnknownLambdaType]
        )

        mock_provider_factory_full.google_imagen.complete.return_value = StructuredOutput(
            output={},
            files=[
                File(
                    data="hell",
                    content_type="image/png",
                ),
            ],
        )

        run = await runner.run(builder)
        assert run.task_output == {
            "image": {
                "data": "hell",
                "content_type": "image/png",
            },
        }

        messages = mock_provider_factory_full.google_imagen.complete.call_args_list[0].args[0]
        assert len(messages) == 2
        assert messages[0].content == "Generate a landscape image of A beautiful sunset over a calm ocean"
        assert messages[0].image_options == ImageOptions(image_count=1, shape="landscape")
        assert messages[1].content == "Follow the instructions"


def test_check_tool_calling_support_tool_enabled_model_not_supporting_tool_calling(
    mock_task: SerializableTaskVariant,
    patched_runner: WorkflowAIRunner,
) -> None:
    """
    Test that '_check_tool_calling_support' raises an error with tool ENABLED and model that does NOT support tool calling
    """

    with (
        patch.object(WorkflowAIRunner, "_build_properties", return_value=Mock(enabled_tools=[])),
        patch.object(WorkflowAIRunner, "is_tool_use_enabled", new_callable=PropertyMock, return_value=True),
    ):
        provider = Provider.GOOGLE_GEMINI
        model_data = Mock(
            spec=FinalModelData,
            supports_tool_calling=False,
            model=Model.GEMINI_2_0_FLASH_THINKING_EXP_0121,
        )
        runner = WorkflowAIRunner(
            mock_task,
            options=WorkflowAIRunnerOptions(
                instructions="",
                model=model_data.model,
                provider=provider,
                template_name=TemplateName.V1,
            ),
        )

        with pytest.raises(ModelDoesNotSupportMode) as exc_info:
            runner._check_tool_calling_support(model_data)  # pyright: ignore[reportPrivateUsage]

            assert exc_info.value.model == model_data.model  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            assert exc_info.value.extras["model"] == model_data.model  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
            assert exc_info.value.msg == f"{model_data.model.value} does not support tool calling"  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]


def test_check_tool_calling_support_tool_disabled_model_not_supporting_tool_calling(
    mock_task: SerializableTaskVariant,
    patched_runner: WorkflowAIRunner,
) -> None:
    """
    Test that '_check_tool_calling_support' does NOT raise an error with tool DISABLED and model that does NOT support tool calling
    """

    with (
        patch.object(WorkflowAIRunner, "_build_properties", return_value=Mock(enabled_tools=[])),
        patch.object(WorkflowAIRunner, "is_tool_use_enabled", new_callable=PropertyMock, return_value=False),
    ):
        provider = Provider.GOOGLE_GEMINI
        model_data = Mock(
            spec=FinalModelData,
            supports_tool_calling=False,
            model=Model.GEMINI_2_0_FLASH_THINKING_EXP_0121,
        )
        runner = WorkflowAIRunner(
            mock_task,
            options=WorkflowAIRunnerOptions(
                instructions="",
                model=model_data.model,
                provider=provider,
                template_name=TemplateName.V1,
            ),
        )
        runner._check_tool_calling_support(model_data)  # pyright: ignore[reportPrivateUsage]


def test_check_tool_calling_support_tool_disabled_model_supporting_tool_calling(
    mock_task: SerializableTaskVariant,
    patched_runner: WorkflowAIRunner,
) -> None:
    """
    Test that '_check_tool_calling_support' does NOT raise an error with tool DISABLED and model that DOES support tool calling
    """

    with (
        patch.object(WorkflowAIRunner, "_build_properties", return_value=Mock(enabled_tools=[])),
        patch.object(WorkflowAIRunner, "is_tool_use_enabled", new_callable=PropertyMock, return_value=False),
    ):
        provider = Provider.GOOGLE_GEMINI
        model_data = Mock(
            spec=FinalModelData,
            supports_tool_calling=True,
            model=Model.GEMINI_1_0_PRO_002,
        )
        runner = WorkflowAIRunner(
            mock_task,
            options=WorkflowAIRunnerOptions(
                instructions="",
                model=model_data.model,
                provider=provider,
                template_name=TemplateName.V1,
            ),
        )

        runner._check_tool_calling_support(model_data)  # pyright: ignore[reportPrivateUsage]


def test_check_tool_calling_support_tool_enabled_model_supporting_tool_calling(
    mock_task: SerializableTaskVariant,
    patched_runner: WorkflowAIRunner,
) -> None:
    """
    Test that '_check_tool_calling_support' does NOT raise an error with tool ENABLED and model that DOES support tool calling
    """

    with (
        patch.object(WorkflowAIRunner, "_build_properties", return_value=Mock(enabled_tools=[])),
        patch.object(WorkflowAIRunner, "is_tool_use_enabled", new_callable=PropertyMock, return_value=True),
    ):
        provider = Provider.GOOGLE_GEMINI
        model_data = Mock(
            spec=FinalModelData,
            supports_tool_calling=True,
            model=Model.GEMINI_1_5_PRO_002,
        )
        runner = WorkflowAIRunner(
            mock_task,
            options=WorkflowAIRunnerOptions(
                instructions="",
                model=model_data.model,
                provider=provider,
                template_name=TemplateName.V1,
            ),
        )

        runner._check_tool_calling_support(model_data)  # pyright: ignore[reportPrivateUsage]


def mock_complete(raw: str):
    def _mock_complete(
        messages: Any,
        options: Any,
        output_factory: Callable[[str, bool], StructuredOutput],
    ) -> StructuredOutput:
        return output_factory(raw, False)

    return _mock_complete


class TestRawOutput:
    async def test_raw_string_output(self, mock_provider_factory_full: Mock):
        runner = _build_runner2(
            mock_provider_factory_full,
            {"type": "object", "properties": {"text": {"type": "string"}}},
            RawStringMessageSchema,
            "Return a string",
            Model.GPT_4O_LATEST,
        )

        mock_provider_factory_full.openai.complete.side_effect = mock_complete("Hello world")

        builder = await runner.task_run_builder({}, start_time=0)
        run = await runner.run(builder)
        assert run.task_output == "Hello world"

    @pytest.mark.parametrize(
        "raw_content",
        [
            pytest.param({"whatever": "Hello world"}, id="dict"),
            pytest.param(["whatever", "Hello world"], id="list"),
        ],
    )
    async def test_any_json_output(self, mock_provider_factory_full: Mock, raw_content: Any):
        """Test that in case of a wildcard json, we can return any json"""
        runner = _build_runner2(
            mock_provider_factory_full,
            {"type": "object", "properties": {"text": {"type": "string"}}},
            RawJSONMessageSchema,
            "Return a string",
            Model.GPT_4O_LATEST,
        )
        mock_provider_factory_full.openai.complete.side_effect = mock_complete(json.dumps(raw_content))

        builder = await runner.task_run_builder({}, start_time=0)
        run = await runner.run(builder)
        assert run.task_output == raw_content


class TestMessagesInput:
    @pytest.mark.parametrize(
        "input",
        [
            pytest.param({"workflowai.messages": [{"content": [{"text": "Hello world"}], "role": "user"}]}, id="dict"),
            pytest.param(
                Messages.with_messages(Message(role="user", content=[MessageContent(text="Hello world")])),
                id="messages_model",
            ),
        ],
    )
    async def test_messages_as_json_object(self, mock_provider_factory_full: Mock, input: Any):
        """Check that we can pass raw messages to the runner"""
        runner = _build_runner2(
            mock_provider_factory_full,
            RawMessagesSchema,
            RawStringMessageSchema,
            "Return a string",
            Model.GPT_4O_LATEST,
        )

        mock_provider_factory_full.openai.complete.side_effect = mock_complete("Hello world")

        builder = await runner.task_run_builder(
            input,
            start_time=0,
        )
        run = await runner.run(builder)
        assert run.task_output == "Hello world"

        mock_provider_factory_full.openai.complete.assert_called_once()
        messages = mock_provider_factory_full.openai.complete.call_args_list[0].args[0]
        assert isinstance(messages, list)
        messages = cast(list[MessageDeprecated], messages)
        assert len(messages) == 1
        assert messages[0].content == "Hello world"


class TestTemplatedMessages:
    async def test_templated_messages(self, mock_provider_factory_full: Mock):
        runner = _build_runner2(
            mock_provider_factory_full,
            SerializableTaskIO.from_json_schema({"type": "object", "properties": {"text": {"type": "string"}}}),
            RawStringMessageSchema,
            messages=[Message.with_text("Hello {{text}}")],
        )

        mock_provider_factory_full.openai.complete.side_effect = mock_complete("Hello world")

        builder = await runner.task_run_builder(
            {
                "text": "bla",
            },
            start_time=0,
        )
        run = await runner.run(builder)
        assert run.task_output == "Hello world"

        mock_provider_factory_full.openai.complete.assert_called_once()

        messages = mock_provider_factory_full.openai.complete.call_args_list[0].args[0]
        assert isinstance(messages, list)
        messages = cast(list[MessageDeprecated], messages)
        assert len(messages) == 1
        assert messages[0].content == "Hello bla"

    async def test_templated_messages_with_messages_key(self, mock_provider_factory_full: Mock):
        runner = _build_runner2(
            mock_provider_factory_full,
            SerializableTaskIO.from_json_schema({"type": "object", "properties": {"messages": {"type": "string"}}}),
            RawStringMessageSchema,
            messages=[Message.with_text("Hello {{messages}}")],
        )

        mock_provider_factory_full.openai.complete.side_effect = mock_complete("Hello world")

        builder = await runner.task_run_builder(
            {
                "messages": "bla",
            },
            start_time=0,
        )
        run = await runner.run(builder)
        assert run.task_output == "Hello world"

        mock_provider_factory_full.openai.complete.assert_called_once()

        messages = mock_provider_factory_full.openai.complete.call_args_list[0].args[0]
        assert isinstance(messages, list)
        messages = cast(list[MessageDeprecated], messages)
        assert len(messages) == 1
        assert messages[0].content == "Hello bla"


class TestExtractFilesToDownload:
    def test_all_files_should_be_downloaded(self, patched_runner: WorkflowAIRunner):
        """Test when all files should be downloaded according to the callback"""
        files = [
            File(content_type="image/png", url="https://example.com/image1.png"),
            File(content_type="image/jpg", url="https://example.com/image2.jpg"),
            File(content_type="text/plain", url="https://example.com/text.txt"),
        ]

        # Callback that always returns True (all files should be downloaded)
        def should_download(f: File) -> bool:
            return True

        result = patched_runner._extract_files_to_download(  # pyright: ignore[reportPrivateUsage]
            files,
            max_number_of_file_urls=None,
            should_download_file=should_download,
        )

        assert result == files

    def test_no_files_should_be_downloaded(self, patched_runner: WorkflowAIRunner):
        """Test when no files should be downloaded and all have data"""
        files = [
            File(content_type="image/png", data="base64=="),
            File(content_type="image/jpg", data="base64=="),
            File(content_type="text/plain", data="base64=="),
        ]

        # Callback that always returns False (no files should be downloaded)
        def should_download(f: File) -> bool:
            return False

        result = patched_runner._extract_files_to_download(  # pyright: ignore[reportPrivateUsage]
            files,
            max_number_of_file_urls=None,
            should_download_file=should_download,
        )

        assert result == []

    def test_mixed_files_with_data_and_urls(self, patched_runner: WorkflowAIRunner):
        """Test mixed scenario with files that have data and files with URLs"""
        files = [
            File(content_type="image/png", data="base64=="),  # Has data, shouldn't download
            File(content_type="image/jpg", url="https://example.com/image2.jpg"),  # No data, could be link
            File(content_type="text/plain", url="https://example.com/text.txt"),  # No data, could be link
        ]

        # Only download the first file (with data)
        def should_download(f: File) -> bool:
            return f.data is not None

        result = patched_runner._extract_files_to_download(  # pyright: ignore[reportPrivateUsage]
            files,
            max_number_of_file_urls=None,
            should_download_file=should_download,
        )

        assert result == [files[0]]  # Only the file with data

    def test_max_file_urls_limit_exceeded(self, patched_runner: WorkflowAIRunner):
        """Test that excess files become downloads when max_number_of_file_urls is exceeded"""
        files = [
            File(content_type="image/png", url="https://example.com/image1.png"),  # No data
            File(content_type="image/jpg", url="https://example.com/image2.jpg"),  # No data
            File(content_type="text/plain", url="https://example.com/text.txt"),  # No data
            File(content_type="application/pdf", url="https://example.com/doc.pdf"),  # No data
        ]

        # Don't download any files initially
        def should_download(f: File) -> bool:
            return False

        result = patched_runner._extract_files_to_download(  # pyright: ignore[reportPrivateUsage]
            files,
            max_number_of_file_urls=2,
            should_download_file=should_download,
        )

        # Since max_number_of_file_urls=2 and we have 4 files without data,
        # the first 2 remain as links, the last 2 get moved to downloads
        assert len(result) == 2
        assert result == files[2:]  # Last 2 files should be downloaded

    def test_max_file_urls_limit_not_exceeded(self, patched_runner: WorkflowAIRunner):
        """Test that files remain as links when max_number_of_file_urls is not exceeded"""
        files = [
            File(content_type="image/png", url="https://example.com/image1.png"),  # No data
            File(content_type="image/jpg", url="https://example.com/image2.jpg"),  # No data
        ]

        # Don't download any files
        def should_download(f: File) -> bool:
            return False

        result = patched_runner._extract_files_to_download(  # pyright: ignore[reportPrivateUsage]
            files,
            max_number_of_file_urls=5,
            should_download_file=should_download,
        )

        # Since we have only 2 files and limit is 5, no files need to be downloaded
        assert result == []

    def test_mixed_scenario_with_limit(self, patched_runner: WorkflowAIRunner):
        """Test complex scenario with files that should be downloaded and URL limit"""
        files = [
            File(content_type="image/png", url="https://example.com/image1.png"),  # Should download
            File(content_type="image/jpg", url="https://example.com/image2.jpg"),  # No data, link
            File(content_type="text/plain", url="https://example.com/text.txt"),  # No data, link
            File(content_type="application/pdf", url="https://example.com/doc.pdf"),  # No data, link
            File(content_type="video/mp4", data="base64=="),  # Has data, not downloaded
        ]

        # Download only the first file
        def should_download(f: File) -> bool:
            return f.url == "https://example.com/image1.png"

        result = patched_runner._extract_files_to_download(  # pyright: ignore[reportPrivateUsage]
            files,
            max_number_of_file_urls=2,
            should_download_file=should_download,
        )

        # First file should be downloaded due to callback
        # Files 1,2 become links (within limit)
        # File 3 gets moved to download (exceeds limit)
        # File 4 has data so it's not considered for links
        expected = [files[0], files[3]]  # First and fourth files
        assert result == expected

    def test_empty_files_list(self, patched_runner: WorkflowAIRunner):
        """Test with empty files list"""

        def should_download(f: File) -> bool:
            return True

        result = patched_runner._extract_files_to_download(  # pyright: ignore[reportPrivateUsage]
            [],
            max_number_of_file_urls=5,
            should_download_file=should_download,
        )

        assert result == []

    def test_zero_max_file_urls(self, patched_runner: WorkflowAIRunner):
        """Test with max_number_of_file_urls set to 0"""
        files = [
            File(content_type="image/png", url="https://example.com/image1.png"),
            File(content_type="image/jpg", url="https://example.com/image2.jpg"),
        ]

        # Don't download any files initially
        def should_download(f: File) -> bool:
            return False

        result = patched_runner._extract_files_to_download(  # pyright: ignore[reportPrivateUsage]
            files,
            max_number_of_file_urls=0,
            should_download_file=should_download,
        )

        # Since max_number_of_file_urls=0, all files without data must be downloaded
        assert result == files
