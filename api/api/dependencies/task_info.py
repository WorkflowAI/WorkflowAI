import logging
from typing import Annotated

from fastapi import Depends, HTTPException

from api.dependencies.path_params import AgentID
from api.dependencies.storage import StorageDep
from core.domain.task_info import TaskInfo
from core.storage import TaskTuple

logger = logging.getLogger(__name__)


async def task_info_dependency(
    agent_id: AgentID,
    storage: StorageDep,
) -> TaskInfo | None:
    try:
        return await storage.tasks.get_task_info(agent_id)
    except Exception as e:
        # TODO: we should remove the exception here
        logger.error(
            "Error getting task info",
            extra={
                "agent_id": agent_id,
                "error": e,
            },
        )
        return None


TaskInfoDep = Annotated[TaskInfo | None, Depends(task_info_dependency)]


async def task_tuple_dependency(task_info: TaskInfoDep) -> TaskTuple:
    if task_info is None:
        raise HTTPException(status_code=404, detail="Task info not found")
    return task_info.id_tuple


TaskTupleDep = Annotated[TaskTuple, Depends(task_tuple_dependency)]
