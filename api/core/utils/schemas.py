import re
from typing import (
    Any,
    Callable,
    Iterator,
    Literal,
    NamedTuple,
    NotRequired,
    Optional,
    Protocol,
    Self,
    Sequence,
    TypedDict,
    Union,
    cast,
)

FieldType = Literal["string", "number", "integer", "boolean", "object", "array", "null", "array_length", "date"]

# using a single type for json schema for simplicity
# If that is not enough, we could switch to union types or even a pydantic model
RawJsonSchema = TypedDict(
    "RawJsonSchema",
    {
        "$defs": NotRequired[dict[str, "RawJsonSchema"]],
        "title": NotRequired[str],
        "description": NotRequired[str],
        "examples": NotRequired[list[Any]],
        "default": NotRequired[Any],
        "type": FieldType,
        "enum": NotRequired[list[Any]],
        "format": NotRequired[str],
        # Object
        "properties": NotRequired[dict[str, "RawJsonSchema"]],
        "required": NotRequired[list[str]],
        "additionalProperties": NotRequired[Union[bool, dict[str, "RawJsonSchema"]]],
        # Array
        "items": NotRequired[Union["RawJsonSchema", list["RawJsonSchema"]]],
        # OneOf
        "oneOf": NotRequired[list["RawJsonSchema"]],
        # AnyOf
        "anyOf": NotRequired[list["RawJsonSchema"]],
        # AllOf
        "allOf": NotRequired[list["RawJsonSchema"]],
        # Ref
        "$ref": NotRequired[str],
        "followed_ref_name": NotRequired[str],
    },
    total=False,
)


class InvalidSchemaError(Exception):
    pass


class JsonSchema:
    def __init__(
        self,
        schema: Union[RawJsonSchema, dict[str, Any]],
        defs: Optional[dict[str, "RawJsonSchema"]] = None,
        is_nullable: bool = False,
        # TODO: it's a bit convoluted but the parent property is only set
        # when the schema is created from a child schema, not when using sub_schema
        parent: tuple["JsonSchema", str | int] | None = None,
    ) -> None:
        self.schema = schema
        self.defs = defs or schema.get("$defs", {})
        self.is_nullable = is_nullable
        self.parent = parent

    @property
    def type(self) -> Optional[FieldType]:
        return self._guess_type(self.schema)

    @property
    def format(self) -> Optional[str]:
        return self.schema.get("format")

    @property
    def title(self) -> Optional[str]:
        return self.schema.get("title")

    @property
    def followed_ref_name(self) -> Optional[str]:
        return self.schema.get("followed_ref_name")

    @classmethod
    def _guess_type(cls, schema: RawJsonSchema | dict[str, Any]) -> FieldType | None:
        explicit_type = schema.get("type", None)
        if explicit_type is not None:
            return explicit_type

        if "properties" in schema:
            return "object"
        if "items" in schema:
            return "array"
        return None

    @classmethod
    def _get_def(
        cls,
        uri: str,
        defs: Optional[dict[str, "RawJsonSchema"]],
        original_schema: RawJsonSchema,
    ) -> RawJsonSchema:
        key = uri.split("/")
        if key[0] != "#":
            raise InvalidSchemaError("Only local refs are supported")
        if len(key) != 3:
            raise InvalidSchemaError(f"Invalid ref {uri}")
        if not defs:
            raise InvalidSchemaError("No definitions found")

        schema = defs.get(key[2])
        if schema is None:
            raise InvalidSchemaError(f"Ref {uri} not found")
        # Not sure why pyright is freaking out here
        # We remove the ref to make sure it is not included in the returned schema and to
        # avoid an infinite recursion
        without_ref: RawJsonSchema = {k: v for k, v in original_schema.items() if k != "$ref"}  # pyright: ignore
        return {**without_ref, **schema, "followed_ref_name": key[2]}

    @classmethod
    def _one_any_all_of(cls, schema: RawJsonSchema) -> Optional[list[RawJsonSchema]]:
        """Return the components of oneOf, anyOf, allOf if they exist"""
        keys = ("oneOf", "anyOf", "allOf")
        for key in keys:
            sub: list["RawJsonSchema"] | None = schema.get(key)  # type: ignore
            if sub:
                return sub
        return None

    @classmethod
    def splat_nulls(cls, schema: RawJsonSchema) -> tuple[RawJsonSchema, bool]:
        """Returns the sub schema if it contains a oneOf, anyOf, allOf that would represent a nullable value"""
        subs = cls._one_any_all_of(schema)
        if not subs or len(subs) != 2:
            return schema, False

        not_nulls = [sub for sub in subs if "null" != sub.get("type", "")]
        if len(not_nulls) != 1:
            return schema, False

        return not_nulls[0], True

    @classmethod
    def _follow_ref(cls, schema: RawJsonSchema, defs: Optional[dict[str, "RawJsonSchema"]]) -> RawJsonSchema:
        """Returns the sub schema if it contains a $ref"""
        ref = schema.get("$ref")
        if not ref:
            return schema
        return cls._get_def(ref, defs, original_schema=schema)

    @classmethod
    def _supports_key(cls, schema: RawJsonSchema, key: str | int, defs: Optional[dict[str, "RawJsonSchema"]]) -> bool:
        if "$ref" in schema:
            return cls._supports_key(
                cls._get_def(schema["$ref"], defs, original_schema=schema),
                key,
                defs,
            )

        type = cls._guess_type(schema)

        if type == "object":
            return key in schema.get("properties", {})
        if type == "array":
            return key == "items"
        return False

    def __getitem__(self, key: str) -> Any:
        return self.schema[key]  # type: ignore

    def __contains__(self, key: str) -> bool:
        return key in self.schema

    @classmethod
    def _raw_child_schema(  # noqa: C901
        cls,
        schema: RawJsonSchema,
        defs: Optional[dict[str, "RawJsonSchema"]],
        key: str | int,
    ) -> RawJsonSchema:
        schema_type = cls._guess_type(schema)
        if schema_type == "object":
            if "properties" in schema and key in schema["properties"]:
                return schema["properties"][key]
            if (
                "additionalProperties" in schema
                and isinstance(schema["additionalProperties"], dict)
                and key in schema["additionalProperties"]
            ):
                return schema["additionalProperties"][key]
            raise InvalidSchemaError(f"Key {key} not found in object schema")
        if schema_type == "array":
            try:
                idx = int(key)
            except ValueError:
                raise InvalidSchemaError(f"Invalid key {key} for array schema")
            items = schema.get("items")
            if not items:
                raise InvalidSchemaError("Array schema has no items")
            if isinstance(items, list):
                if idx >= len(items):
                    raise InvalidSchemaError(f"Index {idx} out of range")
                return items[idx]
            return items
        if "$ref" in schema:
            ref = schema.get("$ref")
            if not ref:
                raise InvalidSchemaError("Ref not found")
            return cls._raw_child_schema(cls._get_def(ref, defs, original_schema=schema), defs, key)

        options = cls._one_any_all_of(schema)
        if options:
            for option in options:
                if cls._supports_key(option, key, defs):
                    return cls._raw_child_schema(option, defs, key)
            raise InvalidSchemaError(f"Key {key} not found in oneOf, anyOf, allOf schema")

        raise InvalidSchemaError("Schema is not an object or array")

    def _raw_sub_schema(self, keys: Sequence[str | int]) -> RawJsonSchema:
        schema: RawJsonSchema = self.schema  # type: ignore
        for key in keys:
            schema = self._raw_child_schema(schema, self.defs, key)
        return schema

    def child_schema(
        self,
        key: str | int,
        splat_nulls: bool = True,
        follow_refs: bool = True,
    ) -> Self:
        """Get a direct sub schema based on a key"""
        return self.sub_schema([key], splat_nulls=splat_nulls, follow_refs=follow_refs, parent=(self, key))

    def child_iterator(self, splat_nulls: bool = True, follow_refs: bool = True):
        if self.type == "object":
            # Copying the keys to allow for modifications
            for key in list(self.schema.get("properties", dict[str, Any]()).keys()):
                yield key, self.child_schema(key, splat_nulls, follow_refs)
            return
        if self.type == "array":
            items = self.schema.get("items")
            if not items:
                return
            if isinstance(items, list):
                for idx in range(len(items)):  # pyright: ignore [reportUnknownArgumentType]
                    yield idx, self.child_schema(idx, splat_nulls, follow_refs)
                return
            yield 0, self.child_schema(0, splat_nulls, follow_refs)
            return
        # Nothing to do here, there are no children
        return

    def safe_child_schema(
        self,
        key: str | int,
        splat_nulls: bool = True,
        follow_refs: bool = True,
    ) -> Self | None:
        try:
            return self.child_schema(key, splat_nulls, follow_refs)
        except InvalidSchemaError:
            return None

    def sub_schema(
        self,
        keys: Sequence[str | int] = [],
        keypath: str = "",
        splat_nulls: bool = True,
        follow_refs: bool = True,
        parent: tuple["JsonSchema", str | int] | None = None,
    ) -> Self:
        """
        Get a sub schema based on a list of keys or a keypath

        Args:
            keys (list[str], optional): List of keys to follow. If not provided the keypath is used
            keypath (str, optional): A dot separated keypath. Defaults to "" in which case the self is returned
            splat_nulls (bool, optional): If true, anyOf, allOf, etc. that represent a nullable objects are splat into the schema. Defaults to True.
            follow_refs (bool, optional): If true, the schema will follow the $ref key. Defaults to True.

        Returns:
            JsonSchema: The sub schema
        """
        if not keys:
            if not keypath:
                return self
            keys = keypath.split(".")

        schema = self._raw_sub_schema(keys)
        is_nullable = False

        # Diving into oneOf, anyOf, allOf if only one is there
        one_any_all_of = self._one_any_all_of(schema)
        if one_any_all_of and len(one_any_all_of) == 1:
            schema = one_any_all_of[0]

        if splat_nulls:
            schema, is_nullable = self.splat_nulls(schema)
        if follow_refs:
            schema = self._follow_ref(schema, self.defs)
        return self.__class__(schema, self.defs, is_nullable, parent)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self:
            return self[key]
        return default

    class Navigator(Protocol):
        def __call__(self, schema: "JsonSchema", obj: Any) -> None: ...

    def navigate(self, obj: Any, navigators: Sequence[Navigator]):
        def _dive(key: str | int, value: Any):
            try:
                self.child_schema(key).navigate(value, navigators=navigators)
            except InvalidSchemaError:
                pass

        if isinstance(obj, dict):
            # Assuming all keys are strings
            for key, value in cast(dict[str, Any], obj).items():
                _dive(key, value)
        elif isinstance(obj, list):
            for idx, value in enumerate(cast(list[Any], obj)):
                _dive(idx, value)

        # TODO: improve by having pre and post navigators?
        # Some navigators like _strip_json_schema_metadata_keys might benefit from running before the dive (to avoid unnecessary recursions)
        for nav in navigators:
            nav(self, obj=obj)

    def fields_iterator(
        self,
        prefix: list[str],
        dive: Callable[[Self], bool] = lambda _: True,
        follow_refs: bool = True,
    ) -> Iterator[tuple[list[str], FieldType, Self]]:
        t = self.type
        if not t:
            return
        if prefix:
            yield prefix, t, self
        if not dive(self):
            return
        match t:
            case "object":
                for key in list(self.schema.get("properties", {}).keys()):
                    yield from self.child_schema(key, follow_refs=follow_refs).fields_iterator(
                        prefix=[*prefix, key],
                        dive=dive,
                    )
            case "array":
                # Assuming array only has one item
                yield from self.child_schema(0, follow_refs=follow_refs).fields_iterator(
                    prefix=[*prefix, "[]"],
                    dive=dive,
                )
            case _:
                pass

    def _remove_property(self, key: str, recursive: bool):
        properties = self.schema.get("properties")
        if not properties:
            return
        properties.pop(key, None)
        if required := self.schema.get("required"):
            required.remove(key)

        if not properties and recursive:
            self.remove_from_parent(recursive=recursive)

    def _remove_item(self, key: int, recursive: bool):
        items = self.schema.get("items")
        if not items:
            return
        if isinstance(items, list):
            items.pop(key)
            if not items and recursive:
                self.remove_from_parent(recursive=recursive)
            return

        self.schema.pop("items")
        if recursive:
            self.remove_from_parent(recursive=recursive)

    def remove_from_parent(self, recursive: bool = True):
        if not self.parent:
            return

        if isinstance(self.parent[1], str):
            self.parent[0]._remove_property(self.parent[1], recursive=recursive)
            return

        if isinstance(self.parent[1], int):  # pyright: ignore[reportUnnecessaryIsInstance]
            self.parent[0]._remove_item(self.parent[1], recursive=recursive)
            return


def strip_json_schema_metadata_keys(
    d: Any,
    exc_keys: set[str],
    filter: Optional[Callable[[dict[str, Any]], bool]] = None,
) -> Any:
    _ignore_if_parent = {"properties", "extra_properties", "$defs"}

    def _inner(d: Any, parent: str) -> Any:
        ignore_parent = parent in _ignore_if_parent
        should_strip = True
        if isinstance(d, dict):
            if filter:
                should_strip = filter(d)  # pyright: ignore[reportUnknownArgumentType]
        if isinstance(d, dict):
            de: dict[str, Any] = d
            include_key = ignore_parent or not should_strip
            return {k: _inner(v, k) for k, v in de.items() if include_key or k not in exc_keys}
        if isinstance(d, list):
            a: list[Any] = d
            return [_inner(v, "") for v in a]
        return d

    return _inner(d, "")


def strip_metadata(d: Any, keys: set[str] | None = None) -> Any:
    _metadata_keys = keys or {
        "title",
        "description",
        "examples",
        "default",
    }
    return strip_json_schema_metadata_keys(d, _metadata_keys)


def add_required_fields(*args: str) -> Callable[[dict[str, Any]], None]:
    def _add_required_fields_to_schema(schema: dict[str, Any]) -> None:
        required = schema.setdefault("required", [])
        required.extend(args)

    return _add_required_fields_to_schema


def make_optional(schema: dict[str, Any]) -> dict[str, Any]:
    return strip_json_schema_metadata_keys(schema, {"required", "minItems", "minLength", "minimum", "enum"})


# Updated regex to exclude line breaks (\n and \r)
_control_char_re = re.compile(r"[\x00-\x09\x0B-\x0C\x0E-\x1F]+")


def clean_json_string(s: str) -> str:
    # Remove control characters except for line breaks
    return _control_char_re.sub("", s)


def remove_extra_keys(schema: JsonSchema, obj: Any):
    if not obj or not isinstance(obj, dict):
        return

    """Use with navigate to remove all extra keys from a schema"""
    if schema.type != "object":
        return
    try:
        properties = set(schema["properties"].keys())
    except KeyError:
        return

    if not properties:
        # When properties is empty, we consider that the object is a freeform object and that extra keys are allowed
        return

    # We do nothing if additionalProperties is truthy
    # The spec of json schema allows complex values for additionalProperties
    # see https://json-schema.org/understanding-json-schema/reference/object#additionalproperties
    # But for now, we only check if it is not False
    if schema.get("additionalProperties"):
        return

    for key in list(cast(dict[Any, Any], obj).keys()):
        if key not in properties:
            del obj[key]


def remove_optional_nulls_and_empty_strings(schema: JsonSchema, obj: Any):  # noqa: C901
    """Use with navigate to remove all optional nulls and empty strings from a schema.

    Sometimes models return an empty string or null instead of omitting the field
    which can sometimes create schema violations.
    """
    if schema.type != "object":
        return
    if not isinstance(obj, dict):
        return

    required = set(schema.get("required", []))
    for k in list(cast(dict[str, Any], obj).keys()):
        # We keep required keys
        if k in required:
            continue
        val: Any = obj[k]
        # For now we remove all optional nulls since they should not happen
        if val is None:
            del obj[k]
            continue

        # We also remove empty strings but only when they have a format
        # We have seen models return "" for dates for example
        if val == "":
            if (child_schema := schema.safe_child_schema(k)) and child_schema.get("format"):
                del obj[k]


class IsSchemaOnlyContainingOneFileProperty(NamedTuple):
    value: bool
    field_description: str | None


def _get_array_description(array_description: str | None, item_description: str | None, ref_to_type: str) -> str | None:
    if not any([array_description, item_description]):
        return f"Input is an array of {ref_to_type.lower()}s"

    if array_description and item_description:
        return f"Input is an array of {ref_to_type.lower()}s with the following description: {array_description} (each item description is: {item_description})"

    return f"Input is an array of {ref_to_type.lower()}s with the following description: {item_description or array_description}"


def _get_single_object_description(item_description: str | None, ref_to_type: str) -> str | None:
    if not item_description:
        return f"Input is a single {ref_to_type.lower()}"
    return f"Input is a single {ref_to_type.lower()} with the following description: {item_description}"


def _is_ref_to_type(schema: dict[str, Any], types_to_detect: list[str]) -> str | None:
    ref = schema.get("$ref")
    if not ref:
        return None

    for type_ in types_to_detect:
        if ref == f"#/$defs/{type_}":
            return type_
    return None


# TODO: have some kind of cache for this, since currently it is called for each agent run
def is_schema_only_containing_one_property(
    schema: dict[str, Any],
    types_to_detect: list[str] = ["File", "Image"],
) -> IsSchemaOnlyContainingOneFileProperty:
    """
    Detect if a JSON schema has a single property and is only composed of the types in 'types_to_detect', or a list of them.
    The types are checked by looking for references to the types in $defs (e.g. "#/$defs/File").

    Also returns the field description, that will replace the input schema in the prompt we send to the LLMs.
    """
    if schema.get("type") != "object":
        return IsSchemaOnlyContainingOneFileProperty(value=False, field_description=None)

    # Get properties from schema
    properties = schema.get("properties", {})
    if len(properties) != 1:
        return IsSchemaOnlyContainingOneFileProperty(value=False, field_description=None)

    # Get the single property's schema
    property_schema = next(iter(properties.values()))

    # Check if it's directly a file type
    if object_ref_to_type := _is_ref_to_type(property_schema, types_to_detect):
        return IsSchemaOnlyContainingOneFileProperty(
            value=True,
            field_description=_get_single_object_description(
                item_description=property_schema.get("description"),
                ref_to_type=object_ref_to_type,
            ),
        )

    # Check if it's an array of file types
    if property_schema.get("type") == "array":
        items_schema = property_schema.get("items")
        if not items_schema:
            return IsSchemaOnlyContainingOneFileProperty(value=False, field_description=None)

        items_ref_to_type = _is_ref_to_type(items_schema, types_to_detect)
        return IsSchemaOnlyContainingOneFileProperty(
            value=items_ref_to_type is not None,
            field_description=_get_array_description(
                array_description=property_schema.get("description"),
                item_description=items_schema.get("description"),
                ref_to_type=items_ref_to_type,
            )
            if items_ref_to_type
            else None,
        )

    return IsSchemaOnlyContainingOneFileProperty(value=False, field_description=None)


EXPLAINATION_KEY = "explanation"


def schema_needs_explanation(schema: dict[str, Any]) -> bool:
    """
    Detects schemas that need an 'explaination':
    - Schemas that are a single boolean (should not exist in WorkflowAI in theory, but we handle the case)
    - Schemas that are an enum (should not exist in WorkflowAI in theory, but we handle the case)
    - Schemas that are an array of enums (should not exist in WorkflowAI in theory, but we handle the case)
    - Schemas that are objects with a single property that is a boolean, enum, or array of enums
    """

    # Check if the schema is an object with a single property that is a boolean, enum, or array of enums
    if schema.get("type") == "object" and "properties" in schema:
        properties = schema.get("properties", {})
        if len(properties) == 1 and EXPLAINATION_KEY not in properties.keys():
            property_schema = next(iter(properties.values()))
            if _is_enum_or_boolean(property_schema):
                return True

    # Not an enum or boolean
    return False


def _is_enum_or_boolean(schema: dict[str, Any]) -> bool:
    """Helper function to check if a schema is directly a boolean, enum, or array of enums"""
    # Check if it's a boolean
    if schema.get("type") == "boolean":
        return True

    # Check if it's directly an enum
    if "enum" in schema:
        return True

    # Check if it's an array of enums
    if schema.get("type") == "array" and "items" in schema:
        items_schema = schema["items"]
        if "enum" in items_schema:
            return True

    # Handle oneOf, anyOf, allOf if they contain enums
    for key in ["oneOf", "anyOf", "allOf"]:
        if key in schema and len(schema[key]) == 1:
            sub_schema = schema[key][0]
            if "enum" in sub_schema:
                return True

    return False


def schema_from_data(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return {
            "type": "object",
            "properties": {k: schema_from_data(v) for k, v in data.items()},  # pyright: ignore[reportUnknownVariableType]
        }
    if isinstance(data, list):
        if not data:
            return {"type": "array"}
        return {
            "type": "array",
            "items": schema_from_data(data[0]),  # pyright: ignore[reportUnknownVariableType]
        }
    if isinstance(data, bool):
        return {"type": "boolean"}
    if isinstance(data, str):
        return {"type": "string"}
    if isinstance(data, int):
        return {"type": "integer"}
    if isinstance(data, float):
        return {"type": "number"}

    # Not assuming anything on None types
    return {}
