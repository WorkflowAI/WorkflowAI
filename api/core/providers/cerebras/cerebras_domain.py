from typing import Any, Literal
from pydantic import BaseModel, Field

from core.domain.llm_usage import LLMUsage
from core.domain.message import MessageDeprecated
from core.providers.base.models import StandardMessage, TextContentDict

CerebrasRole = Literal["system", "user", "assistant"]


class CerebrasMessage(BaseModel):
    role: CerebrasRole
    content: str | None = None

    @classmethod
    def from_domain(cls, message: MessageDeprecated) -> "CerebrasMessage":
        return cls(role=message.role.value, content=message.content)

    def to_standard(self) -> StandardMessage:
        return StandardMessage(
            role=self.role,
            content=[TextContentDict(type="text", text=self.content or "")],
        )


class CompletionRequest(BaseModel):
    messages: list[CerebrasMessage]
    model: str
    temperature: float
    max_tokens: int | None
    stream: bool = False
    top_p: float | None = None


class ChoiceMessage(BaseModel):
    role: CerebrasRole | None = None
    content: str | None = None


class Choice(BaseModel):
    message: ChoiceMessage
    finish_reason: str | None = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_domain(self) -> LLMUsage:
        return LLMUsage(
            prompt_token_count=self.prompt_tokens,
            completion_token_count=self.completion_tokens,
        )


class CompletionResponse(BaseModel):
    id: str | None = None
    choices: list[Choice] = Field(default_factory=list)
    usage: Usage | None = None


class DeltaMessage(BaseModel):
    content: str | None = None


class ChoiceDelta(BaseModel):
    delta: DeltaMessage
    finish_reason: str | None = None


class StreamedResponse(BaseModel):
    id: str | None = None
    choices: list[ChoiceDelta] = Field(default_factory=list)
    usage: Usage | None = None
