from collections.abc import Sequence
from typing import Any, Literal, cast, override
from uuid import UUID

_ClickhouseType = Literal["Bool", "Int", "Float", "UUID", "String", "Date", "Array", "Object", "Null", "Dynamic"]

_FIELD_MAP_TYPE: dict[str, _ClickhouseType] = {
    "boolean": "Bool",
    "integer": "Int",
    "number": "Float",
    "string": "String",
    "array": "Array",
    "object": "Object",
    "null": "Null",
    "array_length": "Int",
    "date": "Date",
}


def _is_numeric_type(type: str):
    starts = ["int", "float", "uint"]
    type = type.lower()
    return any(type.startswith(start) for start in starts)


class W:
    BETWEEN = "BETWEEN"
    NOT_BETWEEN = "NOT BETWEEN"

    EMPTY = "EMPTY"
    NOT_EMPTY = "NOT EMPTY"

    def __init__(self, key: str, value: Any | None = None, operator: str = "=", type: str | None = None) -> None:
        self._key = key
        self._type: _ClickhouseType | None = self._determine_type(value, type)
        self._value = value
        self._operator = operator

    @property
    def type(self) -> _ClickhouseType:
        return self._type or "Dynamic"

    @classmethod
    def _determine_type(cls, value: Any | None, type: str | None) -> _ClickhouseType | None:
        if type:
            # TODO: remove the cast and force a mapping
            return _FIELD_MAP_TYPE.get(type) or cast(_ClickhouseType, type)
        match value:
            case bool():
                return "Bool"
            case int():
                return "Int"
            case float():
                return "Float"
            case UUID():
                return "UUID"
            case str():
                return "String"
            case _:
                return None

    @classmethod
    def _empty_sql(cls, key: str, type: _ClickhouseType):
        if _is_numeric_type(type):
            return f"{key} = 0"
        if type == "String":
            return f"empty({key})"
        return f"isNull({key})"

    @classmethod
    def _not_empty_sql(cls, key: str, type: _ClickhouseType):
        if _is_numeric_type(type):
            return f"{key} != 0"
        if type == "String":
            return f"notEmpty({key})"
        return f"isNotNull({key})"

    @classmethod
    def _is_in_query(cls, type: _ClickhouseType | None, operator: str, value: Any):
        return (
            type
            and (operator == "=" or operator == "!=")
            and (type == "String" or _is_numeric_type(type))
            and bool(value)
            and (isinstance(value, list) or isinstance(value, set))
        )

    @classmethod
    def _in_query_sql(cls, key: str, type: _ClickhouseType | None, operator: str, value: Any, param_start: int):
        if not cls._is_in_query(type, operator, value):
            return None
        if len(value) == 1:
            value = next(iter(value))
            param, param_str = cls._param(param_start, type)
            return f"{key} {operator} {{{param_str}}}", {param: value}

        operator = "IN" if operator == "=" else "NOT IN"

        # Preparing for the IN operator
        param_strs: list[str] = []
        params: dict[str, Any] = {}
        for idx, value in enumerate(value):
            s = f"v{param_start}_{idx}"
            param_strs.append(f"{s}:{cls._determine_type(value=value, type=type)}")
            params[s] = value
        return f"{key} {operator} ({{{'}, {'.join(param_strs)}}})", params

    @classmethod
    def _between_sql(cls, key: str, value: Any, operator: str, type: _ClickhouseType | None, param_start: int = 0):
        if operator != cls.BETWEEN and operator != cls.NOT_BETWEEN:
            return None

        param1, param1_str = cls._param(param_start, cls._determine_type(value=value[0], type=type))
        param2, param2_str = cls._param(param_start + 1, cls._determine_type(value=value[1], type=type))

        return f"{key} {operator} {{{param1_str}}} AND {{{param2_str}}}", {
            param1: value[0],
            param2: value[1],
        }

    @classmethod
    def _build_sql(
        cls,
        key: str,
        value: Any,
        operator: str,
        type: _ClickhouseType | None,
        param_start: int = 0,
    ) -> tuple[str, dict[str, Any]] | None:
        if value is None:
            if operator == cls.EMPTY:
                return cls._empty_sql(key=key, type=type or "Dynamic"), {}
            if operator == cls.NOT_EMPTY:
                return cls._not_empty_sql(key=key, type=type or "Dynamic"), {}
            return key, {}

        if between_query := cls._between_sql(key, value, operator, type, param_start=param_start):
            return between_query

        if in_query := cls._in_query_sql(key, type, operator, value, param_start=param_start):
            return in_query

        param, param_str = cls._param(idx=param_start, type=type)
        return f"{key} {operator} {{{param_str}}}", {param: value}

    def to_sql(self, param_start: int = 0, key: str | None = None):
        return self._build_sql(
            key=key or self._key,
            value=self._value,
            operator=self._operator,
            type=self._type,
            param_start=param_start,
        )

    def to_sql_req(self, param_start: int = 0):
        if sql := self.to_sql(param_start):
            return sql
        raise ValueError("Invalid query")

    @classmethod
    def _param(cls, idx: int, type: str | None):
        return f"v{idx}", f"v{idx}:{type or 'Dynamic'}"

    def __and__(self, other: "W"):
        """Implement the & operator."""
        return WhereAndClause([self, other])

    def __or__(self, other: "W"):
        """Implement the | operator."""
        return WhereOrClause([self, other])

    def __iand__(self, other: "W"):
        """Implement the &= operator."""
        return self & other

    def _join(self, clauses: Sequence["W"], separator: str, param_start: int = 0):
        if len(clauses) == 0:
            return None
        if len(clauses) == 1:
            return clauses[0].to_sql(param_start)
        joined: list[str] = []
        values: dict[str, Any] = {}
        for clause in clauses:
            if c := clause.to_sql(param_start):
                joined.append(c[0])
                values.update(c[1])
                param_start += len(c[1])
        return separator.join(joined), values


class WJSON(W):
    def __init__(
        self,
        key: str,
        path: str,
        value: Any | None = None,
        operator: str = "=",
        type: str | None = None,
    ) -> None:
        super().__init__(key, value, operator, type)
        self._path = path

    @classmethod
    def _json_extract_fn(cls, field_type: _ClickhouseType | None, simple: bool) -> str:
        # See https://clickhouse.com/docs/en/sql-reference/functions/json-functions
        match field_type:
            case "String":
                return "simpleJSONExtractString" if simple else "JSONExtractString"
            case "Float":
                return "simpleJSONExtractFloat" if simple else "JSONExtractFloat"
            case "Int":
                return "simpleJSONExtractInt" if simple else "JSONExtractInt"
            case "Bool":
                return "simpleJSONExtractBool" if simple else "JSONExtractBool"
            case _:
                return "simpleJSONExtractRaw" if simple else "JSONExtractRaw"

    @classmethod
    def _json_extracted_key(cls, field_type: _ClickhouseType | None, field: str, key_path: str):
        splits = key_path.split(".")
        if len(splits) == 1:
            fn = cls._json_extract_fn(field_type, simple=True)
            return f"{fn}({field}, '{key_path}')"
        fn = cls._json_extract_fn(field_type, simple=False)
        joined_key_path = "', '".join(splits)
        return f"{fn}({field}, '{joined_key_path}')"

    @override
    def to_sql(self, param_start: int = 0, key: str | None = None) -> tuple[str, dict[str, Any]] | None:
        key = self._json_extracted_key(self._type, key or self._key, self._path)
        return self._build_sql(
            key=key,
            value=self._value,
            operator=self._operator,
            type=self._type,
            param_start=param_start,
        )


class WJSONArrayLength(WJSON):
    @classmethod
    @override
    def _json_extract_fn(cls, *_args: Any, **_kwargs: Any):
        return "JSONLength"


class WJSONArray(W):
    """Clause to find an element in a JSON array"""

    def __init__(self, key: str, path: str, clause: W):
        """Default constructor

        Args:
            key (str): the key of the JSON array
            clause (W): the clause to apply to the JSON array. The key must be a JSON path *relative* to the key.
        """
        super().__init__(key, None, "exists", None)
        self._clause = clause
        self._path = path

    @override
    def to_sql(self, param_start: int = 0, key: str | None = None) -> tuple[str, dict[str, Any]] | None:
        key = key or self._key
        sub = self._clause.to_sql(param_start, key="x")
        if not sub:
            return None
        extract_fn = (
            f"JSONExtractArrayRaw({key}, '{self._path}')"
            if isinstance(self._clause, WJSON)
            else f"JSONExtract({key}, '{self._path}', 'Array({self._clause.type})')"
        )

        return f"arrayExists(x -> {sub[0]}, {extract_fn})", sub[1]


class WhereAndClause(W):
    def __init__(self, clauses: list[W]) -> None:
        self.clauses = clauses

    @override
    def __and__(self, other: W) -> "WhereAndClause":
        if isinstance(other, WhereAndClause):
            return WhereAndClause(self.clauses + other.clauses)
        return WhereAndClause(self.clauses + [other])

    @override
    def to_sql(self, param_start: int = 0, key: str | None = None) -> tuple[str, dict[str, Any]] | None:
        return self._join(self.clauses, " AND ", param_start)


class WhereOrClause(W):
    def __init__(self, clauses: list[W]) -> None:
        self.clauses = clauses

    @override
    def __or__(self, other: W) -> "WhereOrClause":
        if isinstance(other, WhereOrClause):
            return WhereOrClause(self.clauses + other.clauses)
        return WhereOrClause(self.clauses + [other])

    @override
    def to_sql(self, param_start: int = 0, key: str | None = None) -> tuple[str, dict[str, Any]] | None:
        return self._join(self.clauses, " OR ", param_start)


def Q(
    f: str,
    select: Sequence[str] | None = None,
    where: W | None = None,
    prewhere: W | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: Sequence[str] | None = None,
    distincts: Sequence[str] | None = None,
    limit_by: tuple[str, int] | None = None,
):
    components = ["SELECT"]
    if distincts:
        components.append(f"DISTINCT ON ({', '.join(distincts)})")

    components.append(f"{', '.join(select) if select else '*'} FROM {f}")
    parameters: dict[str, Any] | None = {}

    if prewhere and (s := prewhere.to_sql()):
        components.append(f"PREWHERE {s[0]}")
        parameters.update(s[1])

    if where and (s := where.to_sql(param_start=len(parameters))):
        components.append(f"WHERE {s[0]}")
        parameters.update(s[1])

    if order_by:
        components.append(f"ORDER BY {', '.join(order_by)}")
    if limit_by:
        components.append(f"LIMIT {limit_by[1]} BY {limit_by[0]}")
    if limit:
        components.append(f"LIMIT {limit}")
    if offset:
        components.append(f"OFFSET {offset}")

    return " ".join(components), parameters
