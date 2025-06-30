from typing import Any

from core.domain.integration.integration_domain import IntegrationKind
from core.domain.task_variant import SerializableTaskVariant
from core.storage import ObjectNotFoundException, TenantTuple
from core.storage.mongo.models.task_variant import TaskVariantDocument
from core.storage.mongo.mongo_types import AsyncCollection
from core.storage.mongo.partials.base_partial_storage import PartialStorage


class MongoTaskVariantsStorage(PartialStorage[TaskVariantDocument]):
    def __init__(self, tenant: TenantTuple, collection: AsyncCollection):
        super().__init__(tenant, collection, TaskVariantDocument)

    async def update_task(
        self,
        task_id: str,
        is_public: bool | None = None,
        name: str | None = None,
        used_integration_kind: IntegrationKind | None = None,
    ):
        update: dict[str, Any] = {}
        if is_public is not None:
            update["is_public"] = is_public
        if name is not None:
            update["name"] = name
        if used_integration_kind is not None:
            update["used_integration_kind"] = used_integration_kind

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
        doc = await self._find_one(filter={"task_uid": task_uid}, sort=[("created_at", -1)])
        if doc:
            return TaskVariantDocument.model_validate(doc).to_resource()
        raise ObjectNotFoundException(f"Task variant with uid {task_uid} not found")

    async def variants_iterator(self, agent_id: str, variant_ids: set[str]):
        async for doc in self._find(filter={"slug": agent_id, "version": {"$in": list(variant_ids)}}):
            yield doc.to_resource()
