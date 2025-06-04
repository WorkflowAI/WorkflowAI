from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from api.services.runs._run_conversation_handler import RunConversationHandler
from api.services.runs._stored_message import StoredMessages
from core.domain.message import Message
from tests import models as test_models


@pytest.fixture
def handler(mock_storage: Mock):
    return RunConversationHandler(1, 1, mock_storage.kv)


@pytest.fixture(autouse=True)
def patched_uuid7():
    with patch("api.services.runs._run_conversation_handler.uuid7", return_value=UUID(int=1)):
        yield


class TestHandleRun:
    async def test_no_assistant_message(self, handler: RunConversationHandler, mock_storage: Mock):
        """No assistant message. Run should have a conversation id assigned and the input should be untouched"""
        run = test_models.task_run_ser(
            task_input={
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": "Hello, world!"}],
                    },
                ],
            },
            task_output="hello",
        )
        messages = StoredMessages.model_validate(run.task_input)
        assert not run.conversation_id, "sanity check"
        await handler.handle_run(run, messages)

        mock_storage.kv.get.assert_not_called()
        assert mock_storage.kv.set.call_count == 2
        call_args_list = sorted(mock_storage.kv.set.call_args_list, key=lambda x: x[0])
        assert call_args_list[0].args == (
            "1:1:conversation:conversation_id:2535ac77ef0eea3b2a5306b42a59f3b6e42f31ee0e14a035033bb0c528068a0a",
            str(UUID(int=1)),
            timedelta(hours=1),
        )
        assert call_args_list[1].args == (
            "1:1:conversation:run_id:2535ac77ef0eea3b2a5306b42a59f3b6e42f31ee0e14a035033bb0c528068a0a",
            run.id,
            timedelta(hours=1),
        )
        assert run.conversation_id == str(UUID(int=1))
        # Task input should be untouched
        assert messages.dump_for_input() == {
            "workflowai.messages": [
                {
                    "role": "user",
                    "content": [{"text": "Hello, world!"}],
                },
            ],
        }

    async def test_with_assistant_message(self, handler: RunConversationHandler, mock_storage: Mock):
        """With assistant message. Run should have a conversation id assigned and the input should be untouched"""
        run = test_models.task_run_ser(
            task_input={
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": "Hello, world!"}],
                    },
                    {
                        "role": "assistant",
                        "content": [{"text": "Hello back!"}],
                    },
                    {
                        "role": "user",
                        "content": [{"text": "What is the weather in Tokyo?"}],
                    },
                ],
            },
        )
        mock_storage.kv.get.return_value = str(UUID(int=2))
        messages = StoredMessages.model_validate(run.task_input)
        await handler.handle_run(run, messages)
        assert messages.dump_for_input() == {
            "workflowai.messages": [
                {
                    "role": "user",
                    "content": [{"text": "Hello, world!"}],
                },
                {
                    "role": "assistant",
                    "content": [{"text": "Hello back!"}],
                    "run_id": str(UUID(int=2)),
                },
                {
                    "role": "user",
                    "content": [{"text": "What is the weather in Tokyo?"}],
                },
            ],
        }
        mock_storage.kv.get.assert_called_once()
        assert mock_storage.kv.set.call_count == 2

    async def test_with_extra_input(self, handler: RunConversationHandler, mock_storage: Mock):
        """With extra input. Run should have a conversation id assigned and the input should be untouched"""
        run = test_models.task_run_ser(
            task_input={
                "name": "Cecily",
                "workflowai.replies": [
                    {
                        "role": "assistant",
                        "content": [{"text": "Hello, world!"}],
                    },
                    {
                        "role": "user",
                        "content": [{"text": "What is the weather in Tokyo?"}],
                    },
                ],
            },
        )
        mock_storage.kv.get.return_value = str(UUID(int=2))
        messages = StoredMessages.model_validate(run.task_input)
        await handler.handle_run(run, messages)
        mock_storage.kv.get.assert_called_once()
        assert mock_storage.kv.set.call_count == 2

        assert messages.dump_for_input() == {
            "name": "Cecily",
            "workflowai.messages": [
                {
                    "role": "assistant",
                    "content": [{"text": "Hello, world!"}],
                    "run_id": str(UUID(int=2)),
                },
                {
                    "role": "user",
                    "content": [{"text": "What is the weather in Tokyo?"}],
                },
            ],
        }

    async def test_with_no_messages(self, handler: RunConversationHandler, mock_storage: Mock):
        """With no messages. Run should have a conversation id assigned and the input should be untouched"""
        run = test_models.task_run_ser(
            task_input={
                "hello": "world",
                "something_none": None,
            },
        )
        mock_storage.kv.get.return_value = str(UUID(int=2))
        messages = StoredMessages.model_validate(run.task_input)
        await handler.handle_run(run, messages)
        assert mock_storage.kv.set.call_count == 2
        assert messages.dump_for_input() == {
            "hello": "world",
            "something_none": None,
        }

    async def test_with_empty_messages(self, handler: RunConversationHandler, mock_storage: Mock):
        """With empty messages. Run should have a conversation id assigned and the input should be untouched"""
        run = test_models.task_run_ser(
            task_input={
                "name": "Cecily",
                "workflowai.messages": [],
            },
        )
        messages = StoredMessages.model_validate(run.task_input)
        await handler.handle_run(run, messages)
        assert mock_storage.kv.set.call_count == 2
        assert messages.dump_for_input() == {
            "name": "Cecily",
            "workflowai.messages": [],
        }

    async def test_with_version_messages(self, handler: RunConversationHandler, mock_storage: Mock):
        """With version messages. Run should have a conversation id assigned and the input should be untouched"""
        run = test_models.task_run_ser(
            task_input={
                "name": "Cecily",
                "workflowai.messages": [],
            },
        )
        messages = StoredMessages.model_validate(run.task_input)
        run.group.properties.messages = [
            Message.with_text("Hello, world!", role="system"),
        ]
        await handler.handle_run(run, messages)
        assert mock_storage.kv.set.call_count == 2

        run2 = test_models.task_run_ser(
            task_input={
                "name": "Cecily",
                "workflowai.messages": [],
            },
        )
        messages2 = StoredMessages.model_validate(run2.task_input)
        run2.group.properties.messages = [
            Message.with_text("Hello, world 2!", role="system"),
        ]
        await handler.handle_run(run2, messages2)
        assert mock_storage.kv.set.call_count == 4

        # Checking that the hashes are different
        conversation_keys = [
            c.args[0]
            for c in mock_storage.kv.set.call_args_list
            if c.args[0].startswith("1:1:conversation:conversation_id:")
        ]
        assert len(conversation_keys) == 2
        assert conversation_keys[0] != conversation_keys[1]
