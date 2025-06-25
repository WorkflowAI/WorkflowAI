from typing import NamedTuple

from core.domain.task import SerializableTask
from core.storage.backend_storage import BackendStorage

INTERNAL_TASK_IDS = {
    "checktextfollowsinstructions",
    "chattaskschemageneration",
    "taskinputexample",
    "generateevaluationinstructions",
    "generateevaluationfixedinstructions",
    "generateevaluationcode",
    "textequivalence",
    "taskinstructionsgeneration",
    "taskinstructionsreformating",
    "taskdescriptiongeneration",
    "compareoutputs",
    "evaluateoutput",
    "taskinputoutputclassgeneration",
    "updateinstructions",
    "chatfaithfulnesscheck",
    "taskinstructionsupdate",
    "taskschemacomparison",
    "audiotranscription",
}


def _remove_variants(task: SerializableTask) -> SerializableTask:
    all = task.versions
    task.versions = []
    schemas = set[int]()

    for v in all:
        if v.schema_id not in schemas:
            task.versions.append(v)
            schemas.add(v.schema_id)

    return task


async def list_tasks(
    storage: BackendStorage,
    include_internal: bool = False,
    limit: int | None = None,
    with_schemas: bool = False,
) -> list[SerializableTask]:
    out: list[SerializableTask] = []

    async for a in storage.fetch_tasks(limit=limit, with_schemas=with_schemas):
        if not include_internal:
            if a.id in INTERNAL_TASK_IDS:
                continue
        if a.versions:
            try:
                # TODO: Gather task info in one call after getting all ids instead of one by one
                task_info = await storage.tasks.get_task_info(a.id)
                a.enrich(task_info)
            except Exception:
                pass
        out.append(_remove_variants(a))

    return out


async def get_task_by_id(storage: BackendStorage, task_id: str, with_schemas: bool = False) -> SerializableTask:
    task = await storage.get_task(task_id, with_schemas)
    if task.versions:
        try:
            task_info = await storage.tasks.get_task_info(task.id)
            task.enrich(task_info)
        except Exception:
            pass
    return _remove_variants(task)


class AgentSummary(NamedTuple):
    """
    A simple object to represents an agent name and what it does.
    """

    name: str
    description: str | None

    def __str__(self) -> str:
        if self.description is None:
            return self.name
        return f"{self.name}: {self.description}"

    @classmethod
    def from_domain(cls, agent: SerializableTask) -> "AgentSummary":
        return cls(name=agent.name, description=agent.description)


async def list_agent_summaries(storage: BackendStorage, limit: int | None = None) -> list[AgentSummary]:
    return sorted(
        {AgentSummary.from_domain(agent) for agent in await list_tasks(storage, limit=limit)},
        key=lambda x: x.name,
    )
