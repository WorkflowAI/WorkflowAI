import asyncio
import base64
import copy
import logging
from io import BytesIO
from typing import Any, cast

import httpx
from pydantic import ValidationError

from core.domain.consts import AUDIO_REF_NAME, FILE_DEFS, FILE_REF_NAME, IMAGE_REF_NAME, PDF_REF_NAME
from core.domain.errors import (
    BadRequestError,
    InvalidFileError,
    InvalidRunOptionsError,
    message_from_validation_error,
)
from core.domain.fields.file import File, FileWithKeyPath
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.models import Model, Provider
from core.domain.models.model_data import DeprecatedModel
from core.domain.models.model_data_mapping import MODEL_DATAS
from core.domain.task_group_properties import ReasoningEffort
from core.domain.tool import Tool
from core.domain.types import AgentInput, AgentOutput
from core.runners.workflowai.internal_tool import InternalTool
from core.tools import ToolKind
from core.utils.dicts import set_at_keypath
from core.utils.file_utils.file_utils import guess_content_type
from core.utils.iter_utils import safe_map_optional
from core.utils.schema_sanitation import get_file_format
from core.utils.schemas import JsonSchema
from core.utils.strings import clean_unicode_chars

_logger = logging.getLogger(__file__)


def _replace_file_in_payload(
    payload: dict[str, Any],
    key_path: list[str | int],
    format: str | None,
    append_to: list[FileWithKeyPath],
):
    try:
        valid = FileWithKeyPath.model_validate({**payload, "key_path": key_path, "format": format})
    except ValidationError as e:
        raise InvalidFileError(
            message_from_validation_error(e),
            file_url=payload.get("url"),
            details={"file": payload},
        ) from e
    payload.clear()
    payload["number"] = len(append_to)
    append_to.append(valid)


_ANNOYING_KEYS = ["allOf", "anyOf", "oneOf"]


def _handle_annoying_keys(
    schema: dict[str, Any],
    payload: Any,
    append_to: list[FileWithKeyPath],
    key_path: list[str | int],
    root_defs: dict[str, Any] | None,
) -> None:
    # Check for allOf, anyOf, oneOf and dives in as needed
    for key in _ANNOYING_KEYS:
        if key in schema:
            for sub_schema in schema[key]:
                _recursive_find_files(sub_schema, payload, append_to, key_path, root_defs)


def _process_list_payload(
    schema: dict[str, Any],
    payload: list[Any],
    append_to: list[FileWithKeyPath],
    key_path: list[str | int],
    root_defs: dict[str, Any] | None,
) -> None:
    # Process list payloads, handling 'items' and composite keys (anyOf, allOf, oneOf) to detect file references in arrays.
    if "items" in schema:
        for idx, item in enumerate(payload):
            _recursive_find_files(schema["items"], item, append_to, key_path + [idx], root_defs)
    for composite_key in _ANNOYING_KEYS:
        if composite_key in schema:
            for sub_schema in schema[composite_key]:
                _recursive_find_files(sub_schema, payload, append_to, key_path, root_defs)


def _process_ref(
    schema: dict[str, Any],
    payload: dict[str, Any],
    append_to: list[FileWithKeyPath],
    key_path: list[str | int],
    root_defs: dict[str, Any] | None,
) -> bool:
    ref_val: str = schema["$ref"]
    # Process '$ref' branches: If the ref is for File or Image, extract the file; otherwise, resolve the reference using root_defs.
    if ref_val.removeprefix("#/$defs/") in FILE_DEFS:
        _replace_file_in_payload(payload, key_path, get_file_format(ref_val, schema), append_to)
        return True

    if root_defs is not None and ref_val.startswith("#/$defs/"):
        def_name = ref_val.split("/")[-1]
        if def_name in root_defs:
            _recursive_find_files(root_defs[def_name], payload, append_to, key_path, root_defs)
            return True
    return False


# TODO: We should be using JsonSchema file_iterator here
def _recursive_find_files(
    schema: dict[str, Any],
    payload: Any,
    append_to: list[FileWithKeyPath],
    key_path: list[str | int],
    root_defs: dict[str, Any] | None,
) -> None:  # noqa: C901
    # Main recursive function to traverse the schema and payload and extract file references.
    # It delegates list payloads to _process_list_payload and '$ref' handling to _process_ref.
    if isinstance(payload, list):
        _process_list_payload(schema, cast(list[Any], payload), append_to, key_path, root_defs)
        return

    if not isinstance(payload, dict):
        return

    _handle_annoying_keys(schema, payload, append_to, key_path, root_defs)

    if "$ref" in schema:
        if _process_ref(schema, cast(dict[str, Any], payload), append_to, key_path, root_defs):
            return

    if "properties" in schema:
        for key, value in payload.items():  # type: ignore
            if key in schema["properties"]:
                _recursive_find_files(schema["properties"][key], value, append_to, key_path + [key], root_defs)


def is_schema_containing_file(schema: dict[str, Any]) -> bool:
    file_refs = {IMAGE_REF_NAME, FILE_REF_NAME, AUDIO_REF_NAME, PDF_REF_NAME}
    return "$defs" in schema and any(ref in schema["$defs"] for ref in file_refs)


def is_schema_containing_legacy_file(schema: dict[str, Any]) -> bool:
    return (
        "$defs" in schema
        and IMAGE_REF_NAME in schema["$defs"]
        and "url" not in schema["$defs"][IMAGE_REF_NAME].get("properties", {})
    )


def extract_files(schema: dict[str, Any], payload: Any) -> tuple[dict[str, Any], Any, list[FileWithKeyPath]]:
    """Navigate a payload and extracts images/files from it. Images are identified by the File/Image schema ref"""

    if not is_schema_containing_file(schema):
        return schema, payload, []

    out: list[FileWithKeyPath] = []
    payload = copy.deepcopy(payload)
    schema = copy.deepcopy(schema)
    root_defs: dict[str, Any] = schema.get("$defs", {})
    _recursive_find_files(schema, payload, out, [], root_defs)
    schema["$defs"]["File"] = {
        "type": "object",
        "properties": {
            "number": {"type": "integer", "description": "The index of the file message"},
        },
    }
    return schema, payload, out


def remove_files_from_schema(schema: dict[str, Any]) -> tuple[int, int | None]:
    """Recursively navigate the schema and return a max file count or None if any number of files is allowed.
    Schema is modified in place"""
    raw = JsonSchema(schema)
    min_file_count = 0
    max_file_count: int | None = 0

    for keys, _, child in raw.fields_iterator(prefix=[], dive=lambda s: s.followed_ref_name not in FILE_DEFS):
        if child.followed_ref_name in FILE_DEFS:
            min_file_count += 1
            if "[]" in keys:
                max_file_count = None
            elif max_file_count is not None:
                max_file_count += 1
            child.remove_from_parent(recursive=True)

    return min_file_count, max_file_count


def _replace_keypath_arr_idx(keypath: list[str], idx: int):
    # We replace the last [] in the array
    out: list[str | int] = []
    found = False
    for k in reversed(keypath):
        if k == "[]":
            out.insert(0, idx if not found else 0)
            found = True
            continue
        out.insert(0, k)
    return out


def assign_files(schema: dict[str, Any], files: list[File], output: AgentOutput):
    if not isinstance(output, dict):
        _logger.warning("Cannot assign files to non-dict output", extra={"output": output})
        return files
    for key, _, child in JsonSchema(schema).fields_iterator(
        prefix=[],
        dive=lambda s: s.followed_ref_name not in FILE_DEFS,
    ):
        if child.followed_ref_name not in FILE_DEFS:
            continue

        if "[]" in key:
            # We are in a list, so we append to the last item of the list
            # We finish all the available files, we could try and be smarter here but not for now
            for i, f in enumerate(files):
                set_at_keypath(
                    output,
                    _replace_keypath_arr_idx(key, i),
                    f.model_dump(mode="json", exclude_none=True),
                )
            return None

        # Otherwise it's a single file
        set_at_keypath(output, cast(list[str | int], key), files[0].model_dump(mode="json", exclude_none=True))
        files = files[1:]
        if not files:
            return None
    return files


_download_client = httpx.AsyncClient()


async def _fetch_file_with_retries(url: str, retries: int = 2) -> httpx.Response:
    try:
        return await _download_client.get(url)
    except (
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.ReadError,
        httpx.ConnectError,
        httpx.RemoteProtocolError,
    ) as e:
        if retries <= 0:
            raise InvalidFileError(
                f"Failed to download file: {e}",
                capture=False,
            )
        return await _fetch_file_with_retries(url, retries - 1)


async def download_file(file: File):
    if not file.url:
        raise InvalidFileError("File url is required when data is not provided")

    response = await _fetch_file_with_retries(file.url)

    if response.status_code != 200:
        raise InvalidFileError(
            f"Failed to file image: {response.status_code}",
            file_url=file.url,
            details={"response_status_code": response.status_code, "response_body": response.text},
        )

    file.data = base64.b64encode(response.content).decode("utf-8")

    if file.content_type is None:
        file.content_type = guess_content_type(response.content)
        if file.content_type is None:
            _logger.warning("Could not guess content type of url", extra={"url": file.url})

    return response.content


def sanitize_model_and_provider(
    model_str: str | None,
    provider_str: str | None,
) -> tuple[Model, Provider | None, ReasoningEffort | None]:
    if not model_str:
        # We should never be here so we capture
        raise InvalidRunOptionsError("Model is required", capture=True)

    try:
        model = Model(model_str)
    except ValueError:
        raise InvalidRunOptionsError(f"Model {model_str} is not valid")

    data = MODEL_DATAS[model]  # noqa: F821
    reasoning_effort: ReasoningEffort | None = None
    if isinstance(data, DeprecatedModel):
        model = data.replacement_model
        reasoning_effort = data.reasoning_effort

    try:
        provider = Provider(provider_str) if provider_str else None
    except ValueError:
        raise InvalidRunOptionsError(f"Provider {provider_str} is not valid")

    return model, provider, reasoning_effort


class ToolCallRecursionError(Exception):
    # Raised when all tool calls have already been called with the same arguments
    pass


def split_tools(
    available_tools: dict[ToolKind, InternalTool],
    tools: list[ToolKind | Tool] | None,
) -> tuple[dict[str, InternalTool], dict[str, Tool]]:
    internal_tools: dict[str, InternalTool] = {}
    external_tools: dict[str, Tool] = {}
    if not tools:
        return internal_tools, external_tools

    for tool in tools:
        if isinstance(tool, Tool):
            if tool.name.startswith("@"):
                raise BadRequestError(f"External tool name {tool.name} cannot start with @")
            external_tools[tool.name] = tool
            continue

        try:
            internal_tools[tool] = available_tools[tool]
        except (KeyError, ValueError):
            _logger.exception("Tool kind in enabled_tools is not available", extra={"tool": tool})
    return internal_tools, external_tools


async def convert_pdf_to_images(pdf_file: FileWithKeyPath) -> list[FileWithKeyPath]:
    # No need to wrap in a try-except block
    # The error will be caught upstream
    from pdf2image import convert_from_bytes  # pyright: ignore[reportUnknownVariableType]
    from PIL import Image

    if not pdf_file.data:
        pdf_data = await download_file(pdf_file)
    else:
        pdf_data = base64.b64decode(pdf_file.data)

    images = await asyncio.to_thread(convert_from_bytes, pdf_file=pdf_data, fmt="jpg", dpi=150)  # pyright: ignore[reportUnknownArgumentType]

    def _map(image: Image.Image, idx: int):
        # Convert PIL Image to bytes and encode as base64
        buffer = BytesIO()
        image.save(
            buffer,
            format="JPEG",
            quality=60,
            optimize=True,
            progressive=True,
        )
        image_bytes = buffer.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        return FileWithKeyPath(data=image_base64, content_type="image/jpeg", key_path=pdf_file.key_path + [idx])

    return [_map(image, i) for i, image in enumerate(images)]


def cleanup_provider_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: cleanup_provider_json(v) for k, v in obj.items()}  # pyright: ignore[reportUnknownVariableType]
    if isinstance(obj, list):
        return [cleanup_provider_json(v) for v in obj]  # pyright: ignore[reportUnknownVariableType]
    if isinstance(obj, str):
        return clean_unicode_chars(obj)
    return obj


def reasoning_step_mapper(x: Any, logger: logging.Logger | None = None) -> list[InternalReasoningStep] | None:
    if not isinstance(x, list):
        if logger:
            logger.warning("Expected a list of reasoning steps", extra={"x": x})
        return None
    return safe_map_optional(
        (i for i in cast(list[Any], x) if i),
        InternalReasoningStep.model_validate,
        logger=logger,
    )


def remove_keys_from_input(
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
