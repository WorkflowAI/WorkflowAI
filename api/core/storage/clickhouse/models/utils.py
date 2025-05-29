import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from pydantic import AfterValidator, BaseModel, BeforeValidator, PlainSerializer

from core.domain.errors import BadRequestError, InternalError
from core.domain.search_query import SearchOperation, SearchOperationBetween, SearchOperator
from core.storage.clickhouse.query_builder import WJSON, W, WJSONArray, WJSONArrayLength
from core.utils.generics import BM
from core.utils.schemas import FieldType
from core.utils.uuid import uuid7


def data_and_columns(model: BaseModel, exclude_none: bool = True):
    dumped = model.model_dump(exclude_none=exclude_none)
    data: list[Any] = []
    columns: list[str] = []

    for key, value in dumped.items():
        data.append(value)
        columns.append(key)
    return data, columns


def round_to(ndigits: int, /) -> AfterValidator:
    return AfterValidator(lambda v: round(v, ndigits))


RoundedFloat = Annotated[float, round_to(10)]


def parse_ck_str_list(t: type[BM], v: Any) -> list[BM] | None:
    # TODO: this should be extracted into a before validator
    if not v:
        return None
    if not isinstance(v, list):
        raise ValueError("Expected a list")

    return [t.model_validate_json(k) if isinstance(k, str) else t.model_validate(k) for k in v]  # pyright: ignore [reportUnknownVariableType]


def dump_ck_str_list(seq: Sequence[BaseModel]):
    if not seq:
        return list[str]()
    return [t.model_dump_json(by_alias=True, exclude_none=True) for t in seq]


MAX_UINT_8 = 255
MAX_UINT_16 = 65535
MAX_UINT_32 = 4_294_967_295


def validate_int(
    max_value: int,
    log_name: str | None = None,
    warning: bool = True,
    unsigned: bool = True,
) -> AfterValidator:
    def _cap(v: int | None) -> int | None:
        if v is None:
            return None
        if v > max_value:
            if not log_name:
                raise ValueError(f"Value too large {v} > {max_value}")
            if warning:
                logging.getLogger(__name__).warning(
                    f"Value {log_name} too large",  # noqa: G004
                    extra={"value": v, "max_value": max_value},
                )
            return max_value
        if unsigned and v < 0:
            if not log_name:
                raise ValueError(f"Found negative value {v} < 0")
            if warning:
                logging.getLogger(__name__).warning(
                    f"Found negative value {log_name}",  # noqa: G004
                    extra={"value": v},
                )
            return 0
        return v

    return AfterValidator(_cap)


def validate_fixed(size: int = 32, log_name: str | None = None):
    def _validate(v: str) -> str:
        # Clickhouse strings are padded with null bytes, so we need to strip them
        v = v.rstrip("\x00")
        encoded = v.encode("utf-8")
        if len(encoded) > size:
            if not log_name:
                raise ValueError(f"Value must be at most {size} characters long")
            logging.getLogger(__name__).warning(
                f"Value {log_name} too large",  # noqa: G004
                extra={"value": v, "max_value": size},
            )
            # Truncating to the max size, decoding by ignoring errors
            return encoded[:size].decode("utf-8", errors="ignore")
        return v

    return AfterValidator(_validate)


def _like_mapper(v: Any):
    if not isinstance(v, str):
        raise InternalError("Value in like must be a string", extras={"value": v})
    return f"%{v}%"


_OPERATOR_MAP: dict[SearchOperator, tuple[str, Callable[[Any], Any] | None]] = {
    SearchOperator.IS: ("=", None),
    SearchOperator.IS_NOT: ("!=", None),
    SearchOperator.CONTAINS: ("ILIKE", _like_mapper),
    SearchOperator.NOT_CONTAINS: ("NOT ILIKE", _like_mapper),
    SearchOperator.GREATER_THAN: (">", None),
    SearchOperator.GREATER_THAN_OR_EQUAL_TO: (">=", None),
    SearchOperator.LESS_THAN: ("<", None),
    SearchOperator.LESS_THAN_OR_EQUAL_TO: ("<=", None),
    SearchOperator.IS_BETWEEN: (W.BETWEEN, None),
    SearchOperator.IS_NOT_BETWEEN: (W.NOT_BETWEEN, None),
    SearchOperator.IS_BEFORE: ("<=", None),
    SearchOperator.IS_AFTER: (">=", None),
    SearchOperator.IS_EMPTY: (W.EMPTY, lambda _: None),
    SearchOperator.IS_NOT_EMPTY: (W.NOT_EMPTY, lambda _: None),
}


def _operator_and_value(op: SearchOperation, map_fn: Callable[[Any], Any] | None):
    if isinstance(op, SearchOperationBetween):
        value = [map_fn(v) for v in op.value] if map_fn else op.value
    else:
        value = map_fn(op.value) if (op.value is not None and map_fn) else op.value

    if o := _OPERATOR_MAP.get(op.operator):
        # TODO: map array if needed ?
        return o[0], o[1](value) if o[1] else value

    raise InternalError("Unsupported operator", extras={"operator": op.operator})


def clickhouse_query(
    key: str,
    op: SearchOperation,
    type: str | None = None,
    map_fn: Callable[[Any], Any] | None = None,
):
    operator, value = _operator_and_value(op, map_fn)
    return W(key, value=value, operator=operator, type=type)


def json_query(field_type: FieldType | None, field: str, key_path: str, operation: SearchOperation):
    splits = key_path.split("[]")
    operator, value = _operator_and_value(operation, None)
    # If the key path is not an array, we can just use the WJSON class
    if len(splits) == 1:
        if field_type == "array_length":
            return WJSONArrayLength(key=field, path=key_path, operator=operator, type=field_type, value=value)
        return WJSON(key=field, path=key_path, operator=operator, type=field_type, value=value)

    # if we have more than 2 splits, it means that we are getting
    # an array of arrays. Throwing for now, we could try and support
    # later
    if len(splits) > 2:
        raise BadRequestError("Requested nested array query", extras={"key_path": key_path}, capture=True)

    # Otherwise we have to wrap a json query
    if splits[1] == "":
        nested_w = W(key=field, operator=operator, type=field_type, value=value)
    else:
        nested_w = WJSON(key=field, path=splits[1].removeprefix("."), operator=operator, type=field_type, value=value)

    return WJSONArray(key=field, path=splits[0], clause=nested_w)


def id_lower_bound(value: datetime):
    # We just 0 the gen as a lower bound
    time_ms = int((value).timestamp() * 1000)
    return uuid7(ms=lambda: time_ms, rand=lambda: 0).int


def id_upper_bound(value: datetime):
    # As an upper bound, we need to add a second to the id
    time_ms = int((value + timedelta(seconds=1)).timestamp() * 1000)
    return uuid7(ms=lambda: time_ms, rand=lambda: 0).int


def serialize_uuid_as_int(uuid: UUID):
    return uuid.int


def parse_uuid_as_int(value: Any):
    if isinstance(value, int):
        return UUID(int=value)
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        return UUID(value)
    raise ValueError("Invalid run_uuid")


UUID_AS_INT = Annotated[UUID, BeforeValidator(parse_uuid_as_int), PlainSerializer(serialize_uuid_as_int)]
