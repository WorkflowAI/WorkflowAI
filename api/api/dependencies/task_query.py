from typing import Annotated, Optional

from fastapi import Depends, Query

from api.dependencies.path_params import AgentID, TaskSchemaID
from core.domain.task_query_mixin import TaskQueryMixin


def task_query_dependency(
    agent_id: AgentID,
    task_schema_id: TaskSchemaID,
    task_input_schema_version: Optional[str] = Query(default=None, description="The version of the task input class"),
    task_output_schema_version: Optional[str] = Query(default=None, description="The version of the task output class"),
) -> TaskQueryMixin:
    return TaskQueryMixin(
        task_id=agent_id,
        task_schema_id=task_schema_id,
        task_input_schema_version=task_input_schema_version,
        task_output_schema_version=task_output_schema_version,
    )


TaskQueryDep = Annotated[TaskQueryMixin, Depends(task_query_dependency)]
