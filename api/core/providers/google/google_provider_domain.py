import asyncio
import base64
import logging
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, ValidationError

from core.domain.errors import InvalidFileError, InvalidRunOptionsError
from core.domain.fields.file import File
from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.domain.models import Model
from core.domain.task_group_properties import ToolChoice
from core.domain.tool import Tool
from core.domain.tool_call import ToolCall, ToolCallRequestWithID
from core.providers.base.models import (
    AudioContentDict,
    DocumentContentDict,
    ImageContentDict,
    StandardMessage,
    TextContentDict,
    ToolCallRequestDict,
    ToolCallResultDict,
    role_domain_to_standard,
)
from core.tools import ToolKind
from core.utils.audio import audio_duration_seconds
from core.utils.dicts import TwoWayDict
from core.utils.json_utils import safe_extract_dict_from_json
from core.utils.schemas import JsonSchema
from core.utils.token_utils import tokens_from_string

logger = logging.getLogger(__name__)

GoogleRole = Literal["user", "model"]

GOOGLE_CHARS_PER_TOKEN = 4


PER_TOKEN_MODELS = [Model.LLAMA_3_2_90B, Model.LLAMA_3_1_405B]


MESSAGE_ROLE_X_ROLE_MAP = TwoWayDict[MessageDeprecated.Role, GoogleRole](
    (MessageDeprecated.Role.SYSTEM, "model"),
    (MessageDeprecated.Role.USER, "user"),
    # Reverse mapping will yield assistant for model
    (MessageDeprecated.Role.ASSISTANT, "model"),
)


def internal_tool_name_to_native_tool_call(tool_name: str) -> str:
    return tool_name.replace("@", "")


def native_tool_name_to_internal(tool_name: str) -> str:
    if f"@{tool_name}" in ToolKind.__members__.values():
        return f"@{tool_name}"
    return tool_name


class Blob(BaseModel):
    mimeType: str
    data: str

    def to_url(self) -> str:
        return f"data:{self.mimeType};base64,{self.data}"

    @classmethod
    def from_domain(cls, file: File):
        if not file.content_type:
            raise InvalidFileError("Content type is required", capture=True)
        # data should have been validated here
        return cls(
            mimeType=file.content_type,
            data=file.data or "",
        )


# https://cloud.google.com/vertex-ai/docs/reference/rest/v1/projects.locations.tuningJobs#FileData
class FileData(BaseModel):
    mimeType: str
    fileUri: str

    def to_url(self) -> str:
        return self.fileUri

    @classmethod
    def from_domain(cls, file: File):
        if not file.content_type or not file.url:
            raise InvalidFileError("Content type and url are required", capture=True)
        return cls(
            mimeType=file.content_type,
            fileUri=file.url,
        )


# https://cloud.google.com/vertex-ai/docs/reference/rest/v1/projects.locations.tuningJobs#Part
# https://ai.google.dev/api/caching#Part
class Part(BaseModel):
    text: str | None = None

    inlineData: Blob | None = None

    fileData: FileData | None = None

    thought: bool | None = None

    class FunctionCall(BaseModel):
        # TODO: understand why the id is not accepted
        # id: str | None = None, for some reason, the Google API doesn't accept an id for the function call.
        # {
        #     "field": "contents[1].parts[1].function_call",
        #     "description": "Invalid JSON payload received. Unknown name \"id\" at 'contents[1].parts[1].function_call': Cannot find field."
        #  }
        name: str
        args: dict[str, Any] | None = None

    functionCall: FunctionCall | None = None

    class FunctionResponse(BaseModel):
        # TODO: understand why the id is not accepted
        # id: str
        # {
        #     "field": "contents[2].parts[1].function_response",
        #     "description": "Invalid JSON payload received. Unknown name \"id\" at 'contents[2].parts[1].function_response': Cannot find field."
        #  }
        name: str
        response: dict[str, Any]

    functionResponse: FunctionResponse | None = None

    def to_standard(
        self,
    ) -> list[TextContentDict | ImageContentDict | AudioContentDict | ToolCallRequestDict | ToolCallResultDict]:
        output: list[
            TextContentDict | ImageContentDict | AudioContentDict | ToolCallRequestDict | ToolCallResultDict
        ] = []

        if self.text:
            output.append({"type": "text", "text": self.text})

        def append_data_part(part: Blob | FileData | None):
            if not part:
                return
            if part.mimeType.startswith("image/") or part.mimeType == "application/pdf":
                output.append({"type": "image_url", "image_url": {"url": part.to_url()}})
            elif part.mimeType.startswith("audio/"):
                output.append({"type": "audio_url", "audio_url": {"url": part.to_url()}})

        append_data_part(self.inlineData)
        append_data_part(self.fileData)

        if self.functionCall:
            output.append(
                ToolCallRequestDict(
                    type="tool_call_request",
                    id=None,
                    tool_name=native_tool_name_to_internal(self.functionCall.name),
                    tool_input_dict=self.functionCall.args or {},
                ),
            )

        if self.functionResponse:
            output.append(
                ToolCallResultDict(
                    type="tool_call_result",
                    id=None,
                    tool_name=native_tool_name_to_internal(self.functionResponse.name),
                    tool_input_dict=None,
                    result=self.functionResponse.response,
                    error=None,
                ),
            )
        return output

    @property
    def has_audio(self) -> bool:
        if not self.inlineData:
            return False
        return self.inlineData.mimeType.startswith("audio/")

    async def audio_duration_seconds(self) -> float:
        if not self.inlineData or not self.has_audio:
            return 0.0
        bs = base64.b64decode(self.inlineData.data)
        return await audio_duration_seconds(bs, self.inlineData.mimeType)

    @classmethod
    def from_str(cls, text: str):
        return cls(text=text)

    @classmethod
    def from_file(cls, file: File):
        if file.data:
            return cls(inlineData=Blob.from_domain(file))
        return cls(fileData=FileData.from_domain(file))

    @classmethod
    def from_tool_call_request(cls, tool_call_request: ToolCallRequestWithID):
        return cls(
            functionCall=Part.FunctionCall(
                name=internal_tool_name_to_native_tool_call(tool_call_request.tool_name),
                args=tool_call_request.tool_input_dict,
            ),
        )

    @classmethod
    def from_tool_call_result(cls, tool_call_result: ToolCall):
        try:
            result_dict = safe_extract_dict_from_json(tool_call_result.result)
            if result_dict is None:
                raise ValueError("Can't parse dictionary from result")
            return cls(
                functionResponse=Part.FunctionResponse(
                    name=internal_tool_name_to_native_tool_call(tool_call_result.tool_name),
                    response=result_dict,
                ),
            )
        except Exception:
            return cls(
                functionResponse=Part.FunctionResponse(
                    name=internal_tool_name_to_native_tool_call(tool_call_result.tool_name),
                    response={"result": str(tool_call_result.result)},
                ),
            )


# https://cloud.google.com/vertex-ai/docs/reference/rest/v1/projects.locations.tuningJobs#Content
class Content(BaseModel):
    role: Literal["user", "model"] | None = None

    parts: list[Part] = Field(default_factory=list)


class GoogleMessage(BaseModel):
    role: Literal["user", "model"]

    parts: list[Part]

    @classmethod
    def from_domain(cls, message: MessageDeprecated) -> Self:
        output_message = cls(
            parts=[],
            role=MESSAGE_ROLE_X_ROLE_MAP[message.role],
        )

        add_text_part = True

        # Google breaks if the message does not contain a text part
        if message.content:
            output_message.parts.append(Part.from_str(message.content))
            add_text_part = False

        for file in message.files or []:
            output_message.parts.append(Part.from_file(file))

        if message.tool_call_requests:
            add_text_part = False
            output_message.parts.extend(
                [Part.from_tool_call_request(tool_call_request) for tool_call_request in message.tool_call_requests],
            )

        if message.tool_call_results:
            add_text_part = False
            output_message.parts.extend(
                [Part.from_tool_call_result(tool_call_result) for tool_call_result in message.tool_call_results],
            )

        if add_text_part:
            output_message.parts.insert(0, Part.from_str("-"))

        return output_message

    def text_token_count(self, model: Model) -> int:
        token_count = 0

        for part in self.parts:
            if part.text:
                token_count += tokens_from_string(part.text, model)

        return token_count

    def text_char_count(self) -> int:
        char_count = 0

        for part in self.parts:
            if part.text:
                # Google VertexAI per char pricing ignore white spaces
                # https://cloud.google.com/vertex-ai/generative-ai/pricing
                char_count += len(part.text.replace(" ", ""))

        return char_count

    def image_count(self) -> int:
        image_count = 0

        for part in self.parts:
            if part.inlineData and part.inlineData.mimeType.startswith("image/"):
                image_count += 1

        return image_count

    def file_count(self) -> int:
        file_count = 0
        for part in self.parts:
            if part.inlineData:
                file_count += 1
        return file_count

    async def audio_duration_seconds(self) -> float:
        # System messages cannot contain audio
        coroutines = [part.audio_duration_seconds() for part in self.parts if part.has_audio]
        durations = await asyncio.gather(*coroutines)
        return sum(durations)

    def to_standard(self) -> StandardMessage:
        content: list[
            TextContentDict
            | ImageContentDict
            | AudioContentDict
            | DocumentContentDict
            | ToolCallRequestDict
            | ToolCallResultDict
        ] = []
        for p in self.parts:
            content.extend(p.to_standard())

        try:
            role = MESSAGE_ROLE_X_ROLE_MAP.backward(self.role)
        except KeyError:
            logger.exception("Invalid role", extra={"role": self.role})
            role = MessageDeprecated.Role.USER

        if len(content) == 1 and content[0]["type"] == "text":
            return {"role": role_domain_to_standard(role), "content": content[0]["text"]}

        return {"role": role_domain_to_standard(role), "content": content}


class GoogleSystemMessage(BaseModel):
    class Part(BaseModel):
        text: str

    parts: list[Part]

    @classmethod
    def from_domain(cls, message: MessageDeprecated) -> Self:
        # TODO: Is this correct?
        if message.files:
            raise InvalidRunOptionsError("System messages cannot contain files")

        return cls(
            parts=[
                cls.Part(text=message.content),
            ],
        )

    def text_token_count(self, model: Model) -> int:
        token_count = 0

        for part in self.parts:
            if part.text:
                token_count += tokens_from_string(part.text, model)
        return token_count

    def text_char_count(self) -> int:
        char_count = 0

        for part in self.parts:
            if part.text:
                # Google VertexAI per char pricing ignore white spaces
                # https://cloud.google.com/vertex-ai/generative-ai/pricing
                char_count += len(part.text.replace(" ", ""))

        return char_count

    def image_count(self) -> int:
        return 0  # System messages cannot contain images

    def file_count(self) -> int:
        # TODO: check
        return 0

    async def audio_duration_seconds(self) -> float:
        # System messages cannot contain audio
        return 0.0

    def to_standard(self) -> StandardMessage:
        text = "\n\n".join([part.text for part in self.parts])
        return {"role": "system", "content": text}

    @property
    def has_audio(self) -> bool:
        return False


def message_or_system_message(message: dict[str, Any]) -> GoogleMessage | GoogleSystemMessage:
    try:
        return GoogleMessage.model_validate(message)
    except ValidationError:
        return GoogleSystemMessage.model_validate(message)


BLOCK_THRESHOLD = Literal["BLOCK_LOW_AND_ABOVE", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_ONLY_HIGH", "BLOCK_NONE"]


class HarmCategory(StrEnum):
    HATE_SPEECH = "HARM_CATEGORY_HATE_SPEECH"
    DANGEROUS_CONTENT = "HARM_CATEGORY_DANGEROUS_CONTENT"
    HARASSMENT = "HARM_CATEGORY_HARASSMENT"
    SEXUALLY_EXPLICIT = "HARM_CATEGORY_SEXUALLY_EXPLICIT"


class Schema(BaseModel):
    type: Literal["TYPE_UNSPECIFIED", "STRING", "NUMBER", "INTEGER", "BOOLEAN", "OBJECT", "ARRAY"]
    format: str | None = None
    description: str | None = None
    nullable: bool | None = None
    enum: list[str] | None = None
    maxItems: str | None = None
    minItems: str | None = None
    properties: dict[str, Self] | None = None
    required: list[str] | None = None
    propertyOrdering: list[str] | None = None
    items: Self | None = None

    @classmethod
    def from_json_schema(cls, schema: JsonSchema) -> Self:  # noqa: C901
        from typing import Any, Literal, cast

        # Map JSON schema types to Schema types
        type_mapping: dict[str, str] = {
            "string": "STRING",
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "object": "OBJECT",
            "array": "ARRAY",
            "null": "TYPE_UNSPECIFIED",
            "array_length": "INTEGER",
            "date": "STRING",
        }

        # Convert the schema's internal representation to a plain dict
        raw: dict[str, Any] = dict(schema.schema)
        json_type: str | None = schema.type
        mapped_type: str = (
            type_mapping.get(json_type, "TYPE_UNSPECIFIED") if json_type is not None else "TYPE_UNSPECIFIED"
        )

        # Handle tool that have no argmument
        if mapped_type == "TYPE_UNSPECIFIED":
            return cls(
                type="OBJECT",
                format=None,
                description=None,
                nullable=False,
                enum=None,
                maxItems=None,
                minItems=None,
                properties={},
                required=[],
                propertyOrdering=None,
                items=None,
            )

        schema_format: str | None = schema.format

        # Use description if available, otherwise fallback to title
        description_tmp = raw.get("description") or raw.get("title")
        description: str | None = description_tmp if isinstance(description_tmp, str) else None

        # Process enum if present
        enum_raw = raw.get("enum")
        enum_list: list[str] | None = None
        if isinstance(enum_raw, list):
            enum_list = [str(x) for x in cast(list[Any], enum_raw)]

        properties: dict[str, Self] | None = None
        required: list[str] | None = None
        items_schema: Self | None = None
        minItems: str | None = None
        maxItems: str | None = None
        propertyOrdering: list[str] | None = None
        prop_ord = raw.get("propertyOrdering")
        if isinstance(prop_ord, list):
            propertyOrdering = [str(x) for x in cast(list[Any], prop_ord)]

        if mapped_type == "OBJECT":
            props = raw.get("properties")
            if isinstance(props, dict):
                properties = {}
                for prop_name, prop_schema in cast(dict[str, Any], props).items():
                    if isinstance(prop_schema, dict):
                        child_json_schema = JsonSchema(cast(dict[str, Any], prop_schema), defs=schema.defs)
                        properties[prop_name] = cls.from_json_schema(child_json_schema)
            req = raw.get("required")
            if isinstance(req, list):
                required = [str(x) for x in cast(list[Any], req)]
        elif mapped_type == "ARRAY":
            items: Any = raw.get("items")
            if isinstance(items, list):
                if items:
                    items = items[0]  # take first element if list provided
            if isinstance(items, dict):
                child_json_schema = JsonSchema(cast(dict[str, Any], items), defs=schema.defs)
                items_schema = cls.from_json_schema(child_json_schema)
            if "minItems" in raw:
                minItemVal = raw.get("minItems")
                if isinstance(minItemVal, (int, float, str)):
                    minItems = str(minItemVal)
            if "maxItems" in raw:
                maxItemVal = raw.get("maxItems")
                if isinstance(maxItemVal, (int, float, str)):
                    maxItems = str(maxItemVal)

        typed_mapped_type: Literal["TYPE_UNSPECIFIED", "STRING", "NUMBER", "INTEGER", "BOOLEAN", "OBJECT", "ARRAY"] = (
            mapped_type
            if mapped_type in ("TYPE_UNSPECIFIED", "STRING", "NUMBER", "INTEGER", "BOOLEAN", "OBJECT", "ARRAY")
            else "TYPE_UNSPECIFIED"
        )

        return cls(
            type=typed_mapped_type,
            format=schema_format,
            description=description,
            nullable=schema.is_nullable,
            enum=enum_list,
            properties=cast(dict[str, Schema], properties) if properties is not None else None,
            required=required,
            propertyOrdering=propertyOrdering,
            items=items_schema,
            minItems=minItems,
            maxItems=maxItems,
        )


# https://ai.google.dev/api/generate-content#method:-models.generatecontent
# https://cloud.google.com/vertex-ai/docs/reference/rest/v1/projects.locations.publishers.models/generateContent
class CompletionRequest(BaseModel):
    contents: list[GoogleMessage] | None
    systemInstruction: GoogleSystemMessage | None

    class Tool(BaseModel):
        # https://cloud.google.com/vertex-ai/docs/reference/rest/v1/projects.locations.cachedContents#FunctionDeclaration
        class FunctionDeclaration(BaseModel):
            name: str
            description: str
            parameters: Schema | None = None
            response: Schema | None = None
            # No strict mode yet

            @classmethod
            def from_tool(cls, tool: Tool) -> Self:
                return cls(
                    name=internal_tool_name_to_native_tool_call(tool.name),
                    description=tool.description or "",
                    parameters=Schema.from_json_schema(JsonSchema(tool.input_schema)) if tool.input_schema else None,
                    response=Schema.from_json_schema(JsonSchema(tool.output_schema)) if tool.output_schema else None,
                )

        functionDeclarations: list[FunctionDeclaration]
        # TODO: note that Google also offer Google-native tools (googleSearch, googleSearchRetrieval, codeExecution) that can be configured here.

    tools: Tool | None = None

    class ToolConfig(BaseModel):
        class FunctionCallingConfig(BaseModel):
            mode: Literal["MODE_UNSPECIFIED", "AUTO", "ANY", "NONE"] = "AUTO"
            allowedFunctionNames: list[str] | None = None

            @classmethod
            def from_domain(cls, tool_config: ToolChoice | None):
                if not tool_config:
                    return cls(mode="AUTO")

                if isinstance(tool_config, str):
                    match tool_config:
                        case "auto":
                            return cls(mode="AUTO")
                        case "none":
                            return cls(mode="NONE")
                        case _:
                            return cls(mode="ANY")

                return cls(mode="ANY", allowedFunctionNames=[tool_config.name])

        functionCallingConfig: FunctionCallingConfig

    toolConfig: ToolConfig | None = None

    class GenerationConfig(BaseModel):
        # Docs: https://cloud.google.com/vertex-ai/docs/reference/rest/v1/GenerationConfig
        # Docs: https://ai.google.dev/api/generate-content#generationconfig
        # TODO: use responseSchema

        responseMimeType: Literal["text/plain", "application/json"] = "text/plain"
        responseSchema: dict[str, Any] | None = None
        maxOutputTokens: int | None = None
        temperature: float = 0.0

        class ThinkingConfig(BaseModel):
            include_thoughts: bool = False
            thinkingBudget: int | None = None

        thinking_config: ThinkingConfig | None = None
        responseModalities: list[Literal["TEXT", "IMAGE"]] | None = None

        presencePenalty: float | None = None
        frequencyPenalty: float | None = None
        topP: float | None = None

    generationConfig: GenerationConfig

    class SafetySettings(BaseModel):
        # Docs: https://ai.google.dev/gemini-api/docs/safety-settings
        # Docs: https://cloud.google.com/vertex-ai/docs/reference/rest/v1/SafetySetting

        category: HarmCategory

        threshold: BLOCK_THRESHOLD

    safetySettings: list[SafetySettings] | None = None

    # Parallel tool calls are not supported


class SafetyRating(BaseModel):
    category: str
    probability: str
    probabilityScore: float | None = None
    severity: str | None = None
    severityScore: float | None = None


class Candidate(BaseModel):
    content: Content | None = None
    finishReason: str | None = None
    safetyRatings: list[SafetyRating] | None = None


class UsageMetadata(BaseModel):
    promptTokenCount: int | None = None
    candidatesTokenCount: int | None = None
    totalTokenCount: int | None = None
    cachedContentTokenCount: int | None = None

    def to_domain(self) -> LLMUsage:
        return LLMUsage(
            prompt_token_count=self.promptTokenCount,
            completion_token_count=self.candidatesTokenCount,
            prompt_token_count_cached=self.cachedContentTokenCount,
        )


class StreamedResponse(BaseModel):
    candidates: list[Candidate] | None = None
    usageMetadata: UsageMetadata | None = None


class PromptFeedback(BaseModel):
    blockReason: str | None = None


# https://ai.google.dev/api/generate-content#generatecontentresponse
# https://cloud.google.com/vertex-ai/docs/reference/rest/v1/GenerateContentResponse
class CompletionResponse(BaseModel):
    candidates: list[Candidate] | None = None
    usageMetadata: UsageMetadata | None = None
    promptFeedback: PromptFeedback | None = None
