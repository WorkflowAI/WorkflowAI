import logging
from collections.abc import Coroutine
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, TypeVar, override

from sentry_sdk import capture_exception

_T = TypeVar("_T")


def sentry_wrap(corot: Coroutine[Any, Any, _T]) -> Coroutine[Any, Any, _T | None]:
    async def captured() -> _T | None:
        try:
            return await corot
        except Exception as e:
            capture_exception(e)
            return None

    return captured()


class capture_errors(AbstractContextManager[None]):
    def __init__(self, logger: logging.Logger, msg: str):
        super().__init__()
        self._logger = logger
        self._msg = msg

    def __enter__(self):
        pass

    # Returning a bool here makes pyright understand that the context manager can suppress exceptions
    @override
    def __exit__(
        self,
        exctype: type[BaseException] | None,
        excinst: BaseException | None,
        exctb: TracebackType | None,
    ) -> bool:
        if exctype is None:
            return False

        self._logger.exception(self._msg, exc_info=excinst)
        return True
