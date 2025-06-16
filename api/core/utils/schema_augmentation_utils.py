import logging
from typing import Any

from pydantic import BaseModel, Field

from core.domain.agent_run_result import INTERNAL_AGENT_RUN_RESULT_SCHEMA_KEY, AgentRunResult
from core.domain.fields.internal_reasoning_steps import InternalReasoningStep
from core.domain.reasoning_step import INTERNAL_REASONING_STEPS_SCHEMA_KEY
from core.utils.schema_sanitation import (
    clean_pydantic_schema,
)

logger = logging.getLogger(__name__)


def _add_schema_to_output_schema(
    output_schema: dict[str, Any],
    schema_to_add: dict[str, Any],
    property_name: str,
) -> None:
    if "properties" not in output_schema:
        if output_schema.get("type") != "object":
            # In case the output schema is not an "object" (ex: is an array), we do not use the feature
            logger.exception(
                "Output schema has no properties, skipping schema addition",
                extra={"output_schema": output_schema},
            )
            return
        output_schema["properties"] = {}

    if property_name in output_schema["properties"]:
        # TODO: there is currently a bug that tries to add the same property twice when tools are used.
        # Warning is commented to avoid spam.
        # When it's fixed we can uncomment the following logger.warning.
        # Very unlikely to happen, but we need to handle this case.
        # logger.warning(
        #     "Property already in output schema, skipping",
        #     extra={"property_name": property_name},
        # )
        return

    # Merge JSON schemas
    if "$defs" in schema_to_add:
        if "$defs" in output_schema:
            if any(name in output_schema["$defs"] for name in schema_to_add["$defs"]):
                logger.warning(
                    "Def already in output schema $defs, skipping",
                    extra={"def_name": schema_to_add["$defs"]},
                )
                return
            output_schema["$defs"].update(schema_to_add["$defs"])
        else:
            output_schema["$defs"] = schema_to_add["$defs"]

    output_schema["properties"] = {**schema_to_add["properties"], **output_schema["properties"]}


def _build_reasoning_steps_schema() -> dict[str, Any]:
    class InternalReasoningSteps(BaseModel):
        internal_reasoning_steps: list[InternalReasoningStep] | None = Field(
            default=None,
            description="An array of reasoning steps",
        )

    return clean_pydantic_schema(InternalReasoningSteps)


_REASONING_STEPS_SCHEMA = _build_reasoning_steps_schema()


def add_reasoning_steps_to_schema(output_schema: dict[str, Any]) -> None:
    _add_schema_to_output_schema(
        output_schema=output_schema,
        schema_to_add=_REASONING_STEPS_SCHEMA,
        property_name=INTERNAL_REASONING_STEPS_SCHEMA_KEY,
    )


def _build_agent_run_result_schema() -> dict[str, Any]:
    class AgentRunResultWrapper(BaseModel):
        internal_agent_run_result: AgentRunResult | None = Field(
            default=None,
            description="The status of the agent run, needs to be filled whether the run was successful or not",
        )

    return clean_pydantic_schema(AgentRunResultWrapper)


_AGENT_RUN_RESULT_SCHEMA = _build_agent_run_result_schema()


def add_agent_run_result_to_schema(output_schema: dict[str, Any]) -> None:
    _add_schema_to_output_schema(
        output_schema=output_schema,
        schema_to_add=_AGENT_RUN_RESULT_SCHEMA,
        property_name=INTERNAL_AGENT_RUN_RESULT_SCHEMA_KEY,
    )
