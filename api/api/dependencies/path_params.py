from fastapi import Path
from typing_extensions import Annotated

AgentID = Annotated[str, Path(name="agent_id", title="The id of the task")]
TaskSchemaID = Annotated[int, Path(name="task_schema_id", title="The id of the task schema")]
GroupID = Annotated[int, Path(name="group_id", description="The iteration of an existing group")]
RunID = Annotated[str, Path(name="run_id", description="The id of the run")]
