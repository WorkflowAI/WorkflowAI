from typing import AsyncIterator, Protocol

from core.domain.changelogs import VersionChangelog


class ChangeLogStorage(Protocol):
    async def insert_changelog(self, changelog: VersionChangelog) -> VersionChangelog: ...

    def list_changelogs(
        self,
        task_id: str,
        task_schema_id: int | None,
    ) -> AsyncIterator[VersionChangelog]: ...
