import asyncio
from typing import Any, Callable, Coroutine, Generic, TypeVar

from core.utils.coroutines import sentry_wrap

_T = TypeVar("_T")


class TimedBuffer(Generic[_T]):
    def __init__(
        self,
        purge_fn: Callable[[list[_T]], Coroutine[Any, Any, None]],
        max_buffer_length: int = 50,
        send_interval_seconds: float = 30,
    ):
        self._purge_fn = purge_fn
        self._buffer: list[_T] = []
        self._buffer_lock = asyncio.Lock()
        self._max_buffer_length = max_buffer_length
        self._send_interval_seconds = send_interval_seconds
        self._schedule_task: asyncio.Task[None] | None = None
        self._started = False
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self):
        self._started = True
        if not self._schedule_task:
            self._schedule_task = asyncio.create_task(self._scheduled_purge())

    async def close(self) -> None:
        self._started = False

        if self._schedule_task:
            self._schedule_task.cancel()

        await asyncio.gather(*self._tasks)

    def _add_task(self, task: Coroutine[Any, Any, None]):
        t = asyncio.create_task(sentry_wrap(task))
        self._tasks.add(t)
        t.add_done_callback(self._tasks.remove)

    async def _scheduled_purge(self) -> None:
        while self._started:
            # Send metrics every 10 seconds
            await asyncio.sleep(self._send_interval_seconds)
            # Adding as a task so we can cancel the schedule without
            # affecting the send metrics task
            self._add_task(self.purge())

    async def purge(self):
        async with self._buffer_lock:
            current = self._buffer
            self._buffer = []
        if not current:
            return
        await self._purge_fn(current)

    async def add(self, item: _T):
        async with self._buffer_lock:
            self._buffer.append(item)
        # Purging the buffer if it is too big
        if len(self._buffer) >= self._max_buffer_length:
            self._add_task(self.purge())
