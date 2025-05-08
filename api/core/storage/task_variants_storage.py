from typing import Protocol

from core.domain.task_variant import SerializableTaskVariant


class TaskVariantsStorage(Protocol):
    async def update_task(self, task_id: str, is_public: bool | None = None, name: str | None = None): ...

    async def get_latest_task_variant(
        self,
        task_id: str,
        schema_id: int | None = None,
    ) -> SerializableTaskVariant | None: ...

    async def get_task_variant_by_uid(self, task_uid: int) -> SerializableTaskVariant: ...
