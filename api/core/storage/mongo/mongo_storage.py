import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator, Optional

from bson import CodecOptions, ObjectId
from motor.motor_asyncio import (
    AsyncIOMotorClient,
)
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
from typing_extensions import deprecated, override

from core.domain.analytics_events.analytics_events import SourceType
from core.domain.errors import InternalError
from core.domain.events import EventRouter, TaskGroupCreated
from core.domain.task import SerializableTask
from core.domain.task_example import SerializableTaskExample
from core.domain.task_example_query import SerializableTaskExampleQuery
from core.domain.task_group import TaskGroup, TaskGroupIdentifier
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_info import TaskInfo
from core.domain.task_input import TaskInput, TaskInputFields
from core.domain.task_run import SerializableTaskRun
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.storage.evaluator_storage import EvaluatorStorage
from core.storage.models import TaskUpdate
from core.storage.mongo.models.task_group import TaskGroupDocument
from core.storage.mongo.models.user_identifier import UserIdentifierSchema
from core.storage.mongo.partials.changelogs import MongoChangeLogStorage
from core.storage.mongo.partials.evaluators import MongoEvaluatorStorage
from core.storage.mongo.partials.input_evaluations import MongoInputEvaluationStorage
from core.storage.mongo.partials.mongo_feedback import MongoFeedbackStorage
from core.storage.mongo.partials.mongo_organizations import MongoOrganizationStorage
from core.storage.mongo.partials.mongo_tasks import MongoTaskStorage
from core.storage.mongo.partials.reviews import MongoReviewsStorage
from core.storage.mongo.partials.reviews_benchmark import MongoReviewsBenchmarkStorage
from core.storage.mongo.partials.task_deployments import MongoTaskDeploymentsStorage
from core.storage.mongo.partials.task_group_semvers import TaskGroupSemverStorage
from core.storage.mongo.partials.task_groups import MongoTaskGroupStorage
from core.storage.mongo.partials.task_inputs import MongoTaskInputStorage
from core.storage.mongo.partials.task_variants import MongoTaskVariantsStorage
from core.storage.mongo.partials.transcriptions import MongoTranscriptionStorage
from core.storage.task_group_storage import TaskGroupStorage
from core.storage.task_input_storage import TaskInputsStorage
from core.storage.task_run_storage import TaskRunStorage
from core.utils.encryption import Encryption

from .codecs import type_registry
from .models.task_example import TaskExampleDocument
from .models.task_schema_id_document import TaskSchemaIdDocument
from .models.task_variant import TaskVariantDocument
from .mongo_types import AsyncClient, AsyncCollection, AsyncCursor, AsyncDatabase
from .utils import dump_model, extract_connection_info, object_id

logger = logging.getLogger(__name__)


class MongoStorage(BackendStorage):
    def __init__(
        self,
        tenant: str,
        encryption: Encryption,
        event_router: EventRouter,
        # TODO[ids]: make it mandatory
        tenant_uid: int = 0,
        connection_string: Optional[str] = None,
        client: Optional[AsyncClient] = None,
        db_name: Optional[str] = None,
    ):
        super().__init__()
        if client:
            if not db_name:
                raise ValueError("db_name must be provided when client is provided")

            self.client = client  # type:ignore
            self._db_name: str = db_name
        else:
            self.client, self._db_name = self.build_client(
                connection_string or os.environ["WORKFLOWAI_MONGO_CONNECTION_STRING"],
            )

        self._tenant = tenant
        self._tenant_uid = tenant_uid
        self.encryption = encryption
        self.event_router = event_router

    @property
    def tenant(self) -> str:
        return self._tenant

    @classmethod
    def build_client(cls, connection_string: str) -> tuple[AsyncClient, str]:
        """Returns a client and db name"""
        url, name, tls_ca_file = extract_connection_info(connection_string)
        # By default, the timeoutMS property should allow us to set a global timeout
        # Except that it seems to override maxTimeMS in aggregate functions
        client: AsyncClient = AsyncIOMotorClient(url, tlsCAFile=tls_ca_file)  # pyright: ignore [reportAssignmentType]
        return client, name

    @property
    def _db(self) -> AsyncDatabase:
        return self.client[self._db_name]  # type:ignore

    def _get_collection(self, name: str) -> AsyncCollection:
        return self._db.get_collection(name, codec_options=CodecOptions(type_registry=type_registry, tz_aware=True))

    @property
    def _task_variants_collection(self) -> AsyncCollection:
        return self._get_collection("tasks")

    @property
    def _task_runs_collection(self) -> AsyncCollection:
        return self._get_collection("task_runs")

    @property
    def _task_examples_collections(self) -> AsyncCollection:
        return self._get_collection("task_examples")

    @property
    def _task_schema_id_collection(self) -> AsyncCollection:
        return self._get_collection("task_schema_id")

    @property
    def _task_run_group_idx_collection(self) -> AsyncCollection:
        return self._get_collection("task_run_group_idx")

    @property
    def _task_run_group_collection(self) -> AsyncCollection:
        return self._get_collection("task_run_group")

    @property
    def _organization_collection(self) -> AsyncCollection:
        return self._get_collection("org_settings")

    @property
    def _reviews_collection(self) -> AsyncCollection:
        return self._get_collection("task_run_reviews")

    @property
    def _review_benchmarks_collection(self) -> AsyncCollection:
        return self._get_collection("task_run_review_benchmarks")

    @property
    def _task_schemas_collection(self) -> AsyncCollection:
        return self._get_collection("task_schemas")

    @property
    def _task_benchmarks_collection(self) -> AsyncCollection:
        return self._get_collection("task_benchmarks")

    @property
    def _task_evaluators_collection(self) -> AsyncCollection:
        return self._get_collection("task_evaluators")

    @property
    def _task_inputs_collection(self) -> AsyncCollection:
        return self._get_collection("task_inputs")

    @property
    def _tasks_collection(self) -> AsyncCollection:
        # Not named tasks for historical reasons
        return self._get_collection("task_info")

    @property
    def _changelogs_collection(self) -> AsyncCollection:
        return self._get_collection("changelogs")

    @property
    def _migrations_collection(self) -> AsyncCollection:
        return self._get_collection("migrations")

    @property
    def _dataset_benchmarks_collection(self) -> AsyncCollection:
        return self._get_collection("dataset_benchmarks")

    @property
    def _input_evaluations_collection(self) -> AsyncCollection:
        return self._get_collection("input_evaluations")

    @property
    def _transcriptions_collection(self) -> AsyncCollection:
        return self._get_collection("transcriptions")

    @property
    def _task_deployments_collection(self) -> AsyncCollection:
        return self._get_collection("task_deployments")

    @property
    def _task_group_semvers_collection(self) -> AsyncCollection:
        return self._get_collection("task_run_group_semver")

    @property
    def _feedback_collection(self) -> AsyncCollection:
        return self._get_collection("feedback")

    @property
    def _tenant_tuple(self):
        return (self._tenant, self._tenant_uid)

    @property
    def evaluators(self) -> EvaluatorStorage:
        return MongoEvaluatorStorage(self._tenant_tuple, self._task_evaluators_collection)

    @property
    @override
    def task_runs(self) -> TaskRunStorage:
        from core.storage.mongo.partials.task_runs import MongoTaskRunStorage

        return MongoTaskRunStorage(self._tenant_tuple, self._task_runs_collection)

    @property
    def tasks(self):
        return MongoTaskStorage(self._tenant_tuple, self._tasks_collection, self.task_variants)

    @property
    def task_groups(self) -> TaskGroupStorage:
        return MongoTaskGroupStorage(
            self._tenant_tuple,
            self._task_run_group_collection,
            self.task_group_semvers,
        )

    @property
    def task_variants(self) -> MongoTaskVariantsStorage:
        return MongoTaskVariantsStorage(self._tenant_tuple, self._task_variants_collection)

    @property
    def task_inputs(self) -> TaskInputsStorage:
        return MongoTaskInputStorage(self._tenant_tuple, self._task_inputs_collection)

    @property
    def organizations(self):
        return MongoOrganizationStorage(self._tenant_tuple, self._organization_collection, self.encryption)

    @property
    def changelogs(self) -> MongoChangeLogStorage:
        return MongoChangeLogStorage(self._tenant_tuple, self._changelogs_collection)

    @property
    def input_evaluations(self) -> MongoInputEvaluationStorage:
        return MongoInputEvaluationStorage(self._tenant_tuple, self._input_evaluations_collection)

    @property
    def transcriptions(self) -> MongoTranscriptionStorage:
        return MongoTranscriptionStorage(self._tenant_tuple, self._transcriptions_collection)

    @property
    def reviews(self):
        return MongoReviewsStorage(self._tenant_tuple, self._reviews_collection)

    @property
    def review_benchmarks(self):
        return MongoReviewsBenchmarkStorage(self._tenant_tuple, self._review_benchmarks_collection)

    @property
    def task_deployments(self):
        return MongoTaskDeploymentsStorage(self._tenant_tuple, self._task_deployments_collection)

    @property
    def task_group_semvers(self):
        return TaskGroupSemverStorage(self._tenant_tuple, self._task_group_semvers_collection)

    @property
    def feedback(self):
        return MongoFeedbackStorage(self._tenant_tuple, self._feedback_collection)

    @override
    async def is_ready(self) -> bool:
        try:
            await self.client.server_info()
            return True
        except ServerSelectionTimeoutError as e:
            logger.exception("ServerSelectionTimeoutError", exc_info=e)
            return False

    # ----------------------------------------------------
    # Tasks
    def _migration_filter(self) -> dict[str, Any]:
        return {"_id": "1"}

    async def list_migrations(self) -> list[str]:
        doc = await self._migrations_collection.find_one(self._migration_filter())
        if not doc:
            return []
        return doc.get("migrations", [])

    async def add_migration(self, migration: str) -> None:
        res = await self._migrations_collection.update_one(
            {**self._migration_filter(), "locked": True},
            {"$push": {"migrations": migration}},
        )
        if res.modified_count != 1:
            raise ObjectNotFoundException("Migration lock not found")

    async def remove_migration(self, migration: str) -> None:
        res = await self._migrations_collection.update_one(
            {**self._migration_filter(), "locked": True},
            {"$pull": {"migrations": migration}},
        )
        if res.modified_count != 1:
            raise ObjectNotFoundException(f"Migration {migration} not found")

    async def lock_migrations(self) -> bool:
        async def _attempt_locking_on_existing_doc():
            res = await self._migrations_collection.update_one(
                {**self._migration_filter(), "locked": False},
                {"$set": {"locked": True}},
            )
            return res.modified_count == 1 or res.upserted_id is not None

        # Splitting upsert to make sure it is impervious to race conditions
        doc = await self._migrations_collection.find_one(self._migration_filter())

        if doc:
            return await _attempt_locking_on_existing_doc()

        try:
            await self._migrations_collection.insert_one({**self._migration_filter(), "locked": True})
            return True
        except DuplicateKeyError:
            return await _attempt_locking_on_existing_doc()

    async def unlock_migrations(self) -> None:
        res = await self._migrations_collection.update_one(self._migration_filter(), {"$set": {"locked": False}})
        if res.modified_count != 1:
            raise ObjectNotFoundException("Migration lock not found")

    # ----------------------------------------------------
    # Tasks

    def _tenant_filter(self) -> dict[str, Any]:
        return {"tenant": self._tenant}

    def _tenant_uid_filter(self) -> dict[str, Any]:
        return {"tenant_uid": self._tenant_uid}

    def _build_list_tasks_pipeline(self, filter: dict[str, Any], limit: int | None) -> list[dict[str, Any]]:
        match_clause = {"$match": {**filter, **self._tenant_filter()}}
        pipeline: list[dict[str, Any]] = [
            match_clause,
            {
                "$group": {
                    "_id": "$slug",
                    "id": {"$first": "$slug"},
                    "name": {"$first": "$name"},
                    "is_public": {"$first": "$is_public"},
                    "latest_created_at": {"$max": "$created_at"},
                    "versions": {
                        "$push": {
                            "schema_id": "$schema_id",
                            "variant_id": "$version",
                            "description": "$description",
                            "input_schema_version": "$input_schema.version",
                            "output_schema_version": "$output_schema.version",
                            "created_at": "$created_at",
                        },
                    },
                },
            },
            # Sorting is made after grouping and not right after the match (more desirable compute-wise)n because
            # the grouping is messing up the sort order
            {"$sort": {"latest_created_at": -1}},
        ]

        if limit:
            pipeline.append({"$limit": limit})

        return pipeline

    async def _list_tasks_pipeline(
        self,
        filter: dict[str, Any],
        limit: int | None = None,
    ) -> AsyncIterator[SerializableTask]:
        pipeline = self._build_list_tasks_pipeline(filter, limit)
        async for doc in self._task_variants_collection.aggregate(pipeline):
            try:
                yield SerializableTask.model_validate(doc)
            except ValidationError as e:
                logger.exception(e, extra={"doc": doc})

    @override
    def fetch_tasks(self, limit: int | None = None) -> AsyncIterator[SerializableTask]:
        return self._list_tasks_pipeline({}, limit)

    @override
    async def get_task(self, task_id: str) -> SerializableTask:
        task = None
        async for t in self._list_tasks_pipeline({"slug": task_id}):
            task = t
            break

        if not task:
            raise ObjectNotFoundException(f"The agent id '{task_id}' was not found", code="agent_not_found")

        try:
            task_info = await self.tasks.get_task_info(task_id)
            task.enrich(task_info)
        except ObjectNotFoundException:
            logger.warning(
                "Task info is missing for task",
                extra={"task_id": task.id},
            )

        return task

    async def _find_task_version(
        self,
        filter: dict[str, Any],
        sort: list[tuple[str, int]] | None = None,
    ) -> SerializableTaskVariant:
        filter = {**filter, **self._tenant_filter()}
        corot = self._task_variants_collection.find_one(filter, sort=sort)
        doc = await corot
        if not doc:
            raise ObjectNotFoundException(
                f"Agent version not found for {filter}",
                code="version_not_found",
            )
        schema = TaskVariantDocument.model_validate(doc)
        res = schema.to_resource()
        if not res.task_uid:
            try:
                task_info = await self.tasks.get_task_info(res.task_id)
                res.task_uid = task_info.uid
            except ObjectNotFoundException:
                logger.error("Task info not found, skipping task uid assignment", extra={"task_id": res.task_id})
        return res

    @override
    async def task_version_resource_by_id(self, task_id: str, version_id: str) -> SerializableTaskVariant:
        return await self._find_task_version({"version": version_id, "slug": task_id, **self._tenant_filter()})

    @override
    async def task_variant_latest_by_schema_id(self, task_id: str, task_schema_id: int) -> SerializableTaskVariant:
        return await self._find_task_version(
            {"slug": task_id, "schema_id": task_schema_id, **self._tenant_filter()},
            sort=[("created_at", -1)],
        )

    async def store_task_resource(self, task: SerializableTaskVariant) -> tuple[SerializableTaskVariant, bool]:
        existing_variant = await self._task_variants_collection.find_one_and_update(
            {"version": task.id, "slug": task.task_id, **self._tenant_filter()},
            {"$set": {"created_at": task.created_at}},
            return_document=True,
        )
        if existing_variant:
            return TaskVariantDocument.model_validate(existing_variant).to_resource(), False

        # Check if the task info exists
        tasks_storage = self.tasks
        task_info: TaskInfo | None = None
        try:
            task_info = await tasks_storage.get_task_info(task.task_id)
            task.name = task_info.name
            task.is_public = task_info.is_public
            task.task_uid = task_info.uid
        except ObjectNotFoundException:
            # task info does not exist so we have to create it
            task_info = await tasks_storage.update_task(
                task.task_id,
                TaskUpdate(
                    is_public=task.is_public,
                    name=task.name,
                ),
            )
            task.task_uid = task_info.uid

        idx = await self.get_schema_id(
            task.task_id,
            task.task_uid,
            task.input_schema.version,
            task.output_schema.version,
        )
        schema = TaskVariantDocument.from_resource(self._tenant, task)
        schema.tenant_uid = self._tenant_uid
        schema.schema_id = idx
        try:
            await self._task_variants_collection.insert_one(dump_model(schema))
        except DuplicateKeyError:
            # task can already exist in race conditions
            return await self.task_version_resource_by_id(task.task_id, task.id), False
        return schema.to_resource(), True

    # ----------------------------------------------------
    # Run groups by id

    async def _get_or_create_run_group(  # noqa: C901
        self,
        group: TaskGroupDocument,
        run_is_external: bool,
        user: Optional[UserIdentifier],
        disable_autosave: bool | None = None,
    ) -> TaskGroupDocument:
        if not group.hash or not group.task_id or not group.properties or not group.tenant:
            raise ValueError("Invalid group")

        group_filter = {
            "hash": group.hash,
            "task_id": group.task_id,
            "task_schema_id": group.task_schema_id,
            **self._tenant_filter(),
        }

        async def _find_group() -> Optional[TaskGroupDocument]:
            grp = await self._task_run_group_collection.find_one(group_filter)
            if not grp:
                return None
            try:
                return TaskGroupDocument.model_validate(grp)
            except ValidationError:
                # ValidationError can occur if the iteration is missing, which happens
                # in between the 2 steps below
                return None

        # If the group exists with the provided hash, then we can just return it
        existing = await _find_group()
        if existing:
            return existing
        if run_is_external:
            # When the run is external (aka the tenant that created the run is not the current tenant)
            # the task group is not stored. So we return a group with iteration 0
            return TaskGroupDocument(
                properties=group.properties,
                hash="-",
                alias="",
                iteration=0,
                is_external=True,
            )

        # Otherwise we have to create it

        # Making sure the alias is not empty
        group.alias = group.alias or group.hash

        if user:
            group.created_by = UserIdentifierSchema.from_domain(user)

        # Inserting the group
        try:
            # Inserting group without iteration, we insert the group first to make sure we will
            # not get collisions before setting the iteration
            res = await self._task_run_group_collection.insert_one(dump_model(group, exclude={"iteration"}))
            group.id = res.inserted_id
            # Computing the latest iteration
            iteration = await self._task_run_group_idx_collection.find_one_and_update(
                {"task_id": group.task_id, **self._tenant_filter()},
                {"$inc": {"latest_iteration": 1}},
                projection={"latest_iteration": 1},
                return_document=True,
                upsert=True,
            )

            if not iteration:
                # Should not happen since we are upserting
                raise InternalError("Iteration not found", filter={"task_id": group.task_id, **self._tenant_filter()})

            group.iteration = iteration["latest_iteration"]
        except DuplicateKeyError as e:
            # Group can already exist in race conditions so we return the existing one
            found = await _find_group()
            if found:
                return found

            # We retry once after a sleep just in case in case we need to let the index settle
            # or if we caught
            await asyncio.sleep(0.1)
            found = await _find_group()
            if found:
                return found

            raise InternalError(
                f"No group for filter {json.dumps(group_filter)} when creating {group}",
                group_filter=group_filter,
            ) from e

        try:
            await self._task_run_group_collection.update_one(
                {"_id": res.inserted_id},
                {"$set": {"iteration": group.iteration}},
            )
        except DuplicateKeyError as e:
            found = await _find_group()
            if found:
                logger.exception(
                    "Duplicate key error when setting group iteration",
                    extra={"found": found, "group": group},
                )
                return found
            raise InternalError("Could not set group iteration", group=group) from e

        self.event_router(
            TaskGroupCreated(
                task_id=group.task_id,
                task_schema_id=group.task_schema_id,
                id=group.hash,
                disable_autosave=disable_autosave,
            ),
        )

        return group

    # TODO: remove this method when we can get rid of the CLI
    @deprecated("Use task_groups.get_task_group_by_iteration instead")
    @override
    async def task_group_by_id(
        self,
        task_id: str,
        task_schema_id: int,
        ref: int | VersionEnvironment | TaskGroupIdentifier,
    ) -> TaskGroup:
        logger.error(
            "Calling task_group_by_id is deprecated",
            extra={"group": ref, "task_id": task_id},
        )
        if isinstance(ref, int):
            return await self.task_groups.get_task_group_by_iteration(task_id, task_schema_id, ref)
        if isinstance(ref, VersionEnvironment):
            dep = await self.task_deployments.get_task_deployment(task_id, task_schema_id, ref)  # type:ignore
            return dep.to_task_group()
        return await self.task_groups.get_task_group_by_id(task_id, ref)

    # ----------------------------------------------------
    # Task Runs

    @override
    async def prepare_task_run(
        self,
        task: SerializableTaskVariant,
        run: SerializableTaskRun,
        user: UserIdentifier | None,
        source: SourceType | None,
    ) -> SerializableTaskRun:
        # if the task has no schema id, we make sure the task is registered
        if not task.task_schema_id:
            logger.warning("Task schema id not found, storing task")
            task, _ = await self.store_task_resource(task)

        if not task.task_uid:
            # This is always true for now, we should re-enable this warning when all task variants have a uid
            # logger.warning("Task uid not found, fetching task info")
            try:
                info = await self.tasks.get_task_info(task.task_id)
                task.task_uid = info.uid
            except ObjectNotFoundException:
                logger.exception("Task info not found, skipping task uid assignment", extra={"task_id": task.task_id})

        task_document = TaskVariantDocument.from_resource(self._tenant, task)
        run.task_schema_id = task_document.schema_id
        run.task_uid = task.task_uid

        if run.example_id:
            example_id: Optional[ObjectId] = object_id(run.example_id)
        else:
            existing_example = await self._task_examples_collections.find_one(
                {
                    "task.id": run.task_id,
                    "task.schema_id": run.task_schema_id,
                    "task_input_hash": run.task_input_hash,
                    **self._tenant_filter(),
                },
            )
            example_id = existing_example["_id"] if existing_example else None

        run_is_external = run.author_tenant is not None and run.author_tenant != self._tenant

        group = TaskGroupDocument.from_resource(
            self._tenant,
            task_id=task_document.slug,
            task_schema_id=task.task_schema_id,
            resource=run.group,
        )
        group.tenant_uid = self._tenant_uid
        group = await self._get_or_create_run_group(group, run_is_external=run_is_external, user=user)

        run.group = group.to_resource()
        run.is_active = source.is_active if source else None
        run.is_external = run_is_external
        run.example_id = str(example_id) if example_id else None

        return run

    # ----------------------------------------------------
    # Examples

    @override
    async def example_resource_by_id(self, example_id: str) -> SerializableTaskExample:
        doc = await self._task_examples_collections.find_one({"_id": object_id(example_id), **self._tenant_filter()})
        if not doc:
            raise ObjectNotFoundException(f"Example {example_id} not found", code="example_not_found")
        task_example_schema = TaskExampleDocument.model_validate(doc)
        return task_example_schema.to_resource()

    async def store_example_resource(
        self,
        task: SerializableTaskVariant,
        example: SerializableTaskExample,
    ) -> SerializableTaskExample:
        # if the task has no schema id, we make sure the task is registered
        if not task.task_schema_id:
            task, _ = await self.store_task_resource(task)
        stored = TaskExampleDocument.from_resource(self._tenant, task, example)
        result = await self._task_examples_collections.insert_one(dump_model(stored))
        example.id = str(result.inserted_id)

        run_filter = {
            "task_input_hash": example.task_input_hash,
            "task.id": task.task_id,
            "task.schema_id": task.task_schema_id,
            **self._tenant_filter(),
        }

        # Update matching task runs
        await self._task_runs_collection.update_many(
            run_filter,
            {"$set": {"example_id": str(result.inserted_id)}},
        )

        try:
            await self.task_inputs.attach_example(
                task_id=example.task_id,
                task_schema_id=example.task_schema_id,
                input_hash=example.task_input_hash,
                example_id=example.id,
                example_preview=example.task_output_preview,
            )
        except ObjectNotFoundException:
            pass

        return example

    async def get_schema_id(
        self,
        task_id: str,
        task_uid: int,
        task_input_version: str,
        task_output_version: str,
    ) -> int:
        schema_id = f"{task_input_version}/{task_output_version}"

        async def _find_existing():
            # TODO[uid]: switch to uid filter
            return await self._task_schema_id_collection.find_one({"slug": task_id, **self._tenant_filter()})

        doc = await _find_existing()
        if not doc:
            # There is no task schema idx record for the given task id -> we can create it
            inserting = TaskSchemaIdDocument(
                tenant_uid=self._tenant_uid,
                task_uid=task_uid,
                slug=task_id,
                tenant=self._tenant,
                latest_idx=1,
                idx_mapping={schema_id: 1},
            )

            try:
                await self._task_schema_id_collection.insert_one(dump_model(inserting))
                return 1
            except DuplicateKeyError:
                # We have to fetch the existing record, DuplicateKeyError can happen in race conditions
                doc = await _find_existing()
                if not doc:
                    raise ValueError("DuplicateKeyError but no record found")

        indices = TaskSchemaIdDocument.model_validate(doc)
        # We return the already existing mapping if possible
        try:
            return indices.idx_mapping[schema_id]
        except KeyError:
            pass

        new_idx = indices.latest_idx + 1

        # Otherwise we create a new one
        updated = await self._task_schema_id_collection.update_one(
            {"slug": task_id, "latest_idx": indices.latest_idx, **self._tenant_filter()},
            {
                "$set": {
                    "latest_idx": new_idx,
                    f"idx_mapping.{schema_id}": new_idx,
                },
            },
        )

        if updated.modified_count != 1:
            # TODO: retry, could be race condition
            raise ObjectNotFoundException(
                f"No schema idx record updated for {task_id} and {schema_id}",
                code="schema_not_found",
            )

        return new_idx

    @override
    async def fetch_example_resources(
        self,
        query: SerializableTaskExampleQuery,
    ) -> AsyncIterator[SerializableTaskExample]:
        filter = TaskExampleDocument.build_filter(self._tenant, query)
        project = TaskExampleDocument.build_project(query)

        if query.sort_by == SerializableTaskExampleQuery.SortBy.RANDOM:
            res: AsyncCursor = self._task_examples_collections.aggregate(
                [{"$match": filter}, {"$sample": {"size": query.limit}}],
            )
        elif query.unique_by:
            # We have to use an aggregation
            pipeline: list[dict[str, Any]] = [
                {"$match": filter},
                {"$group": {"_id": f"${query.unique_by}", "doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$doc"}},
            ]
            if query.limit:
                pipeline.append({"$limit": query.limit})
            if project:
                pipeline.insert(1, {"$project": project})

            res = self._task_examples_collections.aggregate(pipeline)
        else:
            res = self._task_examples_collections.find(filter, project)
            if query.limit:
                res = res.limit(query.limit)
            if query.offset:
                res = res.skip(query.offset)

            res = res.sort(*TaskExampleDocument.sort_by(query.sort_by))

        task_example_schema: Optional[TaskExampleDocument] = None
        async for doc in res.batch_size(100):
            task_example_schema = TaskExampleDocument.model_validate(doc)
            yield task_example_schema.to_resource()

    @override
    async def count_examples(self, query: SerializableTaskExampleQuery) -> int:
        # TODO: update count when using the aggregation pipeline ?
        filter = TaskExampleDocument.build_filter(self._tenant, query)
        return await self._task_examples_collections.count_documents(filter)

    @override
    async def delete_example(self, example_id: str) -> SerializableTaskExample:
        # Remove example
        example = await self._task_examples_collections.find_one_and_delete(
            {"_id": object_id(example_id)},
            projection={"task_input": 0, "task_output": 0},
        )
        if not example:
            raise ObjectNotFoundException(f"Example {example_id} not found", code="example_not_found")

        # TODO: when we add training sets:,
        # training set the example belongs to should be updated
        # Resets all task runs that reference this example
        await self._task_runs_collection.update_many(
            {
                "example_id": example_id,
                "task.id": example["task"]["id"],
                "task.schema_id": example["task"]["schema_id"],
                **self._tenant_filter(),
            },
            {"$unset": {"example_id": "", "corrections": ""}},
        )

        try:
            await self.task_inputs.detach_example(
                task_id=example["task"]["id"],
                task_schema_id=example["task"]["schema_id"],
                input_hash=example["task_input_hash"],
                example_id=str(example["_id"]),
            )
        except ObjectNotFoundException:
            pass

        return TaskExampleDocument.model_validate(example).to_resource()

    # TODO[uid]: add task_uid
    @override
    async def get_or_create_task_group(
        self,
        task_id: str,
        task_schema_id: int,
        properties: TaskGroupProperties,
        tags: list[str],
        is_external: Optional[bool] = None,
        id: Optional[str] = None,
        user: Optional[UserIdentifier] = None,
        disable_autosave: bool | None = None,
    ) -> TaskGroup:
        doc = TaskGroupDocument(
            hash=properties.model_hash(),
            task_id=task_id,
            tenant_uid=self._tenant_uid,
            task_schema_id=task_schema_id,
            properties=properties.model_dump(exclude_none=True),
            tags=tags,
            tenant=self._tenant,
            alias=id or "",
            iteration=0,
            is_external=is_external,
            similarity_hash=properties.similarity_hash,
        )

        created = await self._get_or_create_run_group(
            doc,
            run_is_external=False,
            user=user,
            disable_autosave=disable_autosave,
        )
        return created.to_resource()

    @override
    async def delete_task(self, task_id: str) -> None:
        # Remove task
        await self._task_variants_collection.delete_many({"slug": task_id, **self._tenant_filter()})
        # Remove task runs
        await self._task_runs_collection.delete_many({"task.id": task_id, **self._tenant_filter()})
        # Remove task examples
        await self._task_examples_collections.delete_many({"task.id": task_id, **self._tenant_filter()})
        # Remove task schema idx
        await self._task_schema_id_collection.delete_many({"slug": task_id, **self._tenant_filter()})
        # Remove task run group idx
        await self._task_run_group_idx_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        # Remove task run groups
        await self._task_run_group_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        # Remove task schemas
        await self._task_schemas_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        # Remove task benchmarks
        await self._task_benchmarks_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        # Remove task evaluators
        await self._task_evaluators_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        # Remove task inputs
        await self._task_inputs_collection.delete_many({"task.id": task_id, **self._tenant_filter()})
        # Remove task info
        await self._tasks_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        # Remove task changelogs
        await self._changelogs_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        # Remove dataset benchmarks
        await self._dataset_benchmarks_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        # Remove input evaluations
        await self._input_evaluations_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        await self._reviews_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        await self._review_benchmarks_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        await self._task_deployments_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        await self._task_group_semvers_collection.delete_many({"task_id": task_id, **self._tenant_filter()})
        await self._feedback_collection.delete_many({"task_id": task_id, **self._tenant_uid_filter()})

    @override
    async def get_inputs_by_hash(
        self,
        task_id: str,
        task_schema_id: int,
        input_hashes: set[str],
        exclude_fields: set[TaskInputFields] | None = None,
    ) -> AsyncIterator[TaskInput]:
        project = {"task_input": 1, "task_input_hash": 1, "task_input_preview": 1}
        if exclude_fields:
            for field in exclude_fields:
                if field in project:
                    del project[field]

        collections = [self._task_inputs_collection, self._task_examples_collections, self._task_runs_collection]

        hash_set = set(input_hashes)  # Copy to avoid modifying the input

        for c in collections:
            filter = {
                "task.id": task_id,
                "task.schema_id": task_schema_id,
                "task_input_hash": next(iter(hash_set)) if len(hash_set) == 1 else {"$in": list(hash_set)},
                **self._tenant_filter(),
            }

            async for doc in c.find(filter, projection=project):
                yield TaskInput.model_validate(doc)
                hash_set.remove(doc["task_input_hash"])

    @override
    async def get_any_input_by_hash(self, task_id: str, task_schema_id: int, input_hash: str) -> TaskInput:
        async for doc in self.get_inputs_by_hash(task_id, task_schema_id, {input_hash}):
            return doc
        raise ObjectNotFoundException(
            f"Agent input with hash {input_hash} not found for {task_id} and {task_schema_id}",
            code="agent_input_not_found",
        )

    @override
    async def set_task_description(self, task_id: str, description: str) -> None:
        await self._tasks_collection.update_one(
            {"task_id": task_id, **self._tenant_filter()},
            update={"$set": {"description": description}},
        )

    @override
    async def get_latest_idx(self, task_id: str) -> int:
        doc = await self._task_schema_id_collection.find_one({"slug": task_id, **self._tenant_filter()})
        return doc["latest_idx"] if doc else 0

    @override
    async def get_latest_group_iteration(self, task_id: str) -> int:
        doc = await self._task_run_group_idx_collection.find_one({"task_id": task_id, **self._tenant_filter()})
        return doc["latest_iteration"] if doc else 0

    @override
    async def store_task_run_resource(
        self,
        task: SerializableTaskVariant,
        run: SerializableTaskRun,
        user: UserIdentifier | None,
        source: SourceType | None,
    ) -> SerializableTaskRun:
        run = await self.prepare_task_run(task, run, user, source)
        return await self.task_runs.store_task_run(run)
