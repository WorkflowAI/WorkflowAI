from fastapi import APIRouter

from api.dependencies.event_router import EventRouterDep
from core.domain.task_example import SerializableTaskExample

from ..dependencies.storage import StorageDep

router = APIRouter(prefix="/agents/{agent_id}/examples", deprecated=True, include_in_schema=False)


@router.get("/{example_id}")
async def get_task_example(
    storage: StorageDep,
    example_id: str,
) -> SerializableTaskExample:
    return await storage.example_resource_by_id(example_id)


@router.delete("/{example_id}")
async def delete_task_example(
    storage: StorageDep,
    example_id: str,
    event_router: EventRouterDep,
) -> None:
    await storage.delete_example(example_id)
