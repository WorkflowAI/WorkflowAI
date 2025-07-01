import json
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field, model_validator

from core.utils.hash import compute_obj_hash
from core.utils.iter_utils import safe_map
from core.utils.models.previews import compute_preview


class ToolCallRequest(BaseModel):
    tool_name: str = Field(
        description="The name of the tool called",
        examples=["WeatherCheckTask", "ReplyToUserTask"],
    )

    tool_input_dict: dict[str, Any] = Field(
        description="The input of the tool call",
        examples=[
            {  # Example of a WeatherCheckTask input
                "location": {"latitude": 48.8566, "longitude": 2.3522},
                "date": "2021-09-01",
            },
            {  # Example of a ReplyToUserTask inpu
                "content": "Glad I could help!",
            },
        ],
    )

    def with_result(self, result: Any) -> "ToolCall":
        return ToolCall(**self.model_dump(), result=result, error=None)

    def with_error(self, error: str) -> "ToolCall":
        return ToolCall(**self.model_dump(), error=error, result=None)

    @property
    def input_preview(self):
        return compute_preview(self.tool_input_dict)

    @property
    def preview(self):
        input_dict_preview = [f"{k}: {compute_preview(v, max_len=30)}" for k, v in self.tool_input_dict.items()]
        return f"{self.tool_name}({', '.join(input_dict_preview)})"


class ToolCallRequestWithID(ToolCallRequest):
    id: str = Field(default="", description="The id of the tool call")
    # TODO: make index a required field
    index: int = Field(default=0, description="The index of the tool call")

    @classmethod
    def default_id(cls, tool_name: str, input_dict: dict[str, Any]) -> str:
        return f"{tool_name}_{compute_obj_hash(input_dict)}"

    @model_validator(mode="after")
    def post_validate(self):
        if not self.id:
            self.id = self.default_id(self.tool_name, self.tool_input_dict)
        return self

    def add_output(self, output: "ToolCallOutput"):
        return ToolCall(**self.model_dump(), result=output.output, error=output.error)

    def __str__(self) -> str:
        elements = [
            "<tool_call>",
            f"<id>{self.id}</id>",
            f"<name>{self.tool_name}</name>",
            f"<input>{json.dumps(self.tool_input_dict)}</input>",
        ]
        elements.append("</tool_call>")
        return "\n".join(elements)

    def __hash__(self) -> int:
        # Transform the tool_input_dict into a string to make it hashable
        return hash((self.id, self.tool_name, json.dumps(self.tool_input_dict)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ToolCallRequestWithID):
            return NotImplemented
        return (
            self.id == other.id and self.tool_name == other.tool_name and self.tool_input_dict == other.tool_input_dict
        )


class ToolCall(ToolCallRequestWithID):
    """A finalized tool call, that contains the result or the error of the tool call as well as the name and input"""

    result: Any = Field(default=None, description="The result of the tool call")
    error: str | None = Field(default=None, description="The error that occurred during the tool call if any")

    def __str__(self) -> str:
        elements = [
            "<tool_result>",
            f"<id>{self.id}</id>",
            f"<name>{self.tool_name}</name>",
            f"<input>{json.dumps(self.tool_input_dict)}</input>",
        ]
        if self.error is not None:
            elements.append(f"<error>{self.error}</error>")
        else:
            elements.append(f"<output>{json.dumps(self.result)}</output>")
        elements.append("</tool_result>")
        return "\n".join(elements)

    @property
    def output_preview(self):
        if self.error is not None:
            return f"Error: {self.error}"
        return compute_preview(self.result)

    @staticmethod
    def combine(tool_calls: Iterable["ToolCallRequestWithID"], outputs: Iterable["ToolCallOutput"]):
        tool_calls_dict = {t.id: t for t in tool_calls}
        return safe_map(outputs, lambda output: tool_calls_dict[output.id].add_output(output))

    def stringified_result(self):
        if self.error is not None:
            return f"Error: {self.error}"
        return str(self.result)


class ToolCallOutput(BaseModel):
    id: str
    output: Any | None = None
    error: str | None = None
