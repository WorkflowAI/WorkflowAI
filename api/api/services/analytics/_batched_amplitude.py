from core.domain.analytics_events.analytics_events import FullAnalyticsEvent
from core.storage.amplitude.client import Amplitude
from core.utils.timed_buffer import TimedBuffer


class BatchedAmplitude:
    def __init__(self, api_key: str, url: str):
        self._amplitude_client = Amplitude(api_key=api_key, base_url=url)
        self._timed_buffer = TimedBuffer[FullAnalyticsEvent](
            self._send_events,
            # Clearing the buffer every 60 seconds or when it reaches 50 events
            max_buffer_length=50,
            send_interval_seconds=60,
        )

    async def _send_events(self, events: list[FullAnalyticsEvent]):
        await self._amplitude_client.send_event(events)

    async def send_event(self, event: FullAnalyticsEvent):
        await self._timed_buffer.add(event)

    async def start(self):
        await self._timed_buffer.start()

    async def close(self):
        await self._timed_buffer.close()

    async def flush(self):
        await self._timed_buffer.purge()
