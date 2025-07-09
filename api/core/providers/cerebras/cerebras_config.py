from typing import Literal

from pydantic import BaseModel

from core.domain.models.providers import Provider


class CerebrasConfig(BaseModel):
    provider: Literal[Provider.CEREBRAS] = Provider.CEREBRAS

    url: str = "https://api.cerebras.ai/v1/chat/completions"
    api_key: str

    def __str__(self):
        return f"CerebrasConfig(url={self.url}, api_key={self.api_key[:4]}****)"

