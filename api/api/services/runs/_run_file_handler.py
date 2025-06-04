import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from api.services.runs._stored_message import StoredMessages
from core.domain.agent_run import TaskRunIO
from core.domain.fields.file import File
from core.domain.task_io import SerializableTaskIO
from core.domain.task_variant import VariantIO
from core.runners.workflowai.utils import (
    FileWithKeyPath,
    download_file,
    extract_files,
)
from core.storage.azure.azure_blob_file_storage import FileStorage
from core.storage.file_storage import FileData
from core.utils.coroutines import sentry_wrap
from core.utils.dicts import InvalidKeyPathError, set_at_keypath

_logger = logging.getLogger("RunsService")


class FileHandler:
    def __init__(self, file_storage: FileStorage, folder_path: str):
        self._file_storage = file_storage
        self._folder_path = folder_path

    @classmethod
    def _extract_files(
        cls,
        agent_io: SerializableTaskIO,
        payload: Any,
    ) -> list[FileWithKeyPath]:
        _, _, input_files = extract_files(agent_io.json_schema, payload)

        return input_files

    async def handle_run(self, run: TaskRunIO, task_variant: VariantIO, messages: StoredMessages | None):
        raw_input_dict = messages.model_extra if messages else run.task_input
        input_files = self._extract_files(task_variant.input_schema, raw_input_dict)
        output_files = self._extract_files(task_variant.output_schema, run.task_output)

        async with asyncio.TaskGroup() as tg:
            for file in input_files:
                tg.create_task(sentry_wrap(self._handle_file(file)))
            for file in output_files:
                tg.create_task(sentry_wrap(self._handle_file(file)))
            if messages:
                for file in messages.file_iterator():
                    tg.create_task(sentry_wrap(self._handle_file(file)))

        # No need to apply the files from the messages, the input will be rewritten later anyway
        if raw_input_dict:
            self._apply_files(raw_input_dict, input_files, include={"content_type", "url", "storage_url"})
        self._apply_files(run.task_output, output_files, include={"content_type", "url", "storage_url"})

    async def _handle_file(self, file: File):
        if not file.url and not file.data:
            # Skipping, only reason a file might not have data is if it's private
            return

        if file.url and not file.data:
            await download_file(file)

        bts = file.content_bytes()
        if not bts:
            _logger.warning("file has no content bytes", extra={"file": file.model_dump(exclude={"data"})})
            # Skipping, only reason a file might not have data is if it's private
            return

        # Here we can just set the storage url.
        # if we have a file with keypath it will be assigned to the model, but if we have a file it will be stored in extras
        storage_url = await self._file_storage.store_file(
            FileData(contents=bts, content_type=file.content_type),
            folder_path=self._folder_path,
        )
        file.storage_url = storage_url  # pyright: ignore [reportAttributeAccessIssue]

        if file.url and file.url.startswith("data:"):
            file.url = None
        # Clearing data field
        if storage_url:
            file.data = None
            try:
                file.model_fields_set.remove("data")
            except KeyError:
                pass
            if not file.url:
                file.url = storage_url

    @classmethod
    def _apply_files(
        cls,
        payload: dict[str, Any],
        files: Iterable[FileWithKeyPath],
        include: set[str] | None,
    ):
        for file in files:
            if not file.url:
                file.url = file.storage_url
            try:
                set_at_keypath(
                    payload,
                    file.key_path,
                    file.model_dump(include=include, exclude_none=True),
                )
            except InvalidKeyPathError as e:
                _logger.exception(
                    "Error setting file in task run input",
                    extra={"file": file.model_dump(exclude={"data"})},
                    exc_info=e,
                )
                continue
