import re
from enum import StrEnum
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel

from core.domain.errors import BadRequestError
from core.utils.schemas import FieldType


class SpecialFieldQueryName(StrEnum):
    REVIEW = "review"


class SearchOperator(StrEnum):
    IS = "is"
    IS_NOT = "is not"
    IS_EMPTY = "is empty"
    IS_NOT_EMPTY = "is not empty"
    CONTAINS = "contains"
    NOT_CONTAINS = "does not contain"
    GREATER_THAN = "greater than"
    GREATER_THAN_OR_EQUAL_TO = "greater than or equal to"
    LESS_THAN = "less than"
    LESS_THAN_OR_EQUAL_TO = "less than or equal to"
    IS_BETWEEN = "is between"
    IS_NOT_BETWEEN = "is not between"
    IS_BEFORE = "is before"
    IS_AFTER = "is after"

    @classmethod
    def string_operators(cls):
        return [cls.IS, cls.IS_NOT, cls.CONTAINS, cls.NOT_CONTAINS]

    @classmethod
    def number_operators(cls):
        return [
            cls.IS,
            cls.IS_NOT,
            cls.GREATER_THAN,
            cls.GREATER_THAN_OR_EQUAL_TO,
            cls.LESS_THAN,
            cls.LESS_THAN_OR_EQUAL_TO,
        ]

    @classmethod
    def equals_operators(cls):
        return [cls.IS, cls.IS_NOT]

    @classmethod
    def date_operators(cls):
        return [cls.IS_BEFORE, cls.IS_AFTER]


class ReviewSearchOptions(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNSURE = "unsure"
    ANY = "any"


class StatusSearchOptions(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


# All the fields searchable by the search API
class SearchField(StrEnum):
    REVIEW = "review"
    SCHEMA_ID = "schema"
    VERSION = "version"
    PRICE = "price"
    LATENCY = "latency"
    TEMPERATURE = "temperature"
    MODEL = "model"
    SOURCE = "source"
    TIME = "time"
    STATUS = "status"

    INPUT = "input"
    OUTPUT = "output"
    METADATA = "metadata"

    # Used internally to fetch runs that were evaluated
    # Converted from the REVIEW field by the search service
    EVAL_HASH = "eval_hash"


# An option for a field in the search API
class SearchFieldOption(NamedTuple):
    field_name: SearchField
    operators: list[SearchOperator]
    type: FieldType
    suggestions: list[Any] | None = None
    key_path: str | None = None

    @classmethod
    def for_date(cls, field: SearchField, key_path: str | None = None):
        return cls(
            field_name=field,
            operators=[SearchOperator.IS_BEFORE, SearchOperator.IS_AFTER],
            suggestions=None,
            type="date",
            key_path=key_path,
        )


type SingleValueOperator = Literal[
    SearchOperator.IS,
    SearchOperator.IS_NOT,
    SearchOperator.IS_EMPTY,
    SearchOperator.IS_NOT_EMPTY,
    SearchOperator.CONTAINS,
    SearchOperator.NOT_CONTAINS,
    SearchOperator.GREATER_THAN,
    SearchOperator.GREATER_THAN_OR_EQUAL_TO,
    SearchOperator.LESS_THAN,
    SearchOperator.LESS_THAN_OR_EQUAL_TO,
    SearchOperator.IS_BEFORE,
    SearchOperator.IS_AFTER,
]


class SearchOperationSingle(NamedTuple):
    operator: SingleValueOperator
    value: Any

    @property
    def is_greater_op(self):
        """Returns true if the comparison is related to a greater than operation"""
        return self.operator in {
            SearchOperator.GREATER_THAN,
            SearchOperator.GREATER_THAN_OR_EQUAL_TO,
            SearchOperator.IS_AFTER,
        }

    @property
    def is_less_op(self):
        """Returns true if the comparison is related to a less than operation"""
        return self.operator in {
            SearchOperator.LESS_THAN,
            SearchOperator.LESS_THAN_OR_EQUAL_TO,
            SearchOperator.IS_BEFORE,
        }


class SearchOperationBetween(NamedTuple):
    operator: Literal[SearchOperator.IS_BETWEEN, SearchOperator.IS_NOT_BETWEEN]
    value: tuple[Any, Any]


type SearchOperation = SearchOperationSingle | SearchOperationBetween


type SimpleSearchField = Literal[
    SearchField.REVIEW,
    SearchField.SCHEMA_ID,
    SearchField.VERSION,
    SearchField.PRICE,
    SearchField.LATENCY,
    SearchField.TEMPERATURE,
    SearchField.MODEL,
    SearchField.SOURCE,
    SearchField.TIME,
    SearchField.STATUS,
    SearchField.EVAL_HASH,
    SearchField.INPUT,
    SearchField.OUTPUT,
]


# A query on a single field
class SearchQuerySimple(NamedTuple):
    field: SimpleSearchField
    operation: SearchOperation
    field_type: FieldType | None = None


type NestedSearchField = Literal[SearchField.INPUT, SearchField.OUTPUT, SearchField.METADATA]


# A query on a nested field
class SearchQueryNested(NamedTuple):
    field: NestedSearchField
    field_type: FieldType | None
    key_path: str
    operation: SearchOperation

    def validate_keypath(self):
        if not re.match(r"^[a-zA-Z0-9\[\]_]+(\.[a-zA-Z0-9\[\]_]+)*$", self.key_path):
            raise BadRequestError(
                message="Invalid nested field format",
                extra={"key_path": self.key_path},
                # Capturing, the frontend should not send invalid keypaths
                capture=True,
            )


SearchQuery = SearchQuerySimple | SearchQueryNested


# TODO: this object is used in the API layer. If breaking changes are needed duplicate the object
class FieldQuery(BaseModel):
    field_name: str
    operator: SearchOperator
    values: list[Any]
    type: FieldType | None = None
