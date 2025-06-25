from core.storage.mongo.migrations.base import AbstractMigration


class FixAPIKeyIdIndexMigration(AbstractMigration):
    async def apply(self):
        # Drop the old index with incorrect partial filter expression
        await self._drop_index_if_exists(self._organization_collection, "org_settings_api_key_id_index")

        # Create new index with correct partial filter expression
        await self._organization_collection.create_index(
            [("api_keys.id", 1)],
            name="unique_api_key_id",
            unique=True,
            partialFilterExpression={
                "api_keys.id": {"$exists": True},
            },
        )

    async def rollback(self):
        # Drop the new index
        await self._drop_index_if_exists(self._organization_collection, "unique_api_key_id")

        # Recreate the old index with the problematic partial filter expression
        await self._organization_collection.create_index(
            [("api_keys.id", 1)],
            name="org_settings_api_key_id_index",
            unique=True,
            background=True,
            partialFilterExpression={"api_keys": {"$exists": True}},
        )
