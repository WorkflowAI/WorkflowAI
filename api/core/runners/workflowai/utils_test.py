import base64
import json
from logging import Logger
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest
from PIL import Image
from pytest_httpx import HTTPXMock

from core.domain.consts import FILE_DEFS
from core.domain.errors import InvalidFileError
from core.domain.fields.file import File
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.tool import Tool
from core.domain.types import AgentOutput
from core.runners.workflowai.internal_tool import InternalTool
from core.tools import ToolKind
from tests.utils import fixture_bytes

from .utils import (
    FileWithKeyPath,
    _process_ref,  # pyright: ignore[reportPrivateUsage]
    assign_files,
    cleanup_provider_json,
    convert_pdf_to_images,
    download_file,
    extract_files,
    is_schema_containing_legacy_file,
    reasoning_step_mapper,
    remove_files_from_schema,
    split_tools,
)


@pytest.fixture(scope="function")
def simple_schema() -> dict[str, Any]:
    return {
        "$defs": {},
        "properties": {
            "some_field": {"type": "string"},
        },
    }


class TestExtractFiles:
    def test_file_extract_without_file(self, simple_schema: dict[str, Any]):
        payload = {}
        assert extract_files(simple_schema, payload) == (simple_schema, payload, [])

    @pytest.fixture(scope="function", params=["File", "Image"])
    def image_array_schema(self, request: pytest.FixtureRequest) -> dict[str, Any]:
        return {
            "$defs": {f"{request.param}": {}},
            "properties": {
                "files": {
                    "items": {"$ref": f"#/$defs/{request.param}", "format": "image"},
                    "title": "Files",
                    "type": "array",
                },
            },
            "required": ["files"],
            "title": "DemoFileTaskInput",
            "type": "object",
        }

    def test_file_array_extract_array(self, image_array_schema: dict[str, Any]):
        payload = {
            "files": [
                {"content_type": "image/jpeg", "data": "bla1"},
                {"content_type": "image/png", "data": "bla2"},
            ],
        }

        _, updated, files = extract_files(image_array_schema, payload)
        assert len(files) == 2
        assert files[0].data == "bla1"
        assert files[0].key_path == ["files", 0]
        assert files[0].format == "image"
        assert files[1].data == "bla2"
        assert files[1].key_path == ["files", 1]
        assert files[1].format == "image"

        assert updated == {"files": [{"number": 0}, {"number": 1}]}

    SINGLE_IMAGE_SCHEMAS: list[dict[str, Any]] = [
        # Ref is direct
        {
            "$defs": {"File": {}},
            "properties": {"file": {"$ref": "#/$defs/File"}},
            "required": ["file"],
            "title": "DemoFileTaskInput",
            "type": "object",
        },
        # Ref is through a allof (pydantic)
        {
            "$defs": {"File": {}},
            "properties": {"file": {"allOf": [{"$ref": "#/$defs/File"}], "description": "The file to classify"}},
            "required": ["file"],
            "title": "MedicalBillClassificationTaskInput",
            "type": "object",
        },
    ]

    @pytest.mark.parametrize("single_file_schema", SINGLE_IMAGE_SCHEMAS)
    def test_file_array_extract_single(self, single_file_schema: dict[str, Any]):
        payload = {"file": {"name": "1.jpg", "content_type": "image/jpeg", "data": "bla="}}

        _, updated, images = extract_files(single_file_schema, payload)
        assert len(images) == 1
        assert images[0].data == "bla="
        assert images[0].key_path == ["file"]

        assert updated == {"file": {"number": 0}}

    def test_extract_files_deep_nested_schema(self):
        # Check that images are extracted from a deep nested schema
        # Fixes https://linear.app/workflowai/issue/WOR-3502/image-are-passed-as-base64-in-nested-schemas

        SCHEMA = {
            "$defs": {
                "Image": {
                    "properties": {
                        "name": {
                            "anyOf": [
                                {
                                    "type": "string",
                                },
                                {
                                    "type": "null",
                                },
                            ],
                            "default": None,
                            "deprecated": True,
                            "description": "An optional name for the file [no longer used]",
                            "title": "Name",
                        },
                        "content_type": {
                            "anyOf": [
                                {
                                    "type": "string",
                                },
                                {
                                    "type": "null",
                                },
                            ],
                            "default": None,
                            "description": "The content type of the file. Not needed if content type can be inferred from the URL.",
                            "examples": [
                                "image/png",
                                "image/jpeg",
                            ],
                            "title": "Content Type",
                        },
                        "data": {
                            "anyOf": [
                                {
                                    "type": "string",
                                },
                                {
                                    "type": "null",
                                },
                            ],
                            "default": None,
                            "description": "The base64 encoded data of the file. Required if no URL is provided.",
                            "title": "Data",
                        },
                        "url": {
                            "anyOf": [
                                {
                                    "type": "string",
                                },
                                {
                                    "type": "null",
                                },
                            ],
                            "default": None,
                            "description": "The URL of the file. Required if no data is provided.",
                            "title": "Url",
                        },
                    },
                    "title": "Image",
                    "type": "object",
                },
                "Message": {
                    "properties": {
                        "role": {
                            "title": "Role",
                            "type": "string",
                        },
                        "content": {
                            "title": "Content",
                            "type": "string",
                        },
                        "images": {
                            "anyOf": [
                                {
                                    "items": {
                                        "$ref": "#/$defs/Image",
                                    },
                                    "type": "array",
                                },
                                {
                                    "type": "null",
                                },
                            ],
                            "default": None,
                            "title": "Images",
                        },
                    },
                    "required": [
                        "role",
                        "content",
                    ],
                    "title": "Message",
                    "type": "object",
                },
            },
            "properties": {
                "messages": {
                    "items": {
                        "$ref": "#/$defs/Message",
                    },
                    "title": "Messages",
                    "type": "array",
                },
                "current_datetime": {
                    "title": "Current Datetime",
                    "type": "string",
                },
            },
            "required": [
                "messages",
                "current_datetime",
            ],
            "title": "ChatInput",
            "type": "object",
        }

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                    "images": [
                        {"name": "image.png", "content_type": "image/png", "data": "iVBORw0KGgoAAAANSUhEUgAAAAUA"},
                    ],
                },
            ],
        }

        _, updated, images = extract_files(SCHEMA, payload)
        assert images == [
            FileWithKeyPath(
                content_type="image/png",
                data="iVBORw0KGgoAAAANSUhEUgAAAAUA",
                url=None,
                key_path=["messages", 0, "images", 0],
                storage_url=None,
                format="image",
                name="image.png",  # pyright: ignore[reportCallIssue]
            ),
        ]
        assert updated == {
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                    "images": [{"number": 0}],
                },
            ],
        }

    def test_extract_files_complex_nested_schema(self):
        """Test extraction when file references are nested in multiple levels including composite schemas."""
        schema = {
            "$defs": {
                "File": {
                    "properties": {
                        "name": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                        "content_type": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                        "data": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                        "url": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    },
                    "title": "File",
                    "type": "object",
                },
            },
            "properties": {
                "documents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "attachment": {
                                "anyOf": [
                                    {"$ref": "#/$defs/File", "format": "binary"},
                                    {"type": "null"},
                                ],
                                "default": None,
                                "title": "Attachment",
                            },
                        },
                        "required": ["title", "attachment"],
                        "title": "Document",
                    },
                    "title": "Documents",
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "session": {"type": "string"},
                        "avatar": {
                            "allOf": [
                                {"$ref": "#/$defs/File", "format": "image"},
                            ],
                            "default": None,
                            "title": "Avatar",
                        },
                    },
                    "required": ["session", "avatar"],
                    "title": "Metadata",
                },
            },
            "required": ["documents", "metadata"],
            "title": "ComplexSchema",
            "type": "object",
        }

        payload = {
            "documents": [
                {
                    "title": "Doc1",
                    "attachment": {"name": "file1.txt", "content_type": "text/plain", "data": "SVNdl1==", "url": None},
                },
                {
                    "title": "Doc2",
                    "attachment": None,
                },
            ],
            "metadata": {
                "session": "abc123",
                "avatar": {"name": "avatar.png", "content_type": "image/png", "data": "abcd", "url": None},
            },
        }

        _, updated_payload, files = extract_files(schema, payload)

        # Verify that two files were extracted
        assert len(files) == 2
        file1, file2 = files

        # Check file extracted from documents[0].attachment
        assert file1.data == "SVNdl1=="
        assert file1.content_type == "text/plain"
        assert file1.key_path == ["documents", 0, "attachment"]

        # Check file extracted from metadata.avatar
        assert file2.data == "abcd"
        assert file2.content_type == "image/png"
        assert file2.key_path == ["metadata", "avatar"]

        # Verify updated payload: file references replaced with a number
        expected_payload = {
            "documents": [
                {"title": "Doc1", "attachment": {"number": 0}},
                {"title": "Doc2", "attachment": None},
            ],
            "metadata": {"session": "abc123", "avatar": {"number": 1}},
        }
        assert updated_payload == expected_payload

    @pytest.mark.parametrize(
        "schema",
        [
            {"$defs": {"File": {}}, "properties": {"file": {"$ref": "#/$defs/File", "format": "image"}}},
            {"$defs": {"Image": {}}, "properties": {"file": {"$ref": "#/$defs/Image"}}},
        ],
    )
    def test_extract_files_no_format(self, schema: dict[str, Any]):
        """Check that we correctly extract the format from the schema for both named defs
        and Files with format"""
        payload = {"file": {"url": "https://bla.com/file"}}
        _, _, files = extract_files(schema, payload)
        assert len(files) == 1
        assert files[0].format == "image"


class TestDownloadImage:
    async def test_download_image(self, httpx_mock: HTTPXMock):
        image = File(url="https://bla.com/file.png")

        httpx_mock.add_response(status_code=200, content=b"iVBORw0KGgoAAAANSUhEUgAAAAUA")

        await download_file(image)

        # base64 encoded data
        assert image.data == "aVZCT1J3MEtHZ29BQUFBTlNVaEVVZ0FBQUFVQQ=="
        assert image.content_type == "image/png"

    async def test_download_image_no_content_type(self, httpx_mock: HTTPXMock):
        image = File(url="https://bla.com/file")

        httpx_mock.add_response(status_code=200, content=fixture_bytes("files/test.webp"))

        await download_file(image)
        assert image.content_type == "image/webp"


async def test_retry_download_file(httpx_mock: HTTPXMock):
    httpx_mock.add_exception(httpx.ConnectTimeout("Test exception"), is_reusable=True)

    with pytest.raises(InvalidFileError):
        await download_file(File(url="https://bla.com/file.png"))

    assert len(httpx_mock.get_requests()) == 3


class TestFileWithKeyPath:
    @pytest.mark.parametrize(
        "file,is_audio,is_image",
        [
            (FileWithKeyPath(data="bla=", format="image", key_path=[]), False, True),
            (FileWithKeyPath(data="bla=", format="audio", key_path=[]), True, False),
            (FileWithKeyPath(data="bla=", format=None, key_path=[]), None, None),
            (FileWithKeyPath(data="bla=", content_type="image/jpeg", key_path=[]), False, True),
            (FileWithKeyPath(data="bla=", content_type="audio/mpeg", key_path=[]), True, False),
        ],
    )
    def test_is_audio_is_image(self, file: FileWithKeyPath, is_audio: bool | None, is_image: bool | None):
        assert file.is_audio == is_audio
        assert file.is_image == is_image


class TestIsSchemaContainingLegacyFile:
    @pytest.mark.parametrize(
        "schema, expected",
        [
            ({"$defs": {"Image": {}}}, True),
            ({"$defs": {"File": {}}}, False),
            ({"$defs": {"Image": {"properties": {"url": {"type": "string"}}}}}, False),
            ({"$defs": {"Image": {"properties": {"name": {"type": "string"}}}}}, True),
        ],
    )
    def test_is_schema_containing_legacy_file(self, schema: dict[str, Any], expected: bool):
        assert is_schema_containing_legacy_file(schema) == expected


class TestSplitTools:
    def test_with_enabled_tools(self):
        available_tools = {
            ToolKind.WEB_SEARCH_GOOGLE: InternalTool(
                definition=Tool(name=ToolKind.WEB_SEARCH_GOOGLE, input_schema={}, output_schema={}),
                fn=Mock(return_value="success"),
            ),
            ToolKind.WEB_BROWSER_TEXT: InternalTool(
                definition=Tool(name=ToolKind.WEB_BROWSER_TEXT, input_schema={}, output_schema={}),
                fn=Mock(return_value="success"),
            ),
        }

        # Split tools only deals with parsed tools.
        internal, external = split_tools(
            available_tools,
            [
                ToolKind.WEB_SEARCH_GOOGLE,
                ToolKind.WEB_BROWSER_TEXT,
                # Simulating an invalid ToolKind, if for example the runner stops supporting a tool
                "whatever",  # type: ignore
                Tool(name="external", input_schema={}, output_schema={}),
            ],
        )  # pyright: ignore[reportPrivateUsage]

        assert [e.definition.name for e in internal.values()] == [ToolKind.WEB_SEARCH_GOOGLE, ToolKind.WEB_BROWSER_TEXT]
        assert external == {"external": Tool(name="external", input_schema={}, output_schema={})}


class TestConvertPdfToImages:
    @patch("pdf2image.convert_from_bytes")
    async def test_convert_pdf_to_images_success(
        self,
        mock_convert: Mock,
    ) -> None:
        # Setup mock
        img = Image.new("RGB", (100, 100), color="red")
        mock_convert.return_value = [img]

        files = await convert_pdf_to_images(
            FileWithKeyPath(
                data="blabla==",
                key_path=[1, 2],
            ),
        )

        assert files[0].data
        assert files[0].content_type == "image/jpeg"
        assert files[0].key_path == [1, 2, 0]

        # Verify convert_from_bytes was called with correct parameters
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args[1]
        assert call_args["fmt"] == "jpg"
        assert call_args["dpi"] == 150

    @patch("pdf2image.convert_from_bytes")
    async def test_convert_pdf_to_images_invalid_pdf(
        self,
        mock_convert: Mock,
    ) -> None:
        mock_convert.side_effect = Exception("Invalid PDF")
        invalid_pdf = FileWithKeyPath(data=base64.b64encode(b"not a pdf").decode("utf-8"), key_path=[])

        with pytest.raises(Exception):
            await convert_pdf_to_images(invalid_pdf)


class TestProcessRef:
    @patch("core.runners.workflowai.utils._replace_file_in_payload")
    @patch("core.runners.workflowai.utils._recursive_find_files")
    @pytest.mark.parametrize("ref_name", FILE_DEFS)
    def test_process_ref(self, mock_recursive_find_files: Mock, mock_replace_file_in_payload: Mock, ref_name: str):
        """Check that process ref correctly handles all file refs"""
        schema = {"$ref": f"#/$defs/{ref_name}"}
        assert _process_ref(schema, {}, [], [], None)

        mock_replace_file_in_payload.assert_called_once()
        mock_recursive_find_files.assert_not_called()


class TestCleanupProviderJson:
    async def test_double_nulls(self):
        raw_json = '{"blabla":["Pr\\u0000e9paration de commande"]}'
        raw_obj = json.loads(raw_json)
        assert cleanup_provider_json(raw_obj) == {"blabla": ["Préparation de commande"]}


def _file_defs(name: str = "File"):
    return {
        "$defs": {
            name: {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                },
            },
        },
    }


class TestAssignFiles:
    def test_assign_single_file(self):
        schema: dict[str, Any] = {
            "properties": {
                "file": {"$ref": "#/$defs/File"},
            },
            **_file_defs(),
        }
        files = [File(data="fil1", content_type="text/plain")]
        output: AgentOutput = {}

        assert not assign_files(schema, files, output)
        assert output == {"file": {"data": "fil1", "content_type": "text/plain"}}

    def test_assign_file_list(self):
        schema: dict[str, Any] = {
            "properties": {
                "files": {"type": "array", "items": {"$ref": "#/$defs/File"}},
            },
            **_file_defs(),
        }
        files = [
            File(data="fil1", content_type="text/plain"),
            File(data="fil2", content_type="text/plain"),
        ]
        output: AgentOutput = {"files": []}

        assert not assign_files(schema, files, output)
        assert output == {
            "files": [
                {"data": "fil1", "content_type": "text/plain"},
                {"data": "fil2", "content_type": "text/plain"},
            ],
        }

    def test_assign_multiple_file_fields(self):
        schema: dict[str, Any] = {
            "properties": {
                "file1": {"$ref": "#/$defs/File"},
                "file2": {"$ref": "#/$defs/File"},
            },
            **_file_defs(),
        }
        files = [
            File(data="fil1", content_type="text/plain"),
            File(data="fil2", content_type="text/plain"),
        ]
        output: AgentOutput = {}

        assert not assign_files(schema, files, output)
        assert output == {
            "file1": {"data": "fil1", "content_type": "text/plain"},
            "file2": {"data": "fil2", "content_type": "text/plain"},
        }

    def test_assign_mixed_file_fields(self):
        schema: dict[str, Any] = {
            "properties": {
                "single_file": {"$ref": "#/$defs/File"},
                "file_list": {"type": "array", "items": {"$ref": "#/$defs/File"}},
            },
            **_file_defs(),
        }
        files = [
            File(data="single==", content_type="text/plain"),
            File(data="lis1", content_type="text/plain"),
            File(data="lis2", content_type="text/plain"),
        ]
        output: AgentOutput = {}

        assert not assign_files(schema, files, output)
        assert output == {
            "single_file": {"data": "single==", "content_type": "text/plain"},
            "file_list": [
                {"data": "lis1", "content_type": "text/plain"},
                {"data": "lis2", "content_type": "text/plain"},
            ],
        }

    @pytest.fixture()
    def schema_with_object_with_file_field(self) -> dict[str, Any]:
        return {
            "properties": {
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"$ref": "#/$defs/File"},
                            "description": {"type": "string"},
                        },
                    },
                },
            },
            **_file_defs(),
        }

    def test_list_of_object_with_file_field(self, schema_with_object_with_file_field: dict[str, Any]):
        files = [
            File(data="12==", content_type="text/plain"),
            File(data="23==", content_type="text/plain"),
        ]
        output: AgentOutput = {}
        remaining_files = assign_files(schema_with_object_with_file_field, files, output)
        assert not remaining_files
        assert output == {
            "files": [
                {"file": {"data": "12==", "content_type": "text/plain"}},
                {"file": {"data": "23==", "content_type": "text/plain"}},
            ],
        }

    def test_list_of_object_with_file_field_prefilled(self, schema_with_object_with_file_field: dict[str, Any]):
        files = [
            File(data="12==", content_type="text/plain"),
            File(data="23==", content_type="text/plain"),
        ]
        output: AgentOutput = {
            "files": [
                {"description": "file1"},
                {"description": "file2"},
            ],
        }
        remaining_files = assign_files(schema_with_object_with_file_field, files, output)
        assert not remaining_files
        assert output == {
            "files": [
                {"file": {"data": "12==", "content_type": "text/plain"}, "description": "file1"},
                {"file": {"data": "23==", "content_type": "text/plain"}, "description": "file2"},
            ],
        }


class TestRemoveFilesFromSchema:
    def test_remove_files_from_schema(self):
        schema: dict[str, Any] = {
            "properties": {
                "file": {"$ref": "#/$defs/File"},
            },
            **_file_defs(),
        }

        min_file_count, max_file_count = remove_files_from_schema(schema)
        assert min_file_count == 1
        assert max_file_count == 1

        assert schema["properties"] == {}

    # TODO: we should add more tests here
    def test_remove_files_from_schema_with_array(self):
        schema: dict[str, Any] = {
            "properties": {
                "files": {"type": "array", "items": {"$ref": "#/$defs/File"}},
            },
            **_file_defs(),
        }

        min_file_count, max_file_count = remove_files_from_schema(schema)
        assert min_file_count == 1
        assert max_file_count is None

        assert schema["properties"] == {}


class TestReasoningStepMapper:
    def test_with_none_items(self):
        mock_logger = Mock(spec=Logger)
        extracted = reasoning_step_mapper(
            [None, None, None, {}, {"explaination": "h"}],
            logger=mock_logger,
        )
        assert extracted is not None
        mock_logger.warning.assert_not_called()
        mock_logger.exception.assert_not_called()
        assert extracted == [InternalReasoningStep(explaination="h")]

    def test_with_invalid_items(self):
        mock_logger = Mock(spec=Logger)
        extracted = reasoning_step_mapper(
            [None, None, None, {}, {"explaination": 1}],
            logger=mock_logger,
        )
        mock_logger.warning.assert_not_called()
        mock_logger.exception.assert_called_once()
        assert extracted is None
