from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from unittest.mock import Mock

from pytest_httpx import HTTPXMock

from api.services.runs._stored_message import StoredMessages
from core.domain.consts import INPUT_KEY_MESSAGES
from core.domain.task_io import SerializableTaskIO
from core.runners.workflowai.utils import (
    FileWithKeyPath,
)

from ._run_file_handler import FileHandler


class TestFileHandlerApplyFiles:
    async def test_apply_files_with_include(self):
        payload = {"image": {"data": "1234"}}
        files = [
            FileWithKeyPath(
                key_path=["image"],
                storage_url="https://test-url.com/bla",
                data="1234",
                content_type="image",
            ),
        ]
        FileHandler._apply_files(  # pyright: ignore [reportPrivateUsage]
            payload,
            files,
            include={"content_type", "url", "storage_url"},
        )
        assert payload == {
            "image": {
                "url": "https://test-url.com/bla",
                "content_type": "image",
                "storage_url": "https://test-url.com/bla",
            },
        }


class TestHandleRun:
    @dataclass
    class RunIO:
        task_input: Any
        task_output: Any

    @dataclass
    class VariantIO:
        input_schema: SerializableTaskIO
        output_schema: SerializableTaskIO

    async def test_handle_run_with_replies(self, httpx_mock: HTTPXMock, mock_file_storage: Mock):
        httpx_mock.add_response(
            url="https://test-url.com/bla.jpg",
            content=b"1234",
            status_code=200,
        )
        mock_file_storage.store_file.return_value = "https://bliblu.jpg"
        agent_input = {
            "hello": "world",
            INPUT_KEY_MESSAGES: [
                {
                    "role": "user",
                    "content": [
                        {
                            "file": {
                                "url": "https://test-url.com/bla.jpg",
                            },
                        },
                    ],
                },
            ],
        }
        run_io = self.RunIO(task_input=deepcopy(agent_input), task_output=None)
        task_variant = self.VariantIO(
            input_schema=SerializableTaskIO.from_json_schema(
                {
                    "format": "messages",
                    "type": "object",
                    "properties": {
                        "hello": {"type": "string"},
                    },
                },
                streamline=True,
            ),
            output_schema=SerializableTaskIO.from_json_schema({}),
        )
        file_handler = FileHandler(
            file_storage=mock_file_storage,
            folder_path="",
        )
        messages = StoredMessages.model_validate(run_io.task_input)
        await file_handler.handle_run(run_io, task_variant, messages)

        # That should be left untouched since we have messages
        assert run_io.task_input == agent_input
        assert messages.messages[0].content[0].file.storage_url == "https://bliblu.jpg"  # type: ignore
        assert messages.model_dump(exclude_none=True) == {
            "hello": "world",
            INPUT_KEY_MESSAGES: [
                {
                    "role": "user",
                    "content": [
                        {
                            "file": {
                                "url": "https://test-url.com/bla.jpg",
                                "storage_url": "https://bliblu.jpg",
                                "content_type": "image/jpeg",
                            },
                        },
                    ],
                },
            ],
        }

    async def test_handle_run_with_file_in_extra(self, httpx_mock: HTTPXMock, mock_file_storage: Mock):
        httpx_mock.add_response(
            url="https://test-url.com/bla.jpg",
            content=b"1234",
            status_code=200,
        )
        mock_file_storage.store_file.return_value = "https://bliblu.jpg"
        agent_input = {
            "image_url": {"url": "https://test-url.com/bla.jpg"},
            INPUT_KEY_MESSAGES: [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": "hello",
                        },
                    ],
                },
            ],
        }
        run_io = self.RunIO(task_input=deepcopy(agent_input), task_output=None)
        task_variant = self.VariantIO(
            input_schema=SerializableTaskIO.from_json_schema(
                {
                    "format": "messages",
                    "type": "object",
                    "properties": {
                        "image_url": {"$ref": "#/$defs/Image"},
                    },
                },
                streamline=True,
            ),
            output_schema=SerializableTaskIO.from_json_schema({}),
        )
        file_handler = FileHandler(
            file_storage=mock_file_storage,
            folder_path="",
        )
        messages = StoredMessages.model_validate(run_io.task_input)
        await file_handler.handle_run(run_io, task_variant, messages)

        # That should be left untouched since we have messages
        assert run_io.task_input == agent_input
        assert messages.model_dump(exclude_none=True) == {
            "image_url": {
                "url": "https://test-url.com/bla.jpg",
                "storage_url": "https://bliblu.jpg",
                "content_type": "image/jpeg",
            },
            INPUT_KEY_MESSAGES: [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": "hello",
                        },
                    ],
                },
            ],
        }
