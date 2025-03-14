from fastapi import Depends, HTTPException
from typing_extensions import Annotated

from api.dependencies.path_params import GroupID, TaskID, TaskSchemaID
from api.dependencies.storage import TaskGroupStorageDep
from core.domain.task_group import TaskGroup
from core.storage import ObjectNotFoundException


async def group_dependency(
    task_id: TaskID,
    task_schema_id: TaskSchemaID,
    group_id: GroupID,
    storage: TaskGroupStorageDep,
):
    try:
        return await storage.get_task_group_by_iteration(task_id, task_schema_id, group_id)
    except ObjectNotFoundException:
        raise HTTPException(status_code=404, detail="Task group not found")


TaskGroupDep = Annotated[TaskGroup, Depends(group_dependency)]
