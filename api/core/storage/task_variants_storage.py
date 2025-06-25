from collections.abc import AsyncIterator
from typing import Protocol

from core.domain.integration.integration_domain import IntegrationKind
from core.domain.task_variant import SerializableTaskVariant


class TaskVariantsStorage(Protocol):
    async def update_task(
        self,
        task_id: str,
        is_public: bool | None = None,
        name: str | None = None,
        used_integration_kind: IntegrationKind | None = None,
    ): ...

    async def get_latest_task_variant(
        self,
        task_id: str,
        schema_id: int | None = None,
    ) -> SerializableTaskVariant | None: ...

    async def get_task_variant_by_uid(self, task_uid: int) -> SerializableTaskVariant: ...

    def variants_iterator(self, agent_id: str, variant_ids: set[str]) -> AsyncIterator[SerializableTaskVariant]: ...
