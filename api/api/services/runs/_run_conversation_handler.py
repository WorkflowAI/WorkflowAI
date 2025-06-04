import asyncio
import logging
from datetime import timedelta

from core.domain.agent_run import AgentRun
from core.storage.key_value_storage import KeyValueStorage
from core.utils.coroutines import capture_errors
from core.utils.uuid import uuid7

from ._stored_message import StoredMessage, StoredMessages

_logger = logging.getLogger(__name__)

_EXPIRY_TIME = timedelta(hours=1)


class RunConversationHandler:
    def __init__(self, task_uid: int, schema_id: int, kv_storage: KeyValueStorage):
        self._kv_storage = kv_storage
        self._task_uid = task_uid
        self._schema_id = schema_id

    def _key(self, key: str) -> str:
        return f"{self._task_uid}:{self._schema_id}:conversation:{key}"

    def _conversation_id_key(self, hash: str) -> str:
        return self._key(f"conversation_id:{hash}")

    def _run_id_key(self, hash: str) -> str:
        return self._key(f"run_id:{hash}")

    async def _assign_run_id(self, message: StoredMessage):
        if not message.agg_hash:
            _logger.warning("No agg hash for message, skipping run id assignment")
            return
        if message.run_id:
            # Already assigned, maybe the frontend already assigned it
            return

        # Get the run id from the key
        key = self._run_id_key(message.agg_hash)
        run_id = await self._kv_storage.get(key)
        if not run_id:
            return
        # Otherwise we renew the expiry
        with capture_errors(logger=_logger, msg="Could not renew run id expiry"):
            await self._kv_storage.expire(key, _EXPIRY_TIME)
        message.run_id = run_id

    async def _find_conversation_id(self, messages: list[StoredMessage]):
        """Goes through messages in reverse order and tries to find a conversation id that matches
        the message hash."""
        for message in reversed(messages):
            if message.role != "assistant":
                # A conversation ID hash can only come from an assistant message
                continue

            if not message.agg_hash:
                _logger.warning("No agg hash for message, skipping conversation id assignment")
                return None

            # Try to find a conversation id that matches the message hash
            key = self._conversation_id_key(message.agg_hash)
            # We pop the key, we will re-add the new hash over it anyway
            if conversation_id := await self._kv_storage.pop(key):
                return conversation_id
        return None

    async def handle_run(self, run: AgentRun, stored_messages: StoredMessages):
        """Try to find a conversation id and run id for messages in a run."""

        # We are still going if there are no messages, we still need to assign a conversation id
        # and set the hash for the run idn==
        # Compute all hashes
        baseline_history = stored_messages.compute_hashes(run.group.properties)

        # Try to assign the conversation id
        if not run.conversation_id:
            run.conversation_id = await self._find_conversation_id(stored_messages.messages)

        # Assign run id to assistant messages when available
        async with asyncio.TaskGroup() as tg:
            for message in stored_messages.messages:
                if message.role == "assistant":
                    tg.create_task(self._assign_run_id(message))

        # Compute the final message and compute its id
        final_message = StoredMessage(
            role="assistant",
            content=list(run.message_content_iterator()),
        )

        # Compute the final message hash
        final_hash = StoredMessages.aggregate_hashes(
            [
                *baseline_history,
                final_message.model_hash(),
            ],
        )

        if not run.conversation_id:
            run.conversation_id = str(uuid7())

        # Store the new values in redis
        await self._kv_storage.set(self._conversation_id_key(final_hash), run.conversation_id, _EXPIRY_TIME)
        await self._kv_storage.set(self._run_id_key(final_hash), run.id, _EXPIRY_TIME)
