import logging
from typing import Protocol

from core.domain.metrics import Metric
from core.storage.betterstack.betterstack_client import BetterStackClient
from core.utils.timed_buffer import TimedBuffer


class MetricsService(Protocol):
    async def start(self) -> None: ...
    async def close(self) -> None: ...
    async def send_metric(self, metric: Metric) -> None: ...


class BetterStackMetricsService:
    def __init__(
        self,
        tags: dict[str, str],
        betterstack_api_key: str,
        betterstack_api_url: str | None = None,
        send_interval_seconds: float = 30,
        max_buffer_size: int = 50,
        client: BetterStackClient | None = None,
    ):
        self._client = client or BetterStackClient(betterstack_api_key, betterstack_api_url)
        self._tags = tags
        self._buffer = TimedBuffer[Metric](
            self._send_metrics,
            max_buffer_size,
            send_interval_seconds,
        )
        self._logger = logging.getLogger(__name__)

    async def _send_metrics(self, metrics: list[Metric]) -> None:
        try:
            await self._client.send_metrics(metrics, self._tags)
        except Exception as e:
            self._logger.error("Failed to send metrics to BetterStack", exc_info=e, extra={"metrics": metrics})

    async def start(self):
        await self._buffer.start()

    async def close(self) -> None:
        await self._buffer.close()
        await self._client.close()

    async def send_metric(self, metric: Metric) -> None:
        await self._buffer.add(metric)
