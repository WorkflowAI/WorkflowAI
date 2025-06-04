import logging
import os

from api.broker import broker
from core.domain.events import SendAnalyticsEvent
from core.storage.amplitude.client import Amplitude

_logger = logging.getLogger(__name__)


@broker.task(retry_on_error=True)
async def handle_analytics_event(event: SendAnalyticsEvent):
    api_key = os.getenv("AMPLITUDE_API_KEY")
    if not api_key:
        _logger.warning("AMPLITUDE_API_KEY not set, skipping event")
        return

    url = os.getenv("AMPLITUDE_URL", "https://api2.amplitude.com/2/httpapi")
    amplitude_client = Amplitude(api_key=api_key, base_url=url)
    await amplitude_client.send_event([event.event])


jobs = [handle_analytics_event]
