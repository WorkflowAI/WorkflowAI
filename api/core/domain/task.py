import datetime
from typing import Any

from pydantic import BaseModel

from core.domain.task_info import TaskInfo


class SerializableTask(BaseModel):
    id: str
    name: str
    description: str | None = None
    is_public: bool | None = False
    tenant: str = ""

    # TODO: not implemented yet, add when we can perform aggregations
    average_cost_usd: float | None = None
    run_count: int | None = None

    class PartialTaskVersion(BaseModel):
        schema_id: int
        variant_id: str
        description: str | None = None
        input_schema_version: str
        input_schema: dict[str, Any] | None = None
        output_schema_version: str
        output_schema: dict[str, Any] | None = None
        # Using default value to account for backwards compatibility
        created_at: datetime.datetime = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        is_hidden: bool | None = None
        last_active_at: datetime.datetime | None = None

    versions: list[PartialTaskVersion]
    uid: int = 0

    def enrich(self, task_info: TaskInfo):
        self.name = task_info.name
        self.description = task_info.description
        self.is_public = task_info.is_public
        hidden_schema_ids = set(task_info.hidden_schema_ids or [])
        self.uid = task_info.uid
        for version in self.versions:
            version.is_hidden = version.schema_id in hidden_schema_ids
            schema_details = task_info.get_schema_details(version.schema_id)
            version.last_active_at = schema_details.last_active_at if schema_details else None
