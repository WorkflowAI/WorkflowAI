from typing import override

from core.storage.mongo.migrations.base import AbstractMigration


class FixOrgIndexMigration(AbstractMigration):
    @override
    async def apply(self):
        # There was a typo in the index field
        await self._drop_index_if_exists(self._organization_collection, "anonymous_user_id_and_user_id_unique")

        # Anonymous user id is unique
        await self._organization_collection.create_index(
            [
                ("anonymous_user_id", 1),
            ],
            unique=True,
            name="anonymous_user_id_unique",
            partialFilterExpression={"anonymous_user_id": {"$exists": True}},
        )

    @override
    async def rollback(self):
        # Nothing to rollback the index was useless anyway
        pass
