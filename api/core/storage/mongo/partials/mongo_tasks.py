from datetime import datetime
from typing import Any, Protocol, override

from core.domain.task_info import TaskInfo
from core.storage import ObjectNotFoundException, TenantTuple
from core.storage.models import TaskUpdate
from core.storage.mongo.models.task_document import TaskDocument
from core.storage.mongo.mongo_types import AsyncCollection
from core.storage.mongo.partials.base_partial_storage import PartialStorage
from core.storage.mongo.utils import dump_model
from core.storage.task_storage import TaskStorage
from core.utils.ids import id_uint32


class _PartialTaskVariantStorage(Protocol):
    async def update_task(self, task_id: str, is_public: bool | None, name: str | None): ...


class MongoTaskStorage(PartialStorage[TaskDocument], TaskStorage):
    def __init__(
        self,
        tenant: TenantTuple,
        collection: AsyncCollection,
        task_variants: _PartialTaskVariantStorage,
    ):
        super().__init__(tenant, collection, TaskDocument)
        self._task_variants = task_variants

    @override
    async def is_task_public(self, task_id: str) -> bool:
        result = await self._collection.find_one(
            filter={"task_id": task_id, "is_public": True, "tenant": self._tenant},
            projection={"_id": 1},
        )
        return result is not None

    @override
    async def get_task_info(self, task_id: str) -> TaskInfo:
        doc = await self._find_one(
            filter={"task_id": task_id},
        )
        return doc.to_domain()

    async def update_task_schema_details(self, task_id: str, schema_id: int, last_active_at: datetime):
        try:
            await self._update_one(
                filter={"task_id": task_id, "schema_details": {"$elemMatch": {"schema_id": schema_id}}},
                update={"$set": {"schema_details.$.last_active_at": last_active_at}},
            )
        except ObjectNotFoundException:
            # This can happen the first time we update the last_active_at for a schema
            pass

        try:
            await self._update_one(
                filter={"task_id": task_id, "schema_details.schema_id": {"$ne": schema_id}},
                update={
                    "$push": {
                        "schema_details": dump_model(
                            TaskDocument.SchemaDetails(
                                schema_id=schema_id,
                                last_active_at=last_active_at,
                            ),
                        ),
                    },
                },
            )
        except ObjectNotFoundException:
            # This can happen in race conditions
            pass

    @override
    async def update_task(self, task_id: str, update: TaskUpdate, before: bool = False):
        _set: dict[str, Any] = {}
        if update.is_public is not None:
            _set["is_public"] = update.is_public
        if update.name is not None:
            _set["name"] = update.name
        if update.description is not None:
            _set["description"] = update.description

        update_ops: dict[str, dict[str, Any]] = {"$set": _set}

        if update.hide_schema is not None:
            update_ops["$addToSet"] = {"hidden_schema_ids": update.hide_schema}
        if update.unhide_schema is not None:
            update_ops["$pull"] = {"hidden_schema_ids": update.unhide_schema}
        if update.schema_last_active_at is not None:
            await self.update_task_schema_details(
                task_id,
                update.schema_last_active_at[0],
                update.schema_last_active_at[1],
            )
        if update.ban is not None:
            update_ops["$set"] = {"ban": update.ban.model_dump()}

        uid = id_uint32()
        update_ops["$setOnInsert"] = {"uid": uid, "tenant_uid": self._tenant_uid}

        doc = await self._find_one_and_update(
            filter={"task_id": task_id},
            update=update_ops,
            upsert=not before,
            return_document=not before,
        )

        # TODO:We should not have to update the task variant here
        await self._task_variants.update_task(task_id, update.is_public, update.name)
        return doc.to_domain()

    def _public_task_projection(self):
        return {"task_id": 1, "name": 1, "is_public": 1, "tenant": 1, "tenant_uid": 1, "uid": 1}

    @override
    async def get_public_task_info(self, task_uid: int):
        doc = await self._collection.find_one(
            filter={"uid": task_uid},
            projection=self._public_task_projection(),
        )
        if doc is None:
            raise ObjectNotFoundException(f"Task with uid {task_uid} not found")
        return TaskDocument.model_validate(doc).to_public_domain()

    @override
    async def active_tasks(self, since: datetime):
        async for doc in self._collection.find(
            filter={"schema_details.last_active_at": {"$gte": since}},
            projection=self._public_task_projection(),
        ):
            yield TaskDocument.model_validate(doc).to_public_domain()
