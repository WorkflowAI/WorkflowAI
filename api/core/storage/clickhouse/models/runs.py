import json
import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, field_serializer, field_validator

from core.domain.agent_run import AgentRun
from core.domain.consts import METADATA_KEY_PROVIDER_NAME
from core.domain.error_response import ErrorResponse
from core.domain.errors import BadRequestError, InternalError
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.llm_completion import LLMCompletion
from core.domain.llm_usage import LLMUsage
from core.domain.models import Provider
from core.domain.models.models import Model
from core.domain.search_query import (
    SearchField,
    SearchOperation,
    SearchOperationSingle,
    SearchOperator,
    SearchQuery,
    SearchQueryNested,
    StatusSearchOptions,
)
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_run_query import SerializableTaskRunField, SerializableTaskRunQuery
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.domain.types import AgentOutput
from core.domain.utils import compute_eval_hash
from core.domain.version_environment import VersionEnvironment
from core.storage import ObjectNotFoundException
from core.storage.clickhouse.models.utils import (
    MAX_UINT_8,
    MAX_UINT_16,
    MAX_UINT_32,
    UUID_AS_INT,
    RoundedFloat,
    clickhouse_query,
    dump_ck_str_list,
    id_lower_bound,
    id_upper_bound,
    json_query,
    parse_ck_str_list,
    validate_fixed,
    validate_int,
)
from core.storage.clickhouse.query_builder import W
from core.utils.fields import date_zero, uuid_zero
from core.utils.hash import compute_obj_hash
from core.utils.iter_utils import safe_map_optional
from core.utils.models.dumps import safe_dump_pydantic_model
from core.utils.uuid import is_uuid7, uuid7, uuid7_generation_time

_logger = logging.getLogger(__name__)


def _temperature_percent(temperature: float | None) -> int:
    return int(round(temperature * 100)) if temperature else 0


def _from_temperature_percent(temperature: int) -> float:
    return temperature / 100


def _stringify_json(data: Any) -> str:
    # Remove spaces from the JSON string to allow using simplified json queries
    # see https://clickhouse.com/docs/en/sql-reference/functions/json-functions#simplejsonextractstring
    return json.dumps(data, separators=(",", ":"))


def _from_stringified_json(data: str) -> Any:
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return data


def _duration_ds(duration: float | None) -> int:
    return int(round(duration * 10)) if duration else 0


def _cost_millionth_usd(cost: float | None) -> int:
    return int(round(cost * 1_000_000)) if cost else 0


def _sanitize_metadata_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _from_sanitized_metadata_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _sanitize_metadata(metadata: dict[str, Any] | None, provider: str | None):
    converted = {k: _sanitize_metadata_value(v) for k, v in metadata.items()} if metadata else {}
    if METADATA_KEY_PROVIDER_NAME not in converted and provider:
        converted[METADATA_KEY_PROVIDER_NAME] = provider

    return converted or None


def _from_sanitized_metadata(metadata: dict[str, str] | None):
    if not metadata:
        return None
    return {k: _from_sanitized_metadata_value(v) for k, v in metadata.items()}


_FIELD_TO_QUERY: dict[SearchField, tuple[str, str, Callable[[Any], Any] | None]] = {
    SearchField.PRICE: ("cost_millionth_usd", "UInt32", _cost_millionth_usd),
    SearchField.LATENCY: ("duration_ds", "UInt16", _duration_ds),
    SearchField.TEMPERATURE: ("version_temperature_percent", "UInt8", _temperature_percent),
    SearchField.MODEL: ("version_model", "String", None),
    SearchField.SCHEMA_ID: ("task_schema_id", "UInt16", None),
    SearchField.SOURCE: ("is_active", "Bool", None),  # query is already parsed upstream
}

FIELD_TO_COLUMN: dict[SerializableTaskRunField, str] = {
    "_id": "run_uuid",
    "task_output": "output",
    "task_output_hash": "output_hash",
    "task_schema_id": "task_schema_id",
    "llm_completions": "llm_completions",
    "status": "error_payload",
    "metadata": "metadata",
    "tool_calls": "tool_calls",
    "tool_call_requests": "tool_calls",
    "task_input": "input",
    "task_input_hash": "input_hash",
    "version_id": "version_id",
    "group.iteration": "version_iteration",
    "group.properties": "version_model",
    "created_at": "run_uuid",
    "eval_hash": "eval_hash",
}

CLICKHOUSE_RUN_VERSION = 6


class ClickhouseRun(BaseModel):
    tenant_uid: Annotated[int, validate_int(MAX_UINT_32)] = 0
    task_uid: Annotated[int, validate_int(MAX_UINT_32)] = 0
    created_at_date: date = Field(default_factory=date_zero)

    run_uuid: UUID_AS_INT = Field(default_factory=uuid_zero)
    conversation_id: UUID_AS_INT = Field(default_factory=uuid_zero)

    @classmethod
    def from_cost_millionth_usd(cls, cost: int) -> float:
        return cost / 1_000_000

    @classmethod
    def from_duration_ds(cls, duration: int) -> float:
        return duration / 10

    task_schema_id: Annotated[int, validate_int(MAX_UINT_16)] = 0
    version_id: Annotated[str, validate_fixed()] = ""
    version_model: str = ""
    # TODO[iteration]: Field should be removed
    version_iteration: int = 0
    version_temperature_percent: int = 0

    @property
    def task_group(self) -> TaskGroup:
        return TaskGroup(
            id=self.version_id,
            iteration=self.version_iteration,
            properties=TaskGroupProperties(
                model=self.version_model,
                temperature=_from_temperature_percent(self.version_temperature_percent),
            ),
        )

    # Hashes are MD5 strings
    input_hash: Annotated[str, validate_fixed()] = ""
    output_hash: Annotated[str, validate_fixed()] = ""
    eval_hash: Annotated[str, validate_fixed()] = ""
    cache_hash: Annotated[str, validate_fixed()] = ""

    input_preview: str = ""
    input: Any = Field(default_factory=dict)

    @field_serializer("input")
    def serialize_input(self, input: dict[str, Any]) -> str:
        return _stringify_json(input)

    @field_validator("input", mode="before")
    def parse_input(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            return _from_stringified_json(value)
        return value

    output_preview: str = ""
    output: Any = Field(default=None)

    @field_serializer("output")
    def serialize_output(self, output: AgentOutput) -> str:
        return _stringify_json(output) if output else ""

    @field_validator("output", mode="before")
    def parse_output(cls, value: Any) -> AgentOutput:
        if isinstance(value, str):
            return _from_stringified_json(value) if value else {}
        return value

    duration_ds: Annotated[int, validate_int(MAX_UINT_16, "duration_ds")] = 0
    # Right now we are seeing high overhead values when handling large images
    # as base64 data on some deprecated tasks. Silencing the warning for now
    # TODO: set warning back to True when we have figured out the source of the overhead
    overhead_ms: Annotated[int, validate_int(MAX_UINT_8, "overhead_ms", warning=False)] = 0
    cost_millionth_usd: Annotated[int, validate_int(MAX_UINT_32, "cost_millionth_usd")] = 0
    input_token_count: Annotated[int, validate_int(MAX_UINT_32, "input_token_count")] = 0
    output_token_count: Annotated[int, validate_int(MAX_UINT_32, "output_token_count")] = 0

    class _Error(BaseModel):
        title: str | None = None
        details: dict[str, Any] | None = None
        message: str
        status_code: int
        code: str

        @classmethod
        def from_run(cls, run: AgentRun):
            if run.error:
                if run.status == "success":
                    _logger.warning("Run has an error but status is success", extra={"run_id": run.id})
                return cls.from_domain(run.error)
            if run.status == "failure":
                _logger.warning("Run has no error but status is failure", extra={"run_id": run.id})
                return cls(
                    message="Internal error",
                    status_code=0,
                    code="internal_error",
                )

            return None

        @classmethod
        def from_domain(cls, error: ErrorResponse.Error):
            return cls(
                title=error.title,
                details=error.details,
                message=error.message,
                status_code=error.status_code,
                code=error.code,
            )

        def to_domain(self) -> ErrorResponse.Error:
            return ErrorResponse.Error(
                title=self.title,
                details=self.details,
                message=self.message,
                status_code=self.status_code,
                code=self.code,
            )

    # A stringified json payload for the error
    error_payload: _Error | None = None

    @field_serializer("error_payload")
    def serialize_error_payload(self, error_payload: _Error | None):
        if error_payload:
            return _stringify_json(error_payload.model_dump(by_alias=True, exclude_none=True))
        return ""

    @field_validator("error_payload", mode="before")
    def parse_error_payload(cls, value: Any) -> _Error | None:
        if not value:
            return None
        if isinstance(value, str):
            try:
                return cls._Error.model_validate_json(value)
            except ValidationError:
                _logger.warning("Invalid error payload", extra={"error_payload": value})
                return None
        return value

    @property
    def error(self) -> ErrorResponse.Error | None:
        if self.error_payload:
            return self.error_payload.to_domain()
        return None

    metadata: dict[str, str] | None = None

    @field_serializer("metadata")
    def serialize_metadata(self, metadata: dict[str, str] | None):
        return metadata or dict[str, str]()

    author_uid: Annotated[int | None, validate_int(MAX_UINT_32, "author_uid")] = None

    @field_serializer("author_uid")
    def serialize_author_uid(self, author_uid: int | None):
        if author_uid is None:
            return 0
        return author_uid

    is_active: bool = False

    class _ToolCall(BaseModel):
        id: str | None = None
        name: str | None = None
        input: dict[str, Any] | None = None
        output: Any | None = None
        error: str | None = None

        @classmethod
        def from_domain(cls, tool_call: ToolCallRequestWithID | ToolCall):
            is_final = isinstance(tool_call, ToolCall)
            return cls(
                id=tool_call.id or None,
                name=tool_call.tool_name or None,
                input=tool_call.tool_input_dict or None,
                output=tool_call.result if is_final else None,
                error=tool_call.error if is_final else None,
            )

        def to_domain(self) -> ToolCallRequestWithID | ToolCall:
            if self.error or self.output:
                return ToolCall(
                    id=self.id or "",
                    tool_name=self.name or "",
                    tool_input_dict=self.input or {},
                    result=self.output or None,
                    error=self.error or None,
                )
            return ToolCallRequestWithID(
                id=self.id or "",
                tool_name=self.name or "",
                tool_input_dict=self.input or {},
            )

    # ---------------------------
    # Tool calls

    tool_calls: list[_ToolCall] | None = None

    @field_serializer("tool_calls")
    def serialize_tool_calls(self, tool_calls: list[_ToolCall]):
        return dump_ck_str_list(tool_calls)

    @field_validator("tool_calls", mode="before")
    def parse_tool_calls(cls, value: Any):
        return parse_ck_str_list(cls._ToolCall, value)

    # ---------------------------
    # Reasoning steps

    class _ReasoningStep(BaseModel):
        title: str | None = Field(alias="t", default=None)
        explaination: str | None = Field(alias="e", default=None)
        output: str | None = Field(alias="o", default=None)

        @classmethod
        def from_domain(cls, reasoning_step: InternalReasoningStep):
            return cls(
                t=reasoning_step.title or None,
                e=reasoning_step.explaination or None,
                o=reasoning_step.output or None,
            )

        def to_domain(self) -> InternalReasoningStep:
            return InternalReasoningStep(title=self.title, explaination=self.explaination, output=self.output)

    reasoning_steps: list[_ReasoningStep] | None = None

    @field_serializer("reasoning_steps")
    def serialize_reasoning_steps(self, reasoning_steps: list[_ReasoningStep]):
        return dump_ck_str_list(reasoning_steps)

    @field_validator("reasoning_steps", mode="before")
    def parse_reasoning_steps(cls, value: Any):
        return parse_ck_str_list(cls._ReasoningStep, value)

    # ---------------------------
    # LLM completions

    class _LLMCompletion(BaseModel):
        duration_seconds: RoundedFloat | None = None

        messages: list[dict[str, Any]]
        response: str | None = None

        tool_calls: list["ClickhouseRun._ToolCall"] | None = None

        provider: str
        model: str | None = None

        config_id: str | None = None
        preserve_credits: bool | None = None

        # Using aliases to limit the size of the generated json to a minium
        class _LLMUsage(BaseModel):
            prompt_token_count: RoundedFloat | None = Field(alias="pt", default=None)
            prompt_token_count_cached: RoundedFloat | None = Field(alias="ptcc", default=None)
            prompt_cost_usd: float | None = Field(alias="pc", default=None)
            prompt_audio_token_count: RoundedFloat | None = Field(alias="pat", default=None)
            prompt_audio_duration_seconds: RoundedFloat | None = Field(alias="pad", default=None)
            prompt_image_count: int | None = Field(alias="pic", default=None)
            completion_token_count: RoundedFloat | None = Field(alias="ct", default=None)
            completion_cost_usd: float | None = Field(alias="cc", default=None)
            reasoning_token_count: RoundedFloat | None = Field(alias="rt", default=None)
            context_window_size: int | None = Field(alias="mcws", default=None)

            @classmethod
            def from_domain(cls, usage: LLMUsage):
                return cls(
                    pt=usage.prompt_token_count or None,
                    ptcc=usage.prompt_token_count_cached or None,
                    pc=usage.prompt_cost_usd or None,
                    pat=usage.prompt_audio_token_count or None,
                    pad=usage.prompt_audio_duration_seconds or None,
                    pic=usage.prompt_image_count or None,
                    ct=usage.completion_token_count or None,
                    cc=usage.completion_cost_usd or None,
                    rt=usage.reasoning_token_count or None,
                    mcws=usage.model_context_window_size or None,
                )

            def to_domain(self) -> LLMUsage:
                return LLMUsage(
                    prompt_token_count=self.prompt_token_count,
                    prompt_token_count_cached=self.prompt_token_count_cached,
                    prompt_cost_usd=self.prompt_cost_usd,
                    prompt_audio_token_count=self.prompt_audio_token_count,
                    prompt_audio_duration_seconds=self.prompt_audio_duration_seconds,
                    prompt_image_count=self.prompt_image_count,
                    completion_token_count=self.completion_token_count,
                    completion_cost_usd=self.completion_cost_usd,
                    reasoning_token_count=self.reasoning_token_count,
                    model_context_window_size=self.context_window_size,
                )

        usage: _LLMUsage

        def to_domain(self) -> LLMCompletion:
            return LLMCompletion(
                duration_seconds=self.duration_seconds,
                messages=self.messages,
                response=self.response,
                tool_calls=safe_map_optional(self.tool_calls, ClickhouseRun._ToolCall.to_domain, logger=_logger),
                usage=self.usage.to_domain(),
                provider=Provider(self.provider),
                config_id=self.config_id,
                preserve_credits=self.preserve_credits,
                model=Model(self.model) if self.model else None,
            )

        @classmethod
        def from_domain(cls, llm_completion: LLMCompletion):
            return cls(
                duration_seconds=llm_completion.duration_seconds,
                messages=llm_completion.messages,
                response=llm_completion.response,
                tool_calls=safe_map_optional(
                    llm_completion.tool_calls,
                    ClickhouseRun._ToolCall.from_domain,
                    logger=_logger,
                ),
                usage=cls._LLMUsage.from_domain(llm_completion.usage),
                provider=llm_completion.provider.value,
                config_id=llm_completion.config_id,
                preserve_credits=llm_completion.preserve_credits,
                model=llm_completion.model,
            )

    llm_completions: list[_LLMCompletion] | None = None

    @field_validator("llm_completions", mode="before")
    def parse_llm_completions(cls, value: Any):
        return parse_ck_str_list(cls._LLMCompletion, value)

    @field_serializer("llm_completions")
    def serialize_llm_completions(self, llm_completions: list[_LLMCompletion]):
        return dump_ck_str_list(llm_completions)

    @classmethod
    def sanitize_id(cls, run_id: str, created_at: datetime) -> UUID:
        try:
            uuid = UUID(run_id)
        except ValueError:
            _logger.warning("Found a non uuid run id generating a new one", extra={"run_id": run_id})
            return uuid7(ms=lambda: int(created_at.timestamp() * 1000))

        if is_uuid7(uuid):
            return uuid
        return uuid7(ms=lambda: int(created_at.timestamp() * 1000), rand=lambda: uuid.int)

    @classmethod
    def compute_cache_hash(cls, tenant: int, task_id: int, version_id: str, input_hash: str) -> str:
        return compute_obj_hash(
            {"tenant_id": tenant, "task_id": task_id, "version_id": version_id, "input_hash": input_hash},
        )

    def split_tool_calls(self):
        if not self.tool_calls:
            return None, None
        without_result: list[ToolCallRequestWithID] = []
        with_result: list[ToolCall] = []
        for tool_call in self.tool_calls:
            d = tool_call.to_domain()
            if isinstance(d, ToolCall):
                with_result.append(d)
            else:
                without_result.append(d)
        return without_result or None, with_result or None

    @classmethod
    def from_domain(cls, tenant: int, run: AgentRun):
        return cls(
            # IDs
            tenant_uid=tenant,
            task_uid=run.task_uid,
            created_at_date=run.created_at.date(),
            run_uuid=cls.sanitize_id(run.id, run.created_at),
            conversation_id=cls.sanitize_id(run.conversation_id, run.created_at)
            if run.conversation_id
            else uuid7(ms=lambda: int(run.created_at.timestamp() * 1000)),
            task_schema_id=run.task_schema_id,
            # Version
            version_id=run.group.id,
            version_iteration=run.group.iteration,
            version_model=run.group.properties.model or "",
            version_temperature_percent=_temperature_percent(run.group.properties.temperature),
            # hashes
            input_hash=run.task_input_hash,
            output_hash=run.task_output_hash,
            eval_hash=run.eval_hash,
            cache_hash=cls.compute_cache_hash(
                tenant=tenant,
                task_id=run.task_uid,
                version_id=run.group.id,
                input_hash=run.task_input_hash,
            ),
            # Input output
            input_preview=run.task_input_preview,
            input=run.task_input,
            output_preview=run.task_output_preview,
            output=run.task_output,
            # Duration and cost
            duration_ds=_duration_ds(run.duration_seconds),
            overhead_ms=int(round(run.overhead_seconds * 1000)) if run.overhead_seconds else 0,
            cost_millionth_usd=_cost_millionth_usd(run.cost_usd),
            input_token_count=run.input_token_count or 0,
            output_token_count=run.output_token_count or 0,
            # Error
            error_payload=cls._Error.from_domain(run.error) if run.error else None,
            # Metadata
            metadata=_sanitize_metadata(run.metadata, provider=run.group.properties.provider),
            # Author
            author_uid=run.author_uid,
            # Active
            is_active=run.is_active or False,
            # Tool calls
            tool_calls=safe_map_optional(
                (*(run.tool_calls or []), *(run.tool_call_requests or [])),
                cls._ToolCall.from_domain,
                logger=_logger,
            ),
            # Reasoning steps
            reasoning_steps=safe_map_optional(run.reasoning_steps, cls._ReasoningStep.from_domain, logger=_logger),
            # LLM completions
            llm_completions=safe_map_optional(run.llm_completions, cls._LLMCompletion.from_domain, logger=_logger),
        )

    def to_domain(self, task_id: str) -> AgentRun:
        tool_call_requests, tool_calls = self.split_tool_calls()

        return AgentRun(
            # IDs
            task_id=task_id,
            task_uid=self.task_uid,
            conversation_id=str(self.conversation_id) if self.conversation_id else None,
            id=str(self.run_uuid),
            created_at=uuid7_generation_time(self.run_uuid),
            task_schema_id=self.task_schema_id,
            # Group
            group=self.task_group,
            # Hashes
            task_input_hash=self.input_hash,
            task_output_hash=self.output_hash,
            # Input output
            task_input=self.input,
            task_input_preview=self.input_preview,
            task_output=self.output,
            task_output_preview=self.output_preview,
            # Duration and cost
            duration_seconds=self.from_duration_ds(self.duration_ds) or None,
            overhead_seconds=self.overhead_ms / 1000 if self.overhead_ms else None,
            cost_usd=self.from_cost_millionth_usd(self.cost_millionth_usd),
            # Status
            status="success" if not self.error_payload else "failure",
            # Error
            error=self.error,
            # Metadata
            metadata=_from_sanitized_metadata(self.metadata),
            # Author
            author_uid=self.author_uid,
            # Active
            is_active=self.is_active,
            # Tool calls
            tool_calls=tool_calls,
            tool_call_requests=tool_call_requests,
            # Reasoning steps
            reasoning_steps=safe_map_optional(self.reasoning_steps, self._ReasoningStep.to_domain, logger=_logger),
            # LLM completions
            llm_completions=safe_map_optional(self.llm_completions, self._LLMCompletion.to_domain, logger=_logger),
            eval_hash=self.eval_hash,
        )

    @classmethod
    def _metadata_clause(cls, operation: SearchOperation):
        if not isinstance(operation, SearchOperationSingle):
            raise BadRequestError("invalid search operation for metadata")
        if not isinstance(operation.value, str):
            raise BadRequestError("invalid search operation for metadata", capture=True)
        return W("metadata", operator="LIKE", value=f"%{operation.value}%")

    @classmethod
    def _version_clause(cls, operation: SearchOperation):
        if not isinstance(operation, SearchOperationSingle):
            raise BadRequestError("invalid search operation for version", capture=True)
        match operation.operator:
            case SearchOperator.IS:
                op = "="
            case SearchOperator.IS_NOT:
                op = "!="
            case _:
                raise BadRequestError(f"invalid search operator for version: {operation.operator}", capture=True)

        if isinstance(operation.value, VersionEnvironment):
            return W("metadata['workflowai.deployment.env']", operator=op, value=operation.value.value)
        if not isinstance(operation.value, str):
            raise BadRequestError("invalid search value type for version", capture=True)
        return W("version_id", operator=op, value=operation.value)

    @classmethod
    def _time_clause(cls, operation: SearchOperation):  # noqa: C901
        if isinstance(operation, SearchOperationSingle):
            if not isinstance(operation.value, datetime):
                raise BadRequestError("invalid search operation for time", capture=True)

            if operation.is_less_op:
                compared_id = id_upper_bound(operation.value)
                # TODO: should we consider strict equals ?
                op = "<="
            elif operation.is_greater_op:
                compared_id = id_lower_bound(operation.value)
                op = ">="
            else:
                compared_id = None
                op = "="

            w = W("created_at_date", operator=op, value=operation.value.date(), type="Date")
            if compared_id:
                w &= W("run_uuid", operator=op, value=compared_id, type="UInt128")
            return w

        v1, v2 = operation.value
        if not isinstance(v1, datetime) or not isinstance(v2, datetime):
            raise BadRequestError("invalid search operation for time", capture=True)
        if not v1 < v2:
            raise BadRequestError("Second time must be greater than first time")
        if operation.operator == SearchOperator.IS_BETWEEN:
            op = "BETWEEN"
            i1 = id_lower_bound(v1)
            i2 = id_upper_bound(v2)
        elif operation.operator == SearchOperator.IS_NOT_BETWEEN:
            op = "NOT BETWEEN"
            i1 = id_upper_bound(v1)
            i2 = id_lower_bound(v2)
        else:
            raise BadRequestError("invalid search operator for time", capture=True)

        return W("created_at_date", (v1.date(), v2.date()), operator=op) & W(
            "run_uuid",
            (i1, i2),
            operator=op,
        )

    @classmethod
    def _status_clause(cls, operation: SearchOperation):
        if operation.operator != SearchOperator.IS:
            raise BadRequestError(f"invalid search operation '{operation.operator}' for status")

        try:
            value = StatusSearchOptions(operation.value)
        except ValueError:
            raise BadRequestError(f"invalid search value {operation.value} for status")

        if value == StatusSearchOptions.SUCCESS:
            return W("error_payload", operator=W.EMPTY, type="String")

        return W("error_payload", operator=W.NOT_EMPTY, type="String")

    @classmethod
    def to_clause(cls, query: SearchQuery) -> W:  # noqa: C901
        if f := _FIELD_TO_QUERY.get(query.field):
            return clickhouse_query(f[0], query.operation, type=f[1], map_fn=f[2])
        match query.field:
            case SearchField.VERSION:
                return cls._version_clause(query.operation)
            case SearchField.TIME:
                return cls._time_clause(query.operation)
            case SearchField.STATUS:
                return cls._status_clause(query.operation)
            case SearchField.EVAL_HASH:
                return W("eval_hash", operator="=", value=query.operation.value, type="String")
            case SearchField.METADATA:
                # Making sure the keypath resembles a keypath
                # to avoid any weird injection
                query.validate_keypath()
                return clickhouse_query(
                    f"metadata['{query.key_path}']",
                    op=query.operation,
                    type="String",
                )
            case SearchField.INPUT | SearchField.OUTPUT:
                field = "input" if query.field == SearchField.INPUT else "output"
                if isinstance(query, SearchQueryNested):
                    query.validate_keypath()
                    return json_query(query.field_type, field, query.key_path, query.operation)
                return clickhouse_query(field, query.operation, type="String")

            case _:
                raise InternalError("Unsupported query", extras={"query": safe_dump_pydantic_model(query)})

    @classmethod
    def heavy_fields(cls):
        return {
            "tool_calls",
            "llm_completions",
        }

    @classmethod
    def columns(
        cls,
        include: set[SerializableTaskRunField] | None = None,
        exclude: set[SerializableTaskRunField] | None = None,
    ):
        if include:
            return [FIELD_TO_COLUMN[f] for f in include if f in FIELD_TO_COLUMN]
        if not exclude:
            return ["*"]
        exc = {FIELD_TO_COLUMN[f] for f in exclude if f in FIELD_TO_COLUMN}
        return [f for f in cls.model_fields.keys() if f not in exc]

    @classmethod
    def select_in_search(
        cls,
        include: set[SerializableTaskRunField] | None = None,
        exclude: set[SerializableTaskRunField] | None = None,
    ) -> list[str]:
        if include:
            return [FIELD_TO_COLUMN[f] for f in include if f in FIELD_TO_COLUMN]
        # A sublist of fields that should be included in search
        if exclude:
            exclude_fields: set[str] = {FIELD_TO_COLUMN[f] for f in exclude if f in FIELD_TO_COLUMN}
        else:
            exclude_fields: set[str] = {
                "input",
                "output",
                "metadata",
                "tool_calls",
                *cls.heavy_fields(),
            }
        return [f for f in cls.model_fields.keys() if f not in exclude_fields]

    @classmethod
    def select_not_heavy(cls):
        return [f for f in cls.model_fields.keys() if f not in cls.heavy_fields()]

    @classmethod
    def where_by_id(cls, task_uid: int, id: str):
        try:
            run_uuid = UUID(id)
        except ValueError:
            raise ObjectNotFoundException("Run did not have a valid UUID")

        if not is_uuid7(run_uuid):
            raise ObjectNotFoundException("Run did not have a valid UUID7")

        created_at_date = uuid7_generation_time(run_uuid)

        return (
            W("task_uid", type="UInt32", value=task_uid)
            & W("created_at_date", type="Date", value=created_at_date.date().isoformat())
            & W("run_uuid", type="UInt128", value=run_uuid.int)
        )

    @classmethod
    def where_for_query(cls, tenant: int, task_uid: int | None, query: SerializableTaskRunQuery):  # noqa: C901
        w = W("tenant_uid", type="UInt32", value=tenant)
        if task_uid:
            w &= W("task_uid", type="UInt32", value=task_uid)
            if (
                query.task_schema_id
                and query.task_input_hashes
                and len(query.task_input_hashes) == 1
                and query.task_output_hash
            ):
                eval_hash = compute_eval_hash(
                    schema_id=query.task_schema_id,
                    input_hash=next(iter(query.task_input_hashes)),
                    output_hash=query.task_output_hash,
                )
                w &= W("eval_hash", type="String", value=eval_hash)

            if (
                query.task_schema_id
                and query.task_input_hashes
                and len(query.task_input_hashes) == 1
                and query.group_ids
                and len(query.group_ids) == 1
            ):
                cache_hash = cls.compute_cache_hash(
                    tenant,
                    task_uid,
                    next(iter(query.group_ids)),
                    next(iter(query.task_input_hashes)),
                )
                w &= W("cache_hash", type="String", value=cache_hash)

        if query.status:
            if len(query.status) == 1:
                only_success = next(iter(query.status)) == "success"
                if only_success:
                    w &= W("error_payload", type="String", value="") & W(
                        "output",
                        type="String",
                        value="",
                        operator="!=",
                    )
                else:
                    w &= W("error_payload", operator="!=", value="", type="String")

        if query.task_schema_id:
            w &= W("task_schema_id", type="UInt16", value=query.task_schema_id)

        if query.task_input_hashes:
            w &= W("input_hash", type="String", value=query.task_input_hashes)

        if query.task_output_hash:
            w &= W("output_hash", type="String", value=query.task_output_hash)

        if query.group_ids:
            w &= W("version_id", type="String", value=query.group_ids)

        if query.is_active is not None:
            w &= W("is_active", type="Boolean", value=query.is_active)

        if query.created_after:
            w &= W("created_at_date", operator=">=", type="Date", value=query.created_after.date())

        if query.created_before:
            w &= W("created_at_date", operator="<=", type="Date", value=query.created_before.date())

        if query.metadata:
            for key, value in query.metadata.items():
                w &= W(f"metadata['{key}']", operator="=", type="String", value=value)

        return w
