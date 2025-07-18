import asyncio
import json
import logging
import re
import time
from collections.abc import Sequence
from copy import deepcopy
from typing import Any, Callable, Iterable, Literal, NamedTuple, Optional, TypeVar, cast

from pydantic import TypeAdapter, ValidationError
from typing_extensions import override

from api.services.providers_service import shared_provider_factory
from core.domain.agent_run_result import INTERNAL_AGENT_RUN_RESULT_SCHEMA_KEY, AgentRunResult
from core.domain.consts import (
    METADATA_KEY_PROVIDER_NAME,
    METADATA_KEY_USED_MODEL,
    METADATA_KEY_USED_PROVIDERS,
)
from core.domain.errors import (
    BadRequestError,
    InvalidFileError,
    InvalidRunOptionsError,
)
from core.domain.fields.file import File
from core.domain.fields.image_options import ImageOptions
from core.domain.message import Message, MessageContent, MessageDeprecated, Messages
from core.domain.metrics import send_gauge
from core.domain.models.model_data import FinalModelData, ModelData
from core.domain.models.model_data_mapping import MODEL_DATAS
from core.domain.models.models import Model
from core.domain.models.utils import get_model_data, get_model_provider_data
from core.domain.reasoning_step import INTERNAL_REASONING_STEPS_SCHEMA_KEY
from core.domain.run_output import RunOutput
from core.domain.structured_output import StructuredOutput
from core.domain.task_group_properties import FewShotConfiguration, FewShotExample, TaskGroupProperties
from core.domain.task_io import RawJSONMessageSchema, RawStringMessageSchema, SerializableTaskIO
from core.domain.task_run_reply import RunReply
from core.domain.task_typology import TaskTypology
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tenant_data import ProviderSettings
from core.domain.tool import Tool
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.domain.types import AgentInput
from core.providers.base.abstract_provider import AbstractProvider
from core.providers.base.provider_error import (
    AgentRunFailedError,
    MaxToolCallIterationError,
    ModelDoesNotSupportMode,
)
from core.providers.base.provider_options import ProviderOptions
from core.runners.abstract_runner import AbstractRunner, CacheFetcher
from core.runners.builder_context import BuilderInterface
from core.runners.workflowai.internal_tool import build_all_internal_tools
from core.runners.workflowai.message_builder import MessageBuilder
from core.runners.workflowai.message_fixer import MessageAutofixer
from core.runners.workflowai.provider_pipeline import ProviderPipeline
from core.runners.workflowai.templates import (
    TemplateName,
    get_template_content,
    get_template_without_input_schema,
    sanitize_template_name,
)
from core.runners.workflowai.tool_cache import ToolCache
from core.runners.workflowai.utils import (
    FileWithKeyPath,
    ToolCallRecursionError,
    assign_files,
    cleanup_provider_json,
    convert_pdf_to_images,
    download_file,
    extract_files,
    reasoning_step_mapper,
    remove_files_from_schema,
    sanitize_model_and_provider,
    split_tools,
)
from core.utils.background import add_background_task
from core.utils.dicts import set_at_keypath
from core.utils.file_utils.file_utils import extract_text_from_file_base64
from core.utils.generics import T
from core.utils.json_utils import parse_tolerant_json
from core.utils.schema_augmentation_utils import (
    add_agent_run_result_to_schema,
    add_reasoning_steps_to_schema,
)
from core.utils.schemas import clean_json_string, is_schema_only_containing_one_property
from core.utils.templates import InvalidTemplateError, TemplateManager

from .workflowai_options import WorkflowAIRunnerOptions

logger = logging.getLogger(__name__)


MAX_TOOL_CALL_ITERATIONS = 10

_FileVar = TypeVar("_FileVar", bound=File)


class BuildUserMessageContentResult(NamedTuple):
    content: str
    should_remove_input_schema: bool


class PreparedOutputSchema(NamedTuple):
    # If prepared schema is None we deal with a plain json
    prepared_schema: dict[str, Any] | None
    # Images are removed from the schema since they are handled separately
    min_file_count: int = 0
    max_file_count: int | None = None

    @property
    def no_schema(self) -> bool:
        return self.prepared_schema is None or not self.prepared_schema.get("properties", {})


class WorkflowAIRunner(AbstractRunner[WorkflowAIRunnerOptions]):
    """
    A runner that generates a prompt based on:
    - the output json schema
    - the input schema and data serialized to a yaml with comments
    - the task instructions

    The prompt is separated in a system and user message and the version is computed based on the generated
    messages for a standard input (an input generated from the input class with default values).
    """

    # TODO: this should be injected
    provider_factory = shared_provider_factory()

    internal_tools = build_all_internal_tools()

    template_manager = TemplateManager()

    def __init__(
        self,
        task: SerializableTaskVariant,
        properties: Optional[TaskGroupProperties] = None,
        options: Optional[WorkflowAIRunnerOptions] = None,
        custom_configs: list[ProviderSettings] | None = None,
        cache_fetcher: Optional[CacheFetcher] = None,
        metadata: dict[str, Any] | None = None,
        stream_deltas: bool = False,
        # TODO: this is not set anywhere for now
        timeout: float | None = None,
        use_fallback: Literal["auto", "never"] | list[Model] | None = None,
    ):
        super().__init__(
            task=task,
            properties=properties,
            options=options,
            cache_fetcher=cache_fetcher,
            metadata=metadata,
        )

        if self._options.provider:
            # This will throw a ProviderDoesNotSupportModelError if the provider does not support the model
            get_model_provider_data(self._options.provider, self._options.model)
        self._stream_deltas = stream_deltas

        self._custom_configs = custom_configs

        # internal tool cache contains the result of internal tool calls
        self._internal_tool_cache = ToolCache()
        # For external tools we still use a cache to ensure the unicity of tool calls
        # Even though we won't cache the result
        self._external_tool_cache = ToolCache()
        self._enabled_internal_tools, self._external_tools = split_tools(
            self.internal_tools,
            self.properties.enabled_tools,
        )

        self._typology = self.task.typology()
        self._prepared_output_schema = self._prepare_output_schema(
            self.task.output_schema,
            self.properties.is_chain_of_thought_enabled or False,
            self.is_tool_use_enabled,
            self._typology,
        )
        self._timeout = timeout
        # Not sure why pyright looses the literal if not specified here
        self._use_fallback: Literal["auto", "never"] | list[Model] | None = use_fallback

    @override
    def version(self) -> str:
        # This version is not super important since the templates are versioned
        # separately
        return "v0.1.0"

    def _all_tools(self) -> Iterable[Tool]:
        return (
            *(t.definition for t in self._enabled_internal_tools.values()),
            *self._external_tools.values(),
        )

    def _system_message_content(
        self,
        template: str,
        instructions: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any] | None,
    ) -> str:
        """
        Contains instructions about the input and output schemas

        Prompt is inspired by Instructor's ones:

        https://github.com/jxnl/instructor/blob/021cf34ac27ed97cb8d95af372030e7d800533c3/instructor/process_response.py#L169
        """

        return (
            template.replace("{{input_schema}}", json.dumps(input_schema, indent=2))
            .replace("{{output_schema}}", json.dumps(output_schema, indent=2) if output_schema else "")
            .replace("{{instructions}}", instructions)
        )

    def _user_message_content(self, template: str, input: Any) -> str:
        """
        Generate a user message based on the task input
        """

        if self._options.examples:
            examples_str = "\n\n".join([self.example_str(example) for example in self._options.examples])
            examples_str = f"\n\nExamples:\n\n{examples_str}"
        else:
            examples_str = ""

        return template.replace("{{input_data}}", json.dumps(input, indent=2)).replace("{{examples}}", examples_str)

    def _build_user_message_content(
        self,
        user_template: str,
        input_copy: dict[str, Any],
        input_schema: dict[str, Any],
        has_inlined_files: bool,
    ) -> BuildUserMessageContentResult:
        """
        Build the user message content based on the input schema and data.
        If the schema only contains one file property, return a simple prompt.
        Otherwise, format the input data using the user template.
        """
        if not input_copy:
            return BuildUserMessageContentResult(
                content="Follow the instructions",
                should_remove_input_schema=True,
            )

        is_schema_only_containing_one_file_property = is_schema_only_containing_one_property(input_schema)

        if not has_inlined_files and is_schema_only_containing_one_file_property.value:
            return BuildUserMessageContentResult(
                content=is_schema_only_containing_one_file_property.field_description or "The input is:",
                should_remove_input_schema=True,
            )
        return BuildUserMessageContentResult(
            content=self._user_message_content(user_template, input_copy),
            should_remove_input_schema=not input_schema or not input_schema.get("properties", {}),
        )

    def _should_download_file(self, provider: AbstractProvider[Any, Any], file: File) -> bool:
        if file.data:
            return False

        if not provider.requires_downloading_file(file, self._options.model):
            return False

        return True

    async def _download_file_and_update_input(
        self,
        provider: AbstractProvider[Any, Any],
        file: FileWithKeyPath,
        input: AgentInput,
    ):
        # Check should not be needed here since we only pass files that should effectively be downloaded
        if file.data:
            return

        await download_file(file)

        set_at_keypath(
            input,
            file.key_path,
            file.model_dump(mode="json", exclude={"key_path"}, exclude_none=True),
        )

    def _assert_support_for_image_input(self, model_data: ModelData):
        if not model_data.supports_input_image:
            raise ModelDoesNotSupportMode(
                title="This model is unable to process images",
                msg=f"{model_data.display_name} does not support images.",
            )

    def _assert_support_for_pdf_input(self, model_data: ModelData):
        if not model_data.supports_input_pdf:
            models_supporting_pdfs = (
                data.display_name
                for _, data in MODEL_DATAS.items()
                if isinstance(data, ModelData) and data.supports_input_pdf
            )
            raise ModelDoesNotSupportMode(
                title="This model is unable to process PDFs",
                msg=f"{model_data.display_name} does not support PDFs. Please try again with {', '.join(models_supporting_pdfs)}",
            )

    def _assert_support_for_audio_input(self, model_data: ModelData):
        if not model_data.supports_input_audio:
            raise ModelDoesNotSupportMode(
                title="This model is unable to process audio",
                msg=f"{model_data.display_name} does not support audio.",
            )

    def _check_support_for_files(self, model_data: ModelData, files: Sequence[FileWithKeyPath]):
        # We check for support here to allow bypassing some providers in the pipeline
        # Some providers may support different modes
        # The model settings should be optimistic, at worst the provider will return with an error

        for file in files:
            if file.is_image:
                self._assert_support_for_image_input(model_data)
            if file.is_pdf:
                self._assert_support_for_pdf_input(model_data)
            if file.is_audio:
                self._assert_support_for_audio_input(model_data)
            # TODO: Add more content-type checks as needed

    async def _convert_pdf_to_images(
        self,
        files: list[FileWithKeyPath],
        model_data: ModelData,
    ) -> list[FileWithKeyPath]:
        res: list[FileWithKeyPath] = []
        for file in files:
            if not file.is_pdf or (file.is_pdf and model_data.supports_input_pdf):
                res.append(file)
                continue

            if file.is_pdf and not model_data.supports_input_image:
                raise ModelDoesNotSupportMode(
                    msg=f"{model_data.display_name} is unable to process images",
                )

            try:
                converted = await convert_pdf_to_images(file)
            except Exception as e:
                logger.exception("Error converting pdf to images", exc_info=e)
                # We raise a ModelDoesNotSupportMode error, it will get picked up in the next pipeline step
                raise ModelDoesNotSupportMode(
                    msg=f"{model_data.display_name} is unable to process PDFs",
                )

            res.extend(converted)
        return res

    def _inline_text_files(
        self,
        files: Sequence[FileWithKeyPath],
        input: dict[str, Any],
    ) -> tuple[list[FileWithKeyPath], bool]:
        out: list[FileWithKeyPath] = []
        has_inlined_files = False
        for file in files:
            if file.is_text and file.data:
                text_content = extract_text_from_file_base64(file.data)
                set_at_keypath(input, file.key_path, text_content)
                has_inlined_files = True
                continue
            out.append(file)
        return out, has_inlined_files

    def _pick_template(
        self,
        provider: AbstractProvider[Any, Any],
        data: ModelData,
        is_structured_generation_enabled: bool,
    ):
        sanitized = sanitize_template_name(
            self._options.template_name,
            is_tool_use_enabled=self.is_tool_use_enabled,
            # a bit hacky but we templates that have structured generation enabled do
            # not show the output schema
            is_structured_generation_enabled=is_structured_generation_enabled
            and not self._prepared_output_schema.no_schema,
            supports_input_schema=data.supports_input_schema,
        )
        return provider.sanitize_template(sanitized)

    def _user_message_for_reply(self, reply: RunReply) -> MessageDeprecated:
        if not reply.tool_calls and not reply.user_message:
            # Capturing because the error should have been handled earlier
            raise BadRequestError(
                "No user message or tool calls found in reply",
                extra={"run_id": reply.previous_run_id},
                capture=True,
            )

        content: list[str] = []
        if reply.user_message:
            content.append(reply.user_message)

        message = MessageDeprecated(
            content="\n\n".join(content),
            role=MessageDeprecated.Role.USER,
        )

        if reply.tool_calls:
            message.tool_call_results = [
                ToolCall(
                    id=tool_call.id,
                    tool_name=tool_call.tool_name,
                    tool_input_dict=tool_call.tool_input_dict,
                    result=tool_call.result,
                    error=tool_call.error,
                )
                for tool_call in reply.tool_calls
            ]

        return message

    async def _build_messages_for_reply(self, reply: RunReply):
        return [
            *reply.previous_messages,
            self._user_message_for_reply(reply),  # Inject the external tool call result message
        ]

    async def _apply_templated_instructions(
        self,
        instructions: str,
        input: dict[str, Any],
        input_schema: dict[str, Any],
    ):
        """Apply the instruction templating and remove the variables that were consumed by the template from
        the input and input schema. Keys used by the template are added to the used_input_keys set"""
        return await self.template_manager.render_template(instructions, input)

    async def _remove_keys_from_input(
        self,
        input_schema: dict[str, Any],
        input: AgentInput,
        used_input_keys: set[str],
    ):
        """Remove keys from the input and input schema. Only root keys are supported"""
        input_schema_properties: dict[str, Any] = input_schema.get("properties", {})
        input_schema_required: list[str] = input_schema.get("required", [])
        for key in used_input_keys:
            input.pop(key, None)
            input_schema_properties.pop(key, None)
            try:
                input_schema_required.remove(key)
            except ValueError:
                pass

    async def _extract_image_options(
        self,
        input: AgentInput,
    ) -> tuple[ImageOptions | None, set[str]]:
        """Extract the image options from the input and remove it from the input if possible.
        Returns the keys that were extracted from the input and that should be removed"""
        base = self.properties.image_options
        if not self._prepared_output_schema.min_file_count:
            # There are no images in the output, no need to extract anything
            return None, set()

        if not base:
            base = ImageOptions()
        if not base.image_count:
            base.image_count = self._prepared_output_schema.min_file_count

        # We consider that input can contain the same fields as ImageOptions
        try:
            extracted_options = ImageOptions.model_validate(input)
        except ValidationError:
            return base, set()

        # In case of validation, we can check which key was actually extracted
        extracted_keys = extracted_options.model_dump(exclude_unset=True)

        return base.model_copy(update=extracted_keys), set(extracted_keys.keys())

    _json_schema_regexp = re.compile(r"json[ _-]?schema", re.IGNORECASE)

    def _extract_files_to_download(
        self,
        files: list[_FileVar],
        max_number_of_file_urls: int | None,
        should_download_file: Callable[[_FileVar], bool],
    ):
        # Files that should not be downloaded and that will be passed as links
        files_as_links: list[_FileVar] = []
        # files that should be downloaded
        files_to_download: list[_FileVar] = []

        for f in files:
            if should_download_file(f):
                files_to_download.append(f)
                continue
            if not f.data:
                # File does not contain data so we will pass it as a link
                files_as_links.append(f)

        if max_number_of_file_urls is not None and len(files_as_links) > max_number_of_file_urls:
            # If limit we need to make sure we
            files_to_download.extend(files_as_links[max_number_of_file_urls:])

        return files_to_download

    async def _handle_files_in_messages(
        self,
        messages: Sequence[Message],
        provider: AbstractProvider[Any, Any],
    ):
        # Not using file iterator here as it creates a copy of files
        files: list[File] = []
        for m in messages:
            files.extend((c.file for c in m.content if c.file))

        if not files:
            return

        download_start_time = time.time()
        # TODO:
        # files = await self._convert_pdf_to_images(files, model_data)
        # self._check_support_for_files(model_data, files)

        files_to_download = self._extract_files_to_download(
            files,
            provider.max_number_of_file_urls,
            lambda f: self._should_download_file(provider, f),
        )
        if files_to_download:
            try:
                async with asyncio.TaskGroup() as tg:
                    for file in files_to_download:
                        # We want to update the provided input because file data
                        # should be propagated upstream to avoid having to download files twice
                        tg.create_task(download_file(file))
            except* InvalidFileError as eg:
                raise eg.exceptions[0]
            # Here we update the input copy instead of the provided input
            # Since the data will just be provided to the provider
            # files, has_inlined_files = self._inline_text_files(files, input_copy)

            download_duration = time.time() - download_start_time

            if builder := self._get_builder_context():
                builder.record_file_download_seconds(download_duration)

    @classmethod
    def _fix_messages(cls, messages: Sequence[Message]):
        try:
            return MessageAutofixer().fix(messages)
        except ValueError as e:
            raise BadRequestError(msg=str(e)) from e

    async def _inline_messages(
        self,
        messages: Sequence[Message],
        provider: AbstractProvider[Any, Any],
        structured_output: bool,
        use_tools: bool,
    ) -> list[MessageDeprecated]:
        # First handle all files as needed
        await self._handle_files_in_messages(messages, provider)
        messages = self._fix_messages(messages)

        final = Messages.with_messages(*messages)

        if structured_output or self._prepared_output_schema.prepared_schema is None:
            return final.to_deprecated()

        # Otherwise we append the output to the first system message
        final = final.model_copy(deep=True)
        try:
            system_message = next(m for m in final.messages if m.role in ("system", "developer"))
        except StopIteration:
            system_message = Message(role="system", content=[MessageContent(text="")])
            final.messages.insert(0, system_message)

        try:
            text_content = next(m for m in system_message.content if m.text is not None)
        except StopIteration:
            text_content = MessageContent(text="")
            system_message.content.append(text_content)

        if text_content.text and self._json_schema_regexp.search(text_content.text):
            return final.to_deprecated()

        tool_call_str = "either tool call(s) or " if use_tools else ""
        schema_str = (
            f""" enforcing the following schema:
```json
{json.dumps(self._prepared_output_schema.prepared_schema, indent=2)}
```"""
            if self._prepared_output_schema.prepared_schema
            else ""
        )
        suffix = f"Return {tool_call_str}a single JSON object{schema_str}"
        prefix = f"{text_content.text}\n\n" if text_content.text else ""
        text_content.text = f"{prefix}{suffix}"
        return final.to_deprecated()

    async def _extract_raw_messages(self, input: AgentInput) -> Sequence[Message] | None:
        if not self.task.input_schema.uses_messages and not self._options.messages:
            return None

        builder = MessageBuilder(self.template_manager, self.task.input_schema, self._options.messages, logger)
        return await builder.extract(input)

    async def _handle_files_in_input(
        self,
        files: list[FileWithKeyPath],
        model_data: ModelData,
        provider: AbstractProvider[Any, Any],
        builder: BuilderInterface | None,
        input: dict[str, Any],
        input_copy: dict[str, Any],
    ):
        download_start_time = time.time()
        files = await self._convert_pdf_to_images(files, model_data)
        self._check_support_for_files(model_data, files)

        files_to_download = self._extract_files_to_download(
            files,
            provider.max_number_of_file_urls,
            lambda f: self._should_download_file(provider, f),
        )
        if files_to_download:
            try:
                async with asyncio.TaskGroup() as tg:
                    for file in files_to_download:
                        # We want to update the provided input because file data
                        # should be propagated upstream to avoid having to download files twice
                        tg.create_task(self._download_file_and_update_input(provider, file, input))
            except* InvalidFileError as eg:
                raise eg.exceptions[0]

        # Here we update the input copy instead of the provided input
        # Since the data will just be provided to the provider
        files, has_inlined_files = self._inline_text_files(files, input_copy)

        download_duration = time.time() - download_start_time
        if builder:
            builder.record_file_download_seconds(download_duration)

        return files, has_inlined_files

    async def _build_messages(  # noqa: C901
        self,
        template_name: TemplateName,
        input: AgentInput | Messages,
        provider: AbstractProvider[Any, Any],
        model_data: ModelData,
    ) -> list[MessageDeprecated]:
        """
        Build a message array that will:
        - be passed to the _build_task_output function
        - be used to compute the runner version
        """
        if (builder := self._get_builder_context()) and builder.reply:
            return await self._build_messages_for_reply(builder.reply)

        use_structured_output = (
            model_data.supports_structured_output and self._options.is_structured_generation_enabled is not False
        )

        # If the input is already a Messages object we can just use as is
        if isinstance(input, Messages):
            return await self._inline_messages(
                input.messages,
                provider,
                structured_output=use_structured_output,
                use_tools=self.is_tool_use_enabled,
            )

        # If the input is a raw messages schema we have to extract the messages
        # and use. It would be nice to merge with the above call but it would break
        # the typeguard on the input object
        if raw_messages := await self._extract_raw_messages(input):
            return await self._inline_messages(
                raw_messages,
                provider,
                structured_output=use_structured_output,
                use_tools=self.is_tool_use_enabled,
            )

        start_time = time.time()
        input_copy = deepcopy(input)
        input_schema = deepcopy(self.task.input_schema.json_schema)

        input_schema, input_copy, files = extract_files(input_schema, input_copy)

        if files:
            files, has_inlined_files = await self._handle_files_in_input(
                files,
                model_data,
                provider,
                builder,
                input,
                input_copy,
            )

        else:
            has_inlined_files = False

        # Extracting image options after files. If the user provides a mask, it will be in image options
        # and should be treated like a regular file
        # Also extracting after instruction templating just in case the user has provided a templated
        # instruction that mentions keys used in the image options
        image_options, keys_to_remove1 = await self._extract_image_options(input_copy)

        instructions = self._options.instructions
        if instructions is not None:
            instructions = provider.sanitize_agent_instructions(instructions)

        if self._options.has_templated_instructions:
            instructions, templated_keys = await self._apply_templated_instructions(
                self._options.instructions or "",
                input_copy,
                input_schema,
            )
            keys_to_remove1.update(templated_keys)

        await self._remove_keys_from_input(input_schema=input_schema, input=input_copy, used_input_keys=keys_to_remove1)

        template_config = get_template_content(template_name)

        user_message_content = self._build_user_message_content(
            template_config.user_template,
            input_copy,
            input_schema,
            has_inlined_files,
        )

        system_template = template_config.system_template
        if user_message_content.should_remove_input_schema:
            # when the input schema only contains one file property, we do not need t the input schema in the system template without input schema
            system_template = get_template_without_input_schema(template_name).system_template

        messages = [
            MessageDeprecated(
                content=self._system_message_content(
                    template=system_template,
                    instructions=instructions or "",
                    input_schema=input_schema,
                    output_schema=self._prepared_output_schema.prepared_schema
                    if not self._prepared_output_schema.no_schema
                    else None,
                ),
                role=MessageDeprecated.Role.SYSTEM,
                image_options=image_options,
            ),
        ]
        if user_message_content.content or files:
            messages.append(
                MessageDeprecated(
                    content=user_message_content.content,
                    role=MessageDeprecated.Role.USER,
                    files=files or None,
                ),
            )

        add_background_task(
            send_gauge(
                "run_overhead_messages",
                value=time.time() - start_time,
                timestamp=start_time,
                **self.metric_tags,
            ),
        )
        return messages

    @property
    def _run_id(self):
        if ctx := self._get_builder_context():
            return ctx.id
        return self.run

    @property
    def is_tool_use_enabled(self) -> bool:
        return len(self.properties.enabled_tools or []) > 0

    @classmethod
    def _extract_internal_key(cls, raw: dict[str, Any], key: str, parser: Callable[[Any], T]) -> T | None:
        raw = raw.pop(key, None)
        if not raw:
            return None

        try:
            return parser(raw)
        except Exception:
            logger.exception("Failed to parse internal key", extra={"raw": raw})
            return None

    @classmethod
    def _extract_all_internal_keys(cls, raw: Any, partial: bool = False):
        """Extracts internal keys from a raw dict. The raw dict is updated in place"""
        # There is no point in logging errors when we are in partial mode
        if not isinstance(raw, dict):
            return None, None

        raw = cast(dict[str, Any], raw)

        reasoning_steps = cls._extract_internal_key(
            raw,
            INTERNAL_REASONING_STEPS_SCHEMA_KEY,
            lambda x: reasoning_step_mapper(x, None if partial else logger),
        )

        agent_run_result = cls._extract_internal_key(
            raw,
            INTERNAL_AGENT_RUN_RESULT_SCHEMA_KEY,
            TypeAdapter(AgentRunResult).validate_python,
        )
        return agent_run_result, reasoning_steps

    def output_factory(self, raw: str, partial: bool = False) -> StructuredOutput:
        if self._prepared_output_schema.prepared_schema is None:
            return StructuredOutput(
                raw,
                None,
                None,
                None,
            )

        json_str = raw.replace("\t", "\\t")
        # Acting on the string is probably unefficient, we do multiple decodes and encode
        # On the payload. Instead we should probably retrieve bytes for the output
        # and act on that.
        json_str = clean_json_string(json_str)

        try:
            json_dict = json.loads(json_str)
        except json.JSONDecodeError:
            logger.info(
                "Attempting to build output from invalid json",
                extra={"run_id": self._run_id},
                exc_info=True,
            )
            # When the normal json parsing fails, we try and decode it with a tolerant stream handler
            json_dict = parse_tolerant_json(json_str)
        json_dict = cleanup_provider_json(json_dict)

        return self.build_structured_output(json_dict, partial=partial)

    def build_structured_output(self, output: Any, partial: bool):
        agent_run_result, reasoning_steps = self._extract_all_internal_keys(output)

        if agent_run_result and agent_run_result.status == "failure":
            raise AgentRunFailedError.from_agent_run_result(
                agent_run_result,
                partial_output=self.task.validate_output(output, partial=True),
            )

        if self._stream_deltas and partial:
            final_output = output
        else:
            final_output = self.task.validate_output(output, partial=partial)

        return StructuredOutput(
            final_output,
            None,
            agent_run_result,
            reasoning_steps,
        )

    def _split_tools(
        self,
        tool_calls: list[ToolCallRequestWithID] | None,
    ) -> tuple[list[ToolCallRequestWithID] | None, list[ToolCallRequestWithID] | None]:
        """Split tools into internal and external tools"""
        if not tool_calls:
            return None, None

        # First assigning tool call indices
        for i, tool_call in enumerate(tool_calls):
            tool_call.index = i

        internal_tools: list[ToolCallRequestWithID] = []
        external_tools: list[ToolCallRequestWithID] = []
        for tool_call in tool_calls:
            arr = internal_tools if tool_call.tool_name in self._enabled_internal_tools else external_tools
            arr.append(tool_call)
        return internal_tools or None, external_tools or None

    async def _final_run_output(
        self,
        output: StructuredOutput,
        include_tool_calls: bool = True,
    ) -> RunOutput:
        internal_tools: Sequence[ToolCall] | None = (
            await self._internal_tool_cache.values() if include_tool_calls else None
        )

        external_tools: Sequence[ToolCallRequestWithID] | None = (
            await self._external_tool_cache.values() if include_tool_calls else None
        )

        if output.files:
            output_dict: dict[str, Any] = output.output or {}
            assign_files(self.task.output_schema.json_schema, output.files, output_dict)
            output = output._replace(output=output_dict)

        return RunOutput(
            task_output=output.output,
            tool_calls=internal_tools or None,
            tool_call_requests=external_tools or None,
            reasoning_steps=output.reasoning_steps,
            final=True,
        )

    async def _build_task_output_from_messages(
        self,
        provider: AbstractProvider[Any, Any],
        options: ProviderOptions,
        messages: list[MessageDeprecated],
    ) -> RunOutput:
        iteration_count = 0
        current_messages = messages

        while iteration_count < MAX_TOOL_CALL_ITERATIONS:
            iteration_count += 1

            structured_output = await provider.complete(
                current_messages,
                options,
                self.output_factory,
            )

            internal_tools, external_tools = self._split_tools(structured_output.tool_calls)
            # We add the returned tool calls to the external tool cache
            await self._external_tool_cache.ingest(external_tools)

            if not internal_tools:
                return await self._final_run_output(structured_output)

            try:
                tool_results = await self._run_tool_calls(internal_tools, messages)
                current_messages = self._append_tool_call_requests_to_messages(current_messages, internal_tools)
                current_messages = self.append_tool_result_to_messages(current_messages, tool_results)
            except ToolCallRecursionError:
                # If all tool calls have already been called with the same arguments, we stop the iteration
                # and return the output as is
                return await self._final_run_output(structured_output, include_tool_calls=False)

        raise MaxToolCallIterationError(
            f"Tool calls failed to converge after {MAX_TOOL_CALL_ITERATIONS} iterations",
        )

    # Returns a tuple[result, is_cached]
    async def _safe_execute_tool(
        self,
        tool_call: ToolCallRequestWithID,
        messages: list[MessageDeprecated],
    ) -> tuple[ToolCall, bool]:
        # Detect the tool calls made in the context of the same HTTP request
        if res := (await self._internal_tool_cache.get(tool_call.tool_name, tool_call.tool_input_dict)):
            return res, True

        # TODO: use the tool cache for that
        # That's not good also because it probably breaks the tool call message ordering
        # since most models require the tool call result to be immediately after the tool call request
        # Detect the tools calls made in previous HTTPS requests, but present in the messages
        if any(tool_call.id in message.content for message in messages):
            return ToolCall(
                id=tool_call.id,
                tool_name=tool_call.tool_name,
                tool_input_dict=tool_call.tool_input_dict,
                result="Please refer to the previous messages for the result of this tool call",
            ), True

        try:
            tool = self._enabled_internal_tools[tool_call.tool_name].fn
        except KeyError:
            existing_tools_str = ", ".join(self._enabled_internal_tools.keys())
            logger.exception("Requested internal tool call does not exist", extra={"tool_name": tool_call.tool_name})
            return tool_call.with_error(
                f"Tool '{tool_call.tool_name}' does not exist. Existing tools are: {existing_tools_str}",
            ), False

        try:
            tool_result = await tool(**tool_call.tool_input_dict)
            await self._internal_tool_cache.set(tool_call.tool_name, tool_call.tool_input_dict, tool_result)
            return tool_call.with_result(tool_result), False
        except Exception as e:
            logger.exception(
                "Tool call failed",
                extra={"tool_name": tool_call.tool_name, "tool_input": tool_call.tool_input_dict},
            )
            return tool_call.with_error(f"{e.__class__.__name__}: {str(e)}"), False

    async def _run_tool_calls(
        self,
        tool_calls: list[ToolCallRequestWithID],
        messages: list[MessageDeprecated],
    ) -> list[ToolCall]:
        if not tool_calls:
            return []

        results = await asyncio.gather(*[self._safe_execute_tool(tool_call, messages) for tool_call in tool_calls])
        out: list[ToolCall] = []
        found_not_cached = False
        for result, is_cached in results:
            out.append(result)
            if not is_cached:
                found_not_cached = True

        if not found_not_cached:
            raise ToolCallRecursionError("All tool calls have already been called with the same arguments")

        return out

    # TODO[tools]: build an assistant message that contains the tool call requests
    # def _latest_assistant_message(self):
    #     # TODO: a bit sad to retrieve from the builder_context but it will do for now
    #     context = self._get_builder_context()
    #     if context is None or not context.llm_completions:
    #         return None
    #     last_completion = context.llm_completions[-1]
    #     if not last_completion.response:
    #         return None
    #     return Message(
    #         role=Message.Role.ASSISTANT,
    #         content=last_completion.response or "",
    #     )

    @classmethod
    def _append_tool_call_requests_to_messages(
        cls,
        messages: list[MessageDeprecated],
        tool_calls: list[ToolCallRequestWithID],
    ) -> list[MessageDeprecated]:
        assistant_message = MessageDeprecated(
            role=MessageDeprecated.Role.ASSISTANT,
            tool_call_requests=tool_calls,
            content="",
        )
        return [*messages, assistant_message]

    def append_tool_result_to_messages(
        self,
        messages: list[MessageDeprecated],
        tool_results: list[ToolCall],
    ) -> list[MessageDeprecated]:
        # TODO[tools]: not appending the assistant message for now, since the user
        # message contains the input and ouputs. Ultimately we should support let
        # the provider implementation decide how to handle tool calls:
        # - either the provider handle tool calls and then they can be identified by IDs so we
        # can have "native" tool calls in the messages
        # - either it does not and it's likely than providing the tool output right after the tool
        # input is the best approach
        # In both cases, the implementation SHOULD be to add an assistant with tool requests
        # AND a user message with the tool results, and let the provider code do the merging if needed
        # See https://linear.app/workflowai/issue/WOR-3136/use-native-tools-when-available
        #
        # if message := self._latest_assistant_message():
        #     messages.append(message)

        user_message = MessageDeprecated(role=MessageDeprecated.Role.USER, tool_call_results=tool_results, content="")
        return [*messages, user_message]

    @classmethod
    def _prepare_output_schema(
        cls,
        output_schema: SerializableTaskIO,
        is_chain_of_thought_enabled: bool,
        is_tool_use_enabled: bool,
        typology: TaskTypology,
    ) -> PreparedOutputSchema:
        if output_schema.version == RawStringMessageSchema.version:
            return PreparedOutputSchema(prepared_schema=None)
        if output_schema.version == RawJSONMessageSchema.version:
            return PreparedOutputSchema(prepared_schema={})

        output_json_schema = deepcopy(output_schema.json_schema)
        if is_chain_of_thought_enabled:
            add_reasoning_steps_to_schema(output_json_schema)

        # We only need to add the tool schema in the output if we are not using native tools
        if is_tool_use_enabled:
            add_agent_run_result_to_schema(output_json_schema)  # status must be at the 'top'

        if typology.output.is_text_only:
            return PreparedOutputSchema(prepared_schema=output_json_schema)

        min_file_count, max_file_count = remove_files_from_schema(output_json_schema)
        return PreparedOutputSchema(
            prepared_schema=output_json_schema,
            min_file_count=min_file_count,
            max_file_count=max_file_count,
        )

    def _check_tool_calling_support(self, model_data: FinalModelData):
        if self.is_tool_use_enabled is False:
            return

        if not model_data.supports_tool_calling:
            raise ModelDoesNotSupportMode(
                model=model_data.model,
                msg=f"{model_data.model.value} does not support tool calling",
            )

    def _build_provider_data(
        self,
        provider: AbstractProvider[Any, Any],
        model_data: FinalModelData,
        is_structured_generation_enabled: bool,
    ) -> tuple[AbstractProvider[Any, Any], TemplateName, ProviderOptions, FinalModelData]:
        provider_options = ProviderOptions(
            model=model_data.model,
            temperature=self._options.temperature,
            max_tokens=self._options.max_tokens,
            output_schema=self._prepared_output_schema.prepared_schema,
            task_name=self.task.name,
            structured_generation=is_structured_generation_enabled,
            tenant=self.task.tenant,
            stream_deltas=self._stream_deltas,
            top_p=self._options.top_p,
            presence_penalty=self._options.presence_penalty,
            frequency_penalty=self._options.frequency_penalty,
            parallel_tool_calls=self._options.parallel_tool_calls,
            enabled_tools=list(self._all_tools()),
            tool_choice=self._options.tool_choice,
            timeout=self._timeout,
            reasoning_effort=self._options.reasoning_effort,
            reasoning_budget=self._options.reasoning_budget,
        )

        model_data_copy = model_data.model_copy()
        provider.sanitize_model_data(model_data_copy)
        self._check_tool_calling_support(model_data)

        # Overriding the structured generation flag if the model does not support it
        # Post provider override
        if not model_data_copy.supports_structured_output:
            is_structured_generation_enabled = False

        template_name = self._pick_template(provider, model_data_copy, is_structured_generation_enabled)
        return provider, template_name, provider_options, model_data_copy

    async def _stream_task_output_from_messages(  # noqa: C901
        self,
        provider: AbstractProvider[Any, Any],
        options: ProviderOptions,
        messages: list[MessageDeprecated],
    ):
        # For now we don't stream images
        streamable = not self._typology.output.is_text_only and provider.is_streamable(
            options.model,
            options.enabled_tools,
        )
        if streamable:
            yield (await self._build_task_output_from_messages(provider, options, messages))
            return

        if not provider.is_streamable(options.model, options.enabled_tools):
            yield (await self._build_task_output_from_messages(provider, options, messages))
            return

        iteration_count = 0

        # TODO[tools]: fix the streaming
        while iteration_count < MAX_TOOL_CALL_ITERATIONS:
            iteration_count += 1

            completion_has_tool_calls = False

            output: StructuredOutput | None = None
            async for output in provider.stream(
                messages,
                options,
                output_factory=self.output_factory,
                partial_output_factory=lambda p: self.build_structured_output(p, True),
            ):
                if completion_has_tool_calls or output.tool_calls:
                    completion_has_tool_calls = True
                    # This logic is to avoid streaming intermediary task outputs while we still have tool calls to run
                    # This will be corrected by structured generation with anyOf [TaskOutput, list[ToolCall]], but all models will not support struct gen
                    continue

                if output.final and not output.tool_calls:
                    # We will stream the final output after the end of the stream.
                    # This way the provider has time to perform any operation on the context if needed
                    continue
                yield RunOutput(task_output=output.output, reasoning_steps=output.reasoning_steps, delta=output.delta)

            if not output:
                # We never had any output, we can stop the stream
                return

            if not output.tool_calls:
                yield await self._final_run_output(output)
                return

            # Stream empty output to indicate that we are still running tool calls
            # TODO[tools]: remove
            yield RunOutput({}, [d.with_result(None) for d in output.tool_calls])

            internal_tools, external_tools = self._split_tools(output.tool_calls)
            # We add the returned tool calls to the external tool cache
            await self._external_tool_cache.ingest(external_tools)

            if not internal_tools:
                yield await self._final_run_output(output)
                return
            try:
                tool_results = await self._run_tool_calls(output.tool_calls, messages)
            except ToolCallRecursionError:
                # If all tool calls have already been called with the same arguments, we stop the iteration
                # and return the output as is
                if output.output:
                    yield await self._final_run_output(output, include_tool_calls=False)
                    return
                raise MaxToolCallIterationError(
                    f"Tool calls failed to converge after {iteration_count} iterations",
                    capture=True,
                )
            messages = self._append_tool_call_requests_to_messages(messages, output.tool_calls)
            messages = self.append_tool_result_to_messages(messages, tool_results)

        raise MaxToolCallIterationError(
            f"Tool calls failed to converge after {MAX_TOOL_CALL_ITERATIONS} iterations",
        )

    @classmethod
    def supports(cls, task: SerializableTaskVariant) -> bool:
        return True

    @classmethod
    def options_class(cls) -> type[WorkflowAIRunnerOptions]:
        return WorkflowAIRunnerOptions

    def example_str(self, example: FewShotExample) -> str:
        return (
            f"Input:\n```json\n{json.dumps(example.task_input, indent=2)}\n```\n"
            f"Output:\n```json\n{json.dumps(example.task_output, indent=2)}\n```"
        )

    @classmethod
    @override
    def _build_options(
        cls,
        task: SerializableTaskVariant,
        properties: TaskGroupProperties,
    ) -> WorkflowAIRunnerOptions:
        model, provider, reasoning_effort = sanitize_model_and_provider(properties.model, properties.provider)

        is_structured_generation_enabled = (
            False if task.output_schema.is_structured_output_disabled else properties.is_structured_generation_enabled
        )

        instructions = properties.instructions
        if properties.template_name:
            template_name = sanitize_template_name(
                template_name=properties.template_name,
                is_tool_use_enabled=len(properties.enabled_tools or []) > 0,
                is_structured_generation_enabled=is_structured_generation_enabled or False,
                supports_input_schema=get_model_data(model).supports_input_schema,
            )
        else:
            template_name = None

        raw = properties.model_dump(
            exclude_none=True,
            exclude={"instructions", "name", "provider", "few_shot", "is_structured_generation_enabled"},
        )
        raw["instructions"] = instructions
        raw["provider"] = provider
        raw["model"] = model
        raw["template_name"] = template_name
        raw["is_structured_generation_enabled"] = is_structured_generation_enabled
        if reasoning_effort is not None:
            raw["reasoning_effort"] = reasoning_effort

        if properties.few_shot:
            if properties.few_shot.examples:
                raw["examples"] = properties.few_shot.examples
            else:
                logger.warning(
                    "Few shot examples are not set in the properties",
                    extra={
                        "task_id": task.task_id,
                        "properties": properties.model_dump(exclude_none=True),
                    },
                )

        return WorkflowAIRunnerOptions.model_validate(raw)

    @override
    def _build_properties(self, options: WorkflowAIRunnerOptions, original: TaskGroupProperties | None):
        """
        Builds the task run group properties from the selected options
        """
        # Adding some info to the group so it can be re-used later
        base = super()._build_properties(options, original)
        # We store the task variant id in the properties so that
        # the group can be re-used for the same task variant
        base.task_variant_id = self.task.id

        if not base.instructions:
            # Making sure we don't have to deal with empty (instead of None) instructions
            base.instructions = None

        validated = TaskGroupProperties.model_validate(base)

        if options.examples:
            validated.few_shot = FewShotConfiguration(
                examples=options.examples,
                count=len(options.examples),
                selection=original.few_shot.selection if (original and original.few_shot) else None,
            )

        return validated

    @override
    async def validate_run_options(self):
        if self._options.has_templated_instructions:
            # We don't check whether some keys are missing in the task schema
            # That's ok since it will not throw an error at run time
            try:
                # We add it to the cache, if it's here it will be used soon anyway
                await self.template_manager.add_template(self._options.instructions or "")
            except InvalidTemplateError as e:
                # Setting as capture=True for a bit
                raise InvalidRunOptionsError(f"Instruction template is invalid: {str(e)}", capture=True)

    @classmethod
    def _exclude_in_build_run_tags(cls) -> set[str]:
        return {
            "instructions",
            "runner_name",
            "runner_version",
            "instructions",
            "task_schema_id",
            "task_variant_id",
            "template_name",
            "is_structured_generation_enabled",
            "has_templated_instructions",
        }

    def _build_pipeline(self):
        pipeline = ProviderPipeline(
            options=self._options,
            custom_configs=self._custom_configs,
            factory=self.provider_factory,
            builder=self._build_provider_data,
            typology=self._typology,
            use_fallback=self._use_fallback,
        )

        if pipeline.model_data.model != self._options.model:
            self._set_metadata(METADATA_KEY_USED_MODEL, pipeline.model_data.model)

        return pipeline

    @override
    async def _build_task_output(self, input: AgentInput | Messages) -> RunOutput:
        """
        Calls _build_task_output_from_messages with the messages generated _build_messages
        """
        pipeline = self._build_pipeline()

        for provider, template_name, options, model_data in pipeline.provider_iterator():
            self._append_metadata(METADATA_KEY_USED_PROVIDERS, provider.name())
            self._set_metadata(METADATA_KEY_PROVIDER_NAME, provider.name())
            with pipeline.wrap_provider_call(provider):
                messages = await self._build_messages(template_name, input, provider, model_data)
                return await self._build_task_output_from_messages(provider, options, messages)

        return pipeline.raise_on_end(self.task.task_id)

    @override
    async def _stream_task_output(self, input: AgentInput | Messages):
        """
        Calls _stream_task_output_from_messages with the messages generated _build_messages
        """
        pipeline = self._build_pipeline()
        for provider, template_name, options, model_data in pipeline.provider_iterator():
            self._append_metadata(METADATA_KEY_USED_PROVIDERS, provider.name())
            self._set_metadata(METADATA_KEY_PROVIDER_NAME, provider.name())

            with pipeline.wrap_provider_call(provider):
                messages = await self._build_messages(template_name, input, provider, model_data)
                async for o in self._stream_task_output_from_messages(
                    provider,
                    options,
                    messages,
                ):
                    yield o
                return

        pipeline.raise_on_end(self.task.task_id)
