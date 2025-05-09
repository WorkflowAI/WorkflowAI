from typing import Any

from core.domain.task_variant import SerializableTaskVariant
from core.storage import ObjectNotFoundException, TenantTuple
from core.storage.mongo.models.task_variant import TaskVariantDocument
from core.storage.mongo.mongo_types import AsyncCollection
from core.storage.mongo.partials.base_partial_storage import PartialStorage


class MongoTaskVariantsStorage(PartialStorage[TaskVariantDocument]):
    def __init__(self, tenant: TenantTuple, collection: AsyncCollection):
        super().__init__(tenant, collection, TaskVariantDocument)

    async def update_task(self, task_id: str, is_public: bool | None = None, name: str | None = None):
        update: dict[str, Any] = {}
        if is_public is not None:
            update["is_public"] = is_public
        if name is not None:
            update["name"] = name

        await self._update_many(
            filter={"slug": task_id},
            update={"$set": update},
        )

    async def get_latest_task_variant(
        self,
        task_id: str,
        schema_id: int | None = None,
    ) -> SerializableTaskVariant | None:
        try:
            filter: dict[str, Any] = {"slug": task_id}
            if schema_id is not None:
                filter["schema_id"] = schema_id
            doc = await self._find_one(
                filter=filter,
                sort=[("schema_id", -1), ("created_at", -1)],
            )
        except ObjectNotFoundException:
            return None

        if doc:
            return TaskVariantDocument.model_validate(doc).to_resource()

        return None

    async def get_task_variant_by_uid(self, task_uid: int) -> SerializableTaskVariant:
        doc = await self._find_one(filter={"task_uid": task_uid})
        if doc:
            return TaskVariantDocument.model_validate(doc).to_resource()
        raise ObjectNotFoundException(f"Task variant with uid {task_uid} not found")
