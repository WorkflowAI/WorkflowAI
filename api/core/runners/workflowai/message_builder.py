import logging
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from api.services.runs._stored_message import StoredMessage, StoredMessages
from core.domain.errors import BadRequestError
from core.domain.fields.file import File, FileKind
from core.domain.message import Message, MessageContent
from core.domain.task_io import SerializableTaskIO
from core.utils.schemas import InvalidSchemaError, JsonSchema
from core.utils.templates import TemplateManager


class MessageBuilder:
    def __init__(
        self,
        template_manager: TemplateManager,
        input_schema: SerializableTaskIO,
        messages: list[Message] | None,
        logger: logging.Logger,
    ):
        self._template_manager = template_manager
        self._input_schema = input_schema
        self._version_messages = messages
        self._logger = logger

    @classmethod
    def _extract_files(  # noqa: C901
        cls,
        schema: JsonSchema,
        input: Any,
        base_key_path: list[str | int],
        acc: dict[str, File],
    ):
        """Extracts FileWithKeyPath objects from the input.
        Payload is removed from the original input"""

        def _dive(key: int | str):
            try:
                child_schema = schema.child_schema(key, follow_refs=False)
            except InvalidSchemaError:
                return None
            # Check if child schema is a file child_schema
            ref = child_schema.schema.get("$ref")
            if not ref or not ref.startswith("#/$defs/"):
                # Not a file, we can just dive
                cls._extract_files(child_schema, input[key], [*base_key_path, key], acc)
                return False
            # We are in a file
            try:
                file = File.model_validate(input[key])
            except ValidationError as e:
                raise BadRequestError(f"Invalid file with key {key}: {str(e)}", capture=True) from e
            file.format = FileKind.from_ref_name(ref[8:])
            key_path = ".".join(str(key) for key in [*base_key_path, key])
            acc[key_path] = file
            return True

        if isinstance(input, dict):
            for key in list(input.keys()):  # pyright: ignore [reportUnknownArgumentType, reportUnknownVariableType]
                if not isinstance(key, str):
                    continue
                if _dive(key):
                    del input[key]
            return

        if isinstance(input, list):
            indices_to_remove: list[int] = []
            for idx in range(len(input)):  # pyright: ignore [reportUnknownArgumentType]
                if _dive(idx):
                    indices_to_remove.append(idx)  # noqa: PERF401
            for idx in reversed(indices_to_remove):
                del input[idx]
            return

    def _sanitize_files(self, input: Any):
        acc: dict[str, File] = {}
        self._extract_files(JsonSchema(self._input_schema.json_schema), input, [], acc)
        return acc

    async def _handle_templated_messages(self, messages: StoredMessages) -> Sequence[Message] | None:
        if not messages.model_extra:
            self._logger.warning("No extra fields provided, but the input schema is a templated message schema")
            return messages.messages
        if not self._version_messages:
            # There are no version messages, so nothing to template
            # This would be a very weird case so logging a warning
            self._logger.warning("No version messages provided, but the input schema is not RawMessagesSchema")
            return None

        version_messages = self._version_messages
        if self._input_schema.has_files:
            # TODO: add a test that the input is not updated
            files = self._sanitize_files(messages.model_extra)
        else:
            files = None
        renderer = _MessageRenderer(self._template_manager, messages.model_extra, files or {})

        version_messages = await renderer.render_messages(version_messages)
        return [*version_messages, *messages.messages]

    async def extract(self, input: Any):
        # No matter what, the input should be a valid Messages object
        if isinstance(input, list):
            messages = StoredMessages.with_messages(*(StoredMessage.model_validate(m) for m in input))  # pyright: ignore [reportUnknownVariableType]
        else:
            try:
                # Stored messages allows extras
                messages = StoredMessages.model_validate(input)
            except ValidationError as e:
                # Capturing for now just in case
                raise BadRequestError(f"Input is not a valid list of messages: {str(e)}", capture=True) from e

        if self._input_schema.uses_raw_messages:
            # Version messages are not templated since there is no field in the input schema
            # So we can just inline as is
            if self._version_messages:
                return [*self._version_messages, *messages.messages]
            return messages.messages

        return await self._handle_templated_messages(messages)


class _MessageRenderer:
    def __init__(self, template_manager: TemplateManager, input: Any, files: dict[str, File]):
        self._template_manager = template_manager
        self._input = input
        self._files = files

    async def _render_file(self, file: File | None):
        if not file:
            return None
        if template_key := file.template_key():
            # File is a templated file so we can just pop the key
            try:
                return self._files.pop(template_key)
            except KeyError:
                raise BadRequestError(f"Missing file with key {template_key}")
        return None

    async def _render_text(self, text: str | None):
        if not text:
            return None

        return await self._template_manager.render_template(text, self._input)

    async def render_content(self, content: MessageContent):
        update: dict[str, Any] = {}
        if file := await self._render_file(content.file):
            update["file"] = file

        if (text := await self._render_text(content.text)) is not None:
            update["text"] = text[0]

        if update:
            return content.model_copy(update=update)
        return content

    async def render_messages(self, messages: list[Message]):
        rendered = [
            Message(
                role=m.role,
                content=[await self.render_content(c) for c in m.content],
            )
            for m in messages
        ]

        if self._files:
            # Some files were unused
            # TODO: We need to be smarter about this but for now let's just append
            # Them at the end of the last message
            last_message = rendered[-1]
            if last_message.role == "user":
                rendered[-1].content.extend([MessageContent(file=f) for f in self._files.values()])
            else:
                rendered.append(Message(role="user", content=[MessageContent(file=f) for f in self._files.values()]))
        return rendered
