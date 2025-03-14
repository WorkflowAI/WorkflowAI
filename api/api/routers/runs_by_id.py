import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from api.dependencies.services import InternalTasksServiceDep, RunsServiceDep
from api.dependencies.task_info import TaskTupleDep
from core.domain.task_run import SerializableTaskRun
from core.domain.task_variant import SerializableTaskVariant
from core.runners.workflowai.utils import FileWithKeyPath, extract_files
from core.storage import ObjectNotFoundException

from ..dependencies.storage import StorageDep

router = APIRouter(prefix="/agents/{task_id}/runs/{run_id}", deprecated=True)


async def task_run_dependency(
    runs_service: RunsServiceDep,
    task_tuple: TaskTupleDep,
    run_id: str = Path(title="The id of the run"),
) -> SerializableTaskRun:
    # Passing an empty set to exclude to avoid the default exclusion of tool calls and LLM completions
    return await runs_service.run_by_id(task_tuple, run_id, exclude=set())


SerializableTaskRunDep = Annotated[SerializableTaskRun, Depends(task_run_dependency)]


async def task_version_dependency(storage: StorageDep, run: SerializableTaskRunDep) -> SerializableTaskVariant:
    try:
        return await storage.task_variant_latest_by_schema_id(run.task_id, run.task_schema_id)
    except ObjectNotFoundException:
        raise HTTPException(status_code=404, detail="Task not found")


SerializableTaskVariantDep = Annotated[SerializableTaskVariant, Depends(task_version_dependency)]


@router.get("")
async def get_run(run: SerializableTaskRunDep) -> SerializableTaskRun:
    return run


class TranscriptionResponse(BaseModel):
    transcriptions_by_keypath: dict[str, str]


@router.get(
    "/transcriptions",
    response_model=TranscriptionResponse,
    description="Transcribe audio files in agent run",
)
async def transcribed_audio(
    run: SerializableTaskRunDep,
    internal_tasks_service: InternalTasksServiceDep,
    storage: StorageDep,
):
    task = await storage.task_variant_latest_by_schema_id(run.task_id, run.task_schema_id)
    _, _, files = extract_files(task.input_schema.json_schema, run.task_input)
    audio_files = [file for file in files if file.is_audio]
    model = run.group.properties.model

    async def transcribe_file(file: FileWithKeyPath) -> tuple[str, str]:
        transcription = await internal_tasks_service.transcribe_audio(file, model=model)
        return file.key_path_str, transcription

    transcriptions: dict[str, str] = {}
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(transcribe_file(file)) for file in audio_files]

    for task in tasks:
        key_path, transcription = await task
        transcriptions[key_path] = transcription

    return TranscriptionResponse(transcriptions_by_keypath=transcriptions)
