from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from core.domain.task_info import PublicTaskInfo, TaskInfo
from core.storage.models import TaskUpdate


class TaskSystemStorage(Protocol):
    async def get_public_task_info(self, task_uid: int) -> PublicTaskInfo: ...


class TaskStorage(TaskSystemStorage):
    # TODO: move to a system storage that takes tenant_uid and task_id
    async def is_task_public(self, task_id: str) -> bool: ...

    async def get_task_info(self, task_id: str) -> TaskInfo: ...

    async def update_task(self, task_id: str, update: TaskUpdate, before: bool = False) -> TaskInfo:
        """Update a task. If before is True, the returned task info is from before the update."""
        ...

    def active_tasks(self, since: datetime) -> AsyncIterator[PublicTaskInfo]: ...
