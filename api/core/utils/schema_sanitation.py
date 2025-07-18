import logging
from collections.abc import Callable
from typing import Any, TypeAlias, cast, override

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema
from typing_extensions import deprecated

from core.domain.agent_run_result import INTERNAL_AGENT_RUN_RESULT_SCHEMA_KEY
from core.domain.consts import FILE_DEFS, FILE_REF_NAME
from core.domain.errors import UnfixableSchemaError
from core.domain.fields.chat_message import ChatMessage
from core.domain.fields.file import File, FileKind
from core.domain.fields.local_date_time import DatetimeLocal
from core.domain.message import Messages
from core.domain.reasoning_step import INTERNAL_REASONING_STEPS_SCHEMA_KEY
from core.utils.schema_validation_utils import fix_non_object_root
from core.utils.schemas import InvalidSchemaError, JsonSchema, strip_json_schema_metadata_keys

logger = logging.getLogger(__name__)


PROTECTED_SCHEMA_KEYS = [
    INTERNAL_REASONING_STEPS_SCHEMA_KEY,
    INTERNAL_AGENT_RUN_RESULT_SCHEMA_KEY,
]


def _log_and_raise_unfixable_schema_error(message: str) -> None:
    error_message = f"Can not fix schema: {message}"
    e = UnfixableSchemaError(error_message)
    logger.exception(
        error_message,
        exc_info=e,
    )
    raise e


# TODO: add unit tests, for now this function is tested as part of "sanitize_schema" only


def _remove_examples(schema: dict[str, Any]) -> dict[str, Any]:
    return strip_json_schema_metadata_keys(schema, {"examples"})


def _remove_examples_non_string_and_enum(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Keep `examples` only for `string` fields.
    """
    return strip_json_schema_metadata_keys(
        schema,
        {"examples"},
        filter=lambda d: d.get("type") != "string" or "enum" in d,
    )


def _remove_empty_defs(schema: dict[str, Any]) -> dict[str, Any]:
    if "$defs" in schema and schema["$defs"] == {}:
        del schema["$defs"]
    return schema


def _sanitize_file_schema(schema: dict[str, Any]) -> None:
    if "format" not in schema:
        schema["format"] = FileKind.DOCUMENT.value
    if schema["format"] not in FileKind:
        _log_and_raise_unfixable_schema_error(
            f'File schema must have a "format" field among {", ".join([kind.value for kind in FileKind])}, got "{schema["format"]}"',
        )


def _extract_refs(schema: dict[str, Any], into: set[str]):
    # Exract defs from a schema
    if "$ref" in schema:
        name = schema["$ref"].removeprefix("#/$defs/")

        if name == File.__name__:
            _sanitize_file_schema(schema)

        into.add(name)
        return

    if "properties" in schema:
        for prop in schema["properties"].values():
            _extract_refs(prop, into)

    if "items" in schema:
        if isinstance(schema["items"], list):
            for item in cast(list[dict[str, Any]], schema["items"]):
                _extract_refs(item, into)
        else:
            _extract_refs(schema["items"], into)


class _NoTitleJsonSchemaGenerator(GenerateJsonSchema):
    """A schema generator that simplifies the schemas generated by pydantic."""

    @override
    def generate(self, *args: Any, **kwargs: Any):
        generated = super().generate(*args, **kwargs)
        # Remove the title from the schema
        generated.pop("title", None)
        return generated

    @override
    def field_title_should_be_set(self, *args: Any, **kwargs: Any) -> bool:
        return False

    @override
    def model_schema(self, *args: Any, **kwargs: Any):
        generated = super().model_schema(*args, **kwargs)
        # Remove the title from the schema
        generated.pop("title", None)
        return generated


@deprecated("Use streamline_schema instead")
def _add_missing_defs(schema: dict[str, Any]) -> dict[str, Any]:
    schema_defs = _build_internal_defs(streamline=False)

    refs: set[str] = set()
    _extract_refs(schema, refs)

    if refs:
        defs = schema.setdefault("$defs", {})
        for name in refs:
            if name not in defs:
                defs[name] = schema_defs[name]

    return schema


def _check_for_protected_keys(schema: dict[str, Any], protected_keys: list[str] = PROTECTED_SCHEMA_KEYS) -> None:
    for key in protected_keys:
        try:
            JsonSchema(schema).child_schema(key)
            _log_and_raise_unfixable_schema_error(f"Key {key} is protected and can not be included in the schema")
        except InvalidSchemaError:
            continue


def _enforce_no_file_in_output_schema(schema: dict[str, Any]) -> None:
    # Forbides file in the output schema
    if "$defs" in schema and ("File" in schema["$defs"] or "Image" in schema["$defs"]):
        _log_and_raise_unfixable_schema_error("File(s) can not be included in the output schema")


def _normalize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    # Normalize a json schema before storing it
    # This adds refs if needed and removes empty defs
    # The cleanup is lighter than sanitation to avoid overriding user preferences
    _check_for_protected_keys(schema)

    schema = _add_missing_defs(schema)  # pyright: ignore[reportDeprecated]
    schema = _remove_empty_defs(schema)
    schema, _ = fix_non_object_root(schema)

    return schema  # noqa: RET504


# TODO: we should not do any schema modifications in the normalize functions
# We should deprecate these methods and only use sanititation in the internal service
@deprecated("Use streamline_schema instead")
def normalize_input_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = _remove_examples(schema)
    return _normalize_json_schema(schema)


@deprecated("Use streamline_schema instead")
def normalize_output_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = _remove_examples_non_string_and_enum(schema)
    schema = _normalize_json_schema(schema)
    _enforce_no_file_in_output_schema(schema)
    return schema


def _get_or_set_type(schema: dict[str, Any] | list[Any]):
    if not isinstance(schema, dict):
        return None
    obj_type = schema.get("type")
    if not obj_type:
        if obj_type := JsonSchema._guess_type(schema):  # pyright: ignore [reportPrivateUsage]
            schema["type"] = obj_type
    return obj_type


_RefHandler: TypeAlias = Callable[[str, dict[str, Any]], dict[str, Any] | None]


def _streamline_array(schema: dict[str, Any], handle_ref: _RefHandler, defs: dict[str, Any], processing_refs: set[str]):
    items = schema.get("items")
    if not items:
        # not sure what to do here, just skipping for now
        return schema
    if isinstance(items, dict):
        return {
            **schema,
            "items": _inner_streamline_schema(cast(dict[str, Any], items), handle_ref, defs, True, processing_refs),
        }
    if isinstance(items, list):
        items = cast(list[dict[str, Any]], items)
        # Avoiding lists of a single item
        if len(items) == 1:
            return {
                **schema,
                "items": _inner_streamline_schema(items[0], handle_ref, defs, True, processing_refs),
            }
        return {
            **schema,
            "items": [_inner_streamline_schema(item, handle_ref, defs, True, processing_refs) for item in items],
        }
    raise InvalidSchemaError(f"Unexpected items type: {type(items)}")


def _streamline_object(
    schema: dict[str, Any],
    handle_ref: _RefHandler,
    defs: dict[str, Any],
    processing_refs: set[str],
):
    required = set(schema.get("required", []))
    properties = schema.get("properties")
    if not properties:
        return schema

    base = {
        **schema,
        "properties": {
            k: _inner_streamline_schema(v, handle_ref, defs, k in required, processing_refs)
            for k, v in properties.items()
        },
    }
    if required:
        base["required"] = sorted(list(required))
    return base


def _handle_one_any_all_ofs(
    schema: dict[str, Any],
    handle_ref: _RefHandler,
    defs: dict[str, Any],
    is_required: bool,
    processing_refs: set[str],
):
    of_keys = {"oneOf", "anyOf", "allOf"}
    used_keys = [key for key in of_keys if key in schema]
    if not used_keys:
        return schema
    if len(used_keys) != 1:
        raise InvalidSchemaError("Expected a single of key in schema")

    key = used_keys[0]
    sub = schema[key]
    if not isinstance(sub, list):
        logger.warning("Expected a list for an of key", extra={"schema": schema})
        return schema

    remaining = {k: v for k, v in schema.items() if k != key}
    sub = cast(list[dict[str, Any]], sub)

    # If the field is not required, we remove the potential null type
    not_null = [item for item in sub if item.get("type") != "null"]
    if not is_required:
        if "default" in remaining and remaining["default"] is None:
            del remaining["default"]

    if len(not_null) != 1:
        # If there is a not a single non null item then we return as is
        # It's not clear what to do in this case
        # TODO: we should attempt a sort here to make the output deterministic
        # Any of, etc. are a pretty niche case so ok for now
        return {
            **remaining,
            key: [_inner_streamline_schema(item, handle_ref, defs, is_required, processing_refs) for item in sub],
        }

    streamlined_not_null = _inner_streamline_schema(
        {**remaining, **not_null[0]},
        handle_ref,
        defs,
        is_required,
        processing_refs,
    )

    if len(sub) > 1 and is_required and "type" in streamlined_not_null:
        # We removed a null type but the field is required. So we add it back as
        # a type array
        streamlined_not_null["type"] = [streamlined_not_null["type"], "null"]
        # We also need to add it to the enum if it exists
        if "enum" in streamlined_not_null:
            streamlined_not_null["enum"].append(None)

    return streamlined_not_null


def _remove_falsy_keys(schema: dict[str, Any], keys: set[str]):
    return {k: v for k, v in schema.items() if k not in keys or v}


_FALSY_KEYS_TO_REMOVE = {"examples", "description", "items", "properties"}


class _CircularReferenceError(Exception):
    pass


def _inner_streamline_schema(
    schema: dict[str, Any],
    handle_ref: _RefHandler,
    defs: dict[str, Any],
    is_required: bool,
    processing_refs: set[str],
) -> dict[str, Any]:
    obj_type = _get_or_set_type(schema)
    schema = _remove_falsy_keys(schema, _FALSY_KEYS_TO_REMOVE)

    if obj_type == "array":
        return _streamline_array(schema, handle_ref, defs, processing_refs)

    if obj_type == "object":
        return _streamline_object(schema, handle_ref, defs, processing_refs)

    if ref := schema.get("$ref"):
        if not isinstance(ref, str):
            raise InvalidSchemaError(f"Unexpected ref type: {type(ref)}")

        ref_name = ref.removeprefix("#/$defs/")

        # Check for circular reference to prevent infinite recursion
        if ref_name in processing_refs:
            # Return the ref as-is to avoid infinite recursion
            raise _CircularReferenceError(f"Circular reference detected: {ref_name}")

        if replacement := handle_ref(ref_name, schema):
            return replacement

        del schema["$ref"]
        try:
            definition = defs[ref_name]
        except KeyError:
            raise InvalidSchemaError(f"Can't find the definition of the ref: {ref}")

        processing_refs.add(ref_name)
        result = _inner_streamline_schema(
            {**definition, **schema},
            handle_ref,
            defs,
            is_required,
            processing_refs,
        )
        processing_refs.discard(ref_name)
        return result

    return _handle_one_any_all_ofs(schema, handle_ref, defs, is_required, processing_refs)


def _handle_internal_ref(ref_name: str, ref: dict[str, Any], used_refs: set[str], internal_defs: dict[str, Any]):
    """
    We replace old versions of internal refs with new ones. For example, we used to
    have {"$ref": "#/defs/File", "format":"image"}, which makes a valid json schema
    but that is more complicated to handle than just {"$ref": "#/defs/Image"}.
    """
    if ref_name not in internal_defs:
        # Not an internal ref so we return None so that the reference is inlined
        return None

    format = ref.get("format")
    if not format:
        # No format, nothing we can do so we just mark the ref as used and return as is
        used_refs.add(ref_name)
        return ref

    if ref_name != "File":
        # We got a format but it's not a file which is pretty weird.
        # We log a warning and return as is
        logger.warning("Unexpected format for a non File ref", extra={"schema": ref, "ref_name": ref_name})
        used_refs.add(ref_name)
        return ref

    del ref["format"]

    new_ref: str | None = None
    match format:
        case "image":
            new_ref = "Image"
        case "audio":
            new_ref = "Audio"
        case "pdf":
            new_ref = "PDF"
        case _:
            # Unexpected format. Same thing we log a warning and return as is
            logger.warning("Unexpected format for internal ref", extra={"schema": ref, "ref_name": ref_name})
            used_refs.add(ref_name)
            return ref

    used_refs.add(new_ref)
    return {**ref, "$ref": "#/$defs/" + new_ref}


# Inner version of the cal so we can use it to build internal defs
def _streamline_schema(schema: dict[str, Any], internal_defs: dict[str, Any]):
    refererenced_internal_refs = set[str]()

    def _handle_ref(ref_name: str, ref: dict[str, Any]) -> dict[str, Any] | None:
        return _handle_internal_ref(ref_name, ref, refererenced_internal_refs, internal_defs)

    streamlined = _inner_streamline_schema(
        schema,
        _handle_ref,
        schema.get("$defs", {}),
        is_required=True,
        processing_refs=set(),
    )
    # Sanitize the definitions
    defs = streamlined.setdefault("$defs", {})
    # Remove definitions that were inlined
    for key in list(defs.keys()):
        if (key not in internal_defs) or (key not in refererenced_internal_refs):
            del defs[key]

    # Add missing definitions
    for key in refererenced_internal_refs:
        defs[key] = internal_defs[key]
    if not defs:
        del streamlined["$defs"]

    return streamlined


def clean_pydantic_schema(model: type[BaseModel]):
    return _streamline_schema(model.model_json_schema(schema_generator=_NoTitleJsonSchemaGenerator), {})


def _build_internal_defs(streamline: bool = True) -> dict[str, Any]:
    model_defs: list[type[BaseModel]] = [
        DatetimeLocal,
        File,
        ChatMessage,
        Messages,
    ]

    schema_defs = {m.__name__: clean_pydantic_schema(m) if streamline else m.model_json_schema() for m in model_defs}
    for file_ref in FILE_DEFS:
        # Skipping since it is already defined above
        if file_ref == FILE_REF_NAME:
            continue

        schema_defs[file_ref] = schema_defs[File.__name__]

    return schema_defs


_INTERNAL_DEFS = _build_internal_defs()


def streamline_schema(schema: dict[str, Any], internal_defs: dict[str, Any] | None = None):
    """Returns a streamlined version of the schema:
    - refs that are not ignored are replaced by their content
    - optional nullable fields are just made optional
    The base idea is to have a unique representation of the schema so that we can properly match
    schemas regardless of their implementation details.
    """
    try:
        return _streamline_schema(schema, _INTERNAL_DEFS if internal_defs is None else internal_defs)
    except _CircularReferenceError:
        return schema
    except Exception:
        logger.exception("Error while streamlining schema", extra={"schema": schema})
        return schema


def get_file_format(ref_name: str, schema: dict[str, Any]):
    """Return the file format for a given ref and schema

    We have had mutliple iterations of file schemas. At some point, we had a unique
    File ref with a "format" field.
    """
    ref_name = ref_name.removeprefix("#/$defs/")
    match ref_name:
        case "Image":
            return FileKind.IMAGE
        case "File":
            try:
                return FileKind(schema.get("format"))
            except ValueError:
                return None
        case "Audio":
            return FileKind.AUDIO
        case "PDF":
            return FileKind.PDF
        case _:
            return None


def schema_contains_file(schema: dict[str, Any]) -> bool:
    if "$defs" not in schema:
        return False
    return any(k in schema["$defs"] for k in FILE_DEFS)
