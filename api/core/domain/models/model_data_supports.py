from pydantic import BaseModel, Field


class ModelDataIOSupports(BaseModel):
    supports_input_image: bool = Field(description="Whether the model supports input images")
    supports_input_pdf: bool = Field(description="Whether the model supports input pdfs")
    supports_input_audio: bool = Field(description="Whether the model supports input audio")
    supports_output_image: bool = Field(default=False, description="Whether the model supports output images")
    supports_output_text: bool = Field(default=True, description="Whether the model supports output text")

    def missing_io_supports(self, compared_to: "ModelDataIOSupports", exclude: set[str] | None = None):
        """Compares the current supports with the other supports and returns that the other
        supports that are not in the current supports"""
        fields = set(ModelDataIOSupports.model_fields)
        if exclude:
            fields = fields - exclude
        this_dumped = self.model_dump(include=fields)
        other_dumped = compared_to.model_dump(include=fields)

        return {f for f in fields if bool(other_dumped.get(f) and not this_dumped.get(f))}


class ModelDataSupports(ModelDataIOSupports):
    supports_json_mode: bool = Field(description="Whether the model supports JSON mode")
    supports_input_image: bool = Field(description="Whether the model supports input images")
    supports_input_pdf: bool = Field(description="Whether the model supports input pdfs")
    supports_input_audio: bool = Field(description="Whether the model supports input audio")
    # TODO: we should probably remove and only use support output text
    supports_audio_only: bool = Field(
        default=False,
        description="Whether the model supports audio only",
    )
    support_system_messages: bool = Field(default=True, description="Whether the model supports system messages")
    supports_structured_output: bool = Field(default=False, description="Whether the model supports structured output")
    support_input_schema: bool = Field(default=True, description="Whether the model supports input schema")
    supports_parallel_tool_calls: bool = Field(
        default=True,
        description="Whether the model supports parallel tool calls",
    )
    supports_tool_calling: bool = Field(
        description="Whether the model supports tool calling",
    )
    supports_reasoning: bool = Field(
        default=False,
        description="Whether the model supports reasoning mode with step-by-step reasoning content",
    )
