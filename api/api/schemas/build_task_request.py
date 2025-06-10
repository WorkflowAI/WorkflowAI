from typing import Any

from pydantic import BaseModel, Field

from core.agents.chat_task_schema_generation.chat_task_schema_generation_task import AgentSchemaJson


class AgentSchema(BaseModel):
    # Only use in the API for back-compatability with the frontend.

    task_name: str = Field(description="The name of the task in Title Case", serialization_alias="task_name")
    input_json_schema: dict[str, Any] | None = Field(
        default=None,
        description="The JSON schema of the task input",
    )
    output_json_schema: dict[str, Any] | None = Field(
        default=None,
        description="The JSON schema of the agent output",
    )

    @classmethod
    def from_agent_schema(cls, agent_schema: AgentSchemaJson) -> "AgentSchema":
        return cls(
            task_name=agent_schema.agent_name,
            input_json_schema=agent_schema.input_json_schema,
            output_json_schema=agent_schema.output_json_schema,
        )

    def to_agent_schema(self) -> AgentSchemaJson:
        return AgentSchemaJson(
            agent_name=self.task_name,
            input_json_schema=self.input_json_schema,
            output_json_schema=self.output_json_schema,
        )


class BuildAgentIteration(BaseModel):
    user_message: str
    assistant_answer: str

    class AgentSchema(BaseModel):
        # Only use in the API for back-compatability with the frontend.

        task_name: str = Field(description="The name of the task in Title Case", serialization_alias="task_name")
        input_json_schema: dict[str, Any] | None = Field(
            default=None,
            description="The JSON schema of the task input",
        )
        output_json_schema: dict[str, Any] | None = Field(
            default=None,
            description="The JSON schema of the agent output",
        )

        @classmethod
        def from_agent_schema(cls, agent_schema: AgentSchemaJson) -> "BuildAgentIteration.AgentSchema":
            return cls(
                task_name=agent_schema.agent_name,
                input_json_schema=agent_schema.input_json_schema,
                output_json_schema=agent_schema.output_json_schema,
            )

        def to_agent_schema(self) -> AgentSchemaJson:
            return AgentSchemaJson(
                agent_name=self.task_name,
                input_json_schema=self.input_json_schema,
                output_json_schema=self.output_json_schema,
            )

    task_schema: AgentSchema | None = Field(
        default=None,
        description="The task schema of the task generated in this iteration",
    )


class BuildAgentRequest(BaseModel):
    previous_iterations: list[BuildAgentIteration] | None = Field(
        default=None,
        description="The previous iteration of the task building process, as returned by the API",
    )

    user_message: str
    stream: bool = Field(default=False, description="Whether to stream the task building process")
    is_proxy_agent: bool = Field(default=False, description="Whether the agent is a proxy agent")
