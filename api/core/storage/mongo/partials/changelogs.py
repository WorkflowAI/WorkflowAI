import logging
from typing import Any

from core.domain.changelogs import VersionChangelog
from core.storage import TenantTuple
from core.storage.mongo.models.changelog import ChangeLogDocument
from core.storage.mongo.mongo_types import AsyncCollection
from core.storage.mongo.partials.base_partial_storage import PartialStorage

logger = logging.getLogger(__name__)


class MongoChangeLogStorage(PartialStorage[ChangeLogDocument]):
    def __init__(self, tenant: TenantTuple, collection: AsyncCollection):
        super().__init__(tenant, collection, ChangeLogDocument)

    async def insert_changelog(self, changelog: VersionChangelog) -> VersionChangelog:
        doc = ChangeLogDocument.from_domain(changelog)
        res = await self._insert_one(doc)
        return res.to_domain()

    async def list_changelogs(self, task_id: str, task_schema_id: int | None):
        filter: dict[str, Any] = {"task_id": task_id}
        if task_schema_id:
            filter["task_schema_id"] = task_schema_id

        async for doc in self._find(filter):
            yield doc.to_domain()
