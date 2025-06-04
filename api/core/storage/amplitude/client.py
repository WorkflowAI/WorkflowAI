import httpx

from core.domain.analytics_events.analytics_events import (
    FullAnalyticsEvent,
)
from core.storage.amplitude.models import AmplitudeRequest


class Amplitude:
    def __init__(
        self,
        api_key: str,
        base_url: str,
    ):
        self.api_key = api_key
        self.base_url = base_url

    async def send_event(self, events: list[FullAnalyticsEvent]):
        req = AmplitudeRequest.from_domain(self.api_key, events)
        async with httpx.AsyncClient() as client:
            response = await client.post(self.base_url, json=req.model_dump())
            response.raise_for_status()
