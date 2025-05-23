from typing import Any, override

from taskiq import BrokerMessage, InMemoryBroker


class PausableInMemoryBroker(InMemoryBroker):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self._paused = False
        self._waiting_messages: list[BrokerMessage] = []

    def pause(self):
        self._paused = True

    async def resume(self):
        self._paused = False

        while self._waiting_messages:
            message = self._waiting_messages.pop(0)
            await super().kick(message)

    @override
    async def kick(self, message: BrokerMessage):
        if self._paused:
            self._waiting_messages.append(message)
            return
        await super().kick(message)
