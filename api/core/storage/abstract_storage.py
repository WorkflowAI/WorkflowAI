import asyncio
from abc import ABC, abstractmethod
from typing import Any

from typing_extensions import Annotated

from core.domain.agent_run import AgentRun
from core.domain.analytics_events.analytics_events import SourceType
from core.domain.task_example import SerializableTaskExample
from core.domain.task_group import TaskGroup, TaskGroupIdentifier
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment


# TODO: most of these methods should not be used as they
# are linked to the obsolete way to deal with tasks (generic)
class AbstractStorage(ABC):
    """
    An abstract storage for task runs and examples that is exposed client side
    """

    def __init__(self) -> None:
        super().__init__()

        self._background_aio_tasks = set[asyncio.Task[Any]]()

    @property
    @abstractmethod
    def tenant(self) -> str:
        pass

    @abstractmethod
    async def store_task_resource(
        self,
        task: SerializableTaskVariant,
    ) -> tuple[SerializableTaskVariant, Annotated[bool, "whether a new task was created"]]:
        pass

    @abstractmethod
    async def store_task_run_resource(
        self,
        task: SerializableTaskVariant,
        run: AgentRun,
        user: UserIdentifier | None,
        source: SourceType | None,
    ) -> AgentRun:
        pass

    @abstractmethod
    async def task_group_by_id(
        self,
        task_id: str,
        task_schema_id: int,
        ref: int | VersionEnvironment | TaskGroupIdentifier,
    ) -> TaskGroup:
        """Returns a task run group given an id, alias or iteration"""
        pass

    # Still used in evaluators...
    @abstractmethod
    async def example_resource_by_id(self, example_id: str) -> SerializableTaskExample:
        pass
