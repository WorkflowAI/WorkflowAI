# pyright: reportPrivateUsage=false

import logging
from unittest.mock import Mock

import pytest

from api.services.runs._stored_message import StoredMessages
from core.domain.fields.file import File
from core.domain.message import Message, MessageContent
from core.domain.task_io import SerializableTaskIO
from core.runners.workflowai.message_builder import MessageBuilder
from core.utils.schema_sanitation import streamline_schema
from core.utils.templates import TemplateManager


@pytest.fixture
def mock_builder():
    return MessageBuilder(
        template_manager=TemplateManager(),
        input_schema=SerializableTaskIO.from_json_schema({}),
        messages=None,
        logger=Mock(spec=logging.Logger),
    )


class TestExtractFiles:
    def test_extract_file(self, mock_builder: MessageBuilder):
        mock_builder._input_schema.json_schema = streamline_schema(
            {
                "properties": {
                    "file": {"$ref": "#/$defs/File"},
                    "hello": {"type": "string"},
                },
            },
        )
        input = {
            "file": {"url": "https://blabla"},
            "hello": "world",
        }
        files = mock_builder._sanitize_files(input)
        assert len(files) == 1
        assert input == {
            "hello": "world",
        }

    def test_extract_files_array(self, mock_builder: MessageBuilder):
        mock_builder._input_schema.json_schema = streamline_schema(
            {
                "properties": {
                    "files": {"type": "array", "items": {"$ref": "#/$defs/File"}},
                    "hello": {"type": "string"},
                },
            },
        )
        input = {
            "files": [{"url": "https://blabla"}, {"url": "https://blabla2"}],
            "hello": "world",
        }
        files = mock_builder._sanitize_files(input)
        assert len(files) == 2
        assert input == {
            "files": [],
            "hello": "world",
        }


class TestHandleTemplatedMessages:
    async def test_no_file(self, mock_builder: MessageBuilder):
        mock_builder._version_messages = [
            Message.with_text("Hello {{name}}"),
        ]
        mock_builder._input_schema.json_schema = streamline_schema(
            {
                "properties": {
                    "name": {"type": "string"},
                },
            },
        )

        messages = await mock_builder._handle_templated_messages(
            StoredMessages.model_validate(
                {
                    "name": "John",
                },
            ),
        )
        assert messages == [
            Message.with_text("Hello John"),
        ]

    async def test_with_file_in_dedicated_slot(self, mock_builder: MessageBuilder):
        mock_builder._version_messages = [
            Message.with_text("Describe this image"),
            Message.with_file_url("{{ image_url}}"),
        ]
        mock_builder._input_schema.json_schema = streamline_schema(
            {
                "properties": {
                    "image_url": {"$ref": "#/$defs/File"},
                },
            },
        )
        messages = await mock_builder._handle_templated_messages(
            StoredMessages.model_validate(
                {
                    "image_url": "https://blabla",
                },
            ),
        )
        assert messages == [
            Message.with_text("Describe this image"),
            Message.with_file_url("https://blabla"),
        ]

    async def test_with_file_in_raw_text(self, mock_builder: MessageBuilder):
        mock_builder._version_messages = [
            Message.with_text("Describe this image {{ image_url}}"),
        ]
        mock_builder._input_schema.json_schema = streamline_schema(
            {
                "properties": {
                    "image_url": {"$ref": "#/$defs/File"},
                },
            },
        )
        messages = await mock_builder._handle_templated_messages(
            StoredMessages.model_validate(
                {
                    "image_url": "https://blabla",
                },
            ),
        )
        assert messages == [
            Message(
                role="user",
                content=[
                    MessageContent(text="Describe this image "),
                    MessageContent(file=File(url="https://blabla")),
                ],
            ),
        ]

    async def test_with_file_in_raw_text_in_system(self, mock_builder: MessageBuilder):
        mock_builder._version_messages = [
            Message.with_text("Describe this image {{ image_url}}", role="system"),
        ]
        mock_builder._input_schema.json_schema = streamline_schema(
            {
                "properties": {
                    "image_url": {"$ref": "#/$defs/File"},
                },
            },
        )
        messages = await mock_builder._handle_templated_messages(
            StoredMessages.model_validate(
                {
                    "image_url": "https://blabla",
                },
            ),
        )
        assert messages == [
            Message(
                role="system",
                content=[
                    MessageContent(text="Describe this image "),
                ],
            ),
            Message(
                role="user",
                content=[
                    MessageContent(file=File(url="https://blabla")),
                ],
            ),
        ]
