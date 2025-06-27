from typing import Literal

from pydantic import BaseModel

from core.domain.models.providers import Provider


class XAIConfig(BaseModel):
    provider: Literal[Provider.X_AI] = Provider.X_AI

    url: str = "https://api.x.ai/v1/chat/completions"
    api_key: str

    def __str__(self):
        return f"XAIConfig(url={self.url}, api_key={self.api_key[:4]}****)"
