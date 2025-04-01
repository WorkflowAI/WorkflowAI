import asyncio
import logging
from typing import NamedTuple

from api.services.internal_tasks.internal_tasks_service import InternalTasksService
from api.services.models import ModelsService
from core.domain.analytics_events.analytics_events import SourceType
from core.domain.changelogs import VersionChangelog
from core.domain.events import EventRouter, TaskGroupSaved
from core.domain.models import Model
from core.domain.task_group import TaskGroup, TaskGroupIdentifier, TaskGroupQuery
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from core.domain.version_major import VersionDeploymentMetadata, VersionMajor
from core.storage import TaskTuple
from core.storage.backend_storage import BackendStorage
from core.utils.coroutines import sentry_wrap
from core.utils.models.dumps import safe_dump_pydantic_model


class VersionsService:
    def __init__(self, storage: BackendStorage, event_router: EventRouter):
        self._storage = storage
        self._event_router = event_router
        self._logger = logging.getLogger(self.__class__.__name__)

    async def _list_version_majors(self, task_id: str, schema_id: int | None):
        return [v async for v in self._storage.task_groups.list_version_majors(task_id, schema_id)]

    async def _deployments_metadata_by_iteration(self, task_id: str, schema_id: int | None):
        by_iteration: dict[int, list[VersionDeploymentMetadata]] = {}
        async for d in self._storage.task_deployments.list_task_deployments(task_id, schema_id, exclude=["properties"]):
            by_iteration.setdefault(d.iteration, []).append(VersionDeploymentMetadata.from_deployment(d))
        return by_iteration

    async def _changelogs_by_similarity_hash(self, task_id: str, schema_id: int | None):
        by_similarity_hash: dict[str, VersionChangelog] = {}
        async for c in self._storage.changelogs.list_changelogs(task_id, schema_id):
            by_similarity_hash[c.similarity_hash_to] = c
        return by_similarity_hash

    async def _model_price_calculators_by_schema_id(
        self,
        task_id: TaskTuple,
        schema_ids: set[int],
        models_service: ModelsService,
    ):
        # Max time is 1sec per schema id so some will fail
        calculators = await asyncio.gather(
            *[models_service.model_price_calculator(task_id, schema_id) for schema_id in schema_ids],
            return_exceptions=True,
        )
        return {
            schema_id: calculator
            for schema_id, calculator in zip(schema_ids, calculators)
            if not isinstance(calculator, BaseException)
        }

    async def list_version_majors(
        self,
        task_id: TaskTuple,
        schema_id: int | None,
        models_service: ModelsService,
    ) -> list[VersionMajor]:
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(self._list_version_majors(task_id[0], schema_id))
            t2 = tg.create_task(self._deployments_metadata_by_iteration(task_id[0], schema_id))
            t3 = tg.create_task(self._changelogs_by_similarity_hash(task_id[0], schema_id))

        versions = t1.result()
        deployments_by_iteration = t2.result()
        changelogs_by_similarity_hash = t3.result()

        for v in versions:
            for m in v.minors:
                m.deployments = deployments_by_iteration.get(m.iteration)
            v.changelog = changelogs_by_similarity_hash.get(v.similarity_hash)

        # To aggregate costs we need to get all the schema ids
        schema_ids = set(v.schema_id for v in versions)
        model_price_calculators_by_schema_id = await self._model_price_calculators_by_schema_id(
            task_id,
            schema_ids,
            models_service,
        )
        for v in versions:
            if calc := model_price_calculators_by_schema_id.get(v.schema_id):
                for m in v.minors:
                    if isinstance(m.properties.model, Model):
                        m.cost_estimate_usd = calc(m.properties.model)

        return versions

    class EnrichedVersion(NamedTuple):
        group: TaskGroup
        deployments: list[VersionDeploymentMetadata] | None
        cost_estimate_usd: float | None
        variant: SerializableTaskVariant | None

    async def get_version(self, task_id: TaskTuple, id: TaskGroupIdentifier, models_service: ModelsService):
        group = await self._storage.task_groups.get_task_group_by_id(task_id[0], id)

        async def _list_deployments():
            return [
                d
                async for d in self._storage.task_deployments.get_task_deployment_for_iteration(
                    task_id[0],
                    group.iteration,
                )
            ]

        async def _get_variant():
            if not group.properties.task_variant_id:
                return None
            return await self._storage.task_version_resource_by_id(task_id[0], group.properties.task_variant_id)

        deployments, cost_calculator, variant = await asyncio.gather(
            sentry_wrap(_list_deployments()),
            sentry_wrap(self._model_price_calculators_by_schema_id(task_id, {group.schema_id}, models_service)),
            sentry_wrap(_get_variant()),
        )

        if cost_calculator and (by_schema := cost_calculator.get(group.schema_id)) and group.properties.model:
            cost_estimate_usd = by_schema(Model(group.properties.model))
        else:
            cost_estimate_usd = None

        return self.EnrichedVersion(
            group=group,
            deployments=[VersionDeploymentMetadata.from_deployment(d) for d in deployments] if deployments else None,
            cost_estimate_usd=cost_estimate_usd,
            variant=variant,
        )

    async def save_version(self, task_id: str, hash: str):
        grp, newly_saved = await self._storage.task_groups.save_task_group(task_id, hash)
        if newly_saved:
            if not grp.semver:
                self._logger.error(
                    "Saved version did not have a semver",
                    extra={"task_id": task_id, "hash": hash, "grp": safe_dump_pydantic_model(grp)},
                )
            else:
                self._event_router(
                    TaskGroupSaved(
                        task_id=task_id,
                        task_schema_id=grp.schema_id,
                        hash=hash,
                        major=grp.semver.major,
                        minor=grp.semver.minor,
                        properties=grp.properties,
                    ),
                )

        return grp

    async def _first_id_for_schema(self, task_id: str, schema_id: int):
        query = TaskGroupQuery(
            task_id=task_id,
            task_schema_id=schema_id,
            sort_by="oldest",
            limit=1,
        )
        try:
            grp = await anext(self._storage.task_groups.list_task_groups(query, include=["id"]))
            return grp.id
        except StopAsyncIteration:
            self._logger.warning(
                "No task groups found for schema",
                extra={"task_id": task_id, "schema_id": schema_id},
            )
            return None

    async def autosave_version(self, task_id: str, grp_id: str, source: SourceType | None):
        grp_storage = self._storage.task_groups
        grp = await grp_storage.get_task_group_by_id(task_id, grp_id)
        if grp.semver:
            return grp

        # If the below is true then the version was created by the SDK so we always autosave
        if not (source and source == SourceType.SDK):
            # If the version is the first one for the schema then we save it
            first_id = await grp_storage.first_id_for_schema(task_id, grp.schema_id)
            if not (first_id == grp.id):
                return None

        return await self.save_version(task_id, grp.id)

    async def generate_changelog_for_major(
        self,
        task_id: str,
        schema_id: int,
        major: int,
        properties: TaskGroupProperties,
        internal_service: InternalTasksService,
    ):
        previous_major = await self._storage.task_groups.get_previous_major(task_id, schema_id, major)
        if not previous_major:
            return

        previous_major_properties = previous_major.properties

        changelog_item = await internal_service.generate_changelog(
            tenant=self._storage.tenant,
            task_id=task_id,
            task_schema_id=schema_id,
            major_from=previous_major.semver.major if previous_major.semver else 0,
            major_to=major,
            old_task_group=previous_major_properties,
            new_task_group=properties,
        )
        if not changelog_item:
            return
        await self._storage.changelogs.insert_changelog(changelog_item)
