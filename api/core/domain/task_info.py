from datetime import datetime

from pydantic import BaseModel

from core.domain.ban import Ban
from core.storage import TaskTuple


class PublicTaskInfo(BaseModel):
    uid: int = 0
    task_id: str
    name: str = ""
    is_public: bool = False
    # TODO[uids]: remove once we don't need the string tenant anymore
    tenant: str = ""
    tenant_uid: int = 0


class TaskInfo(BaseModel):
    uid: int = 0
    task_id: str
    name: str = ""
    description: str | None = None
    is_public: bool = False
    hidden_schema_ids: list[int] | None = None

    class SchemaDetails(BaseModel):
        schema_id: int = 0
        last_active_at: datetime | None = None

    schema_details: list[SchemaDetails] | None = None
    ban: Ban | None = None

    def get_schema_details(self, schema_id: int) -> SchemaDetails | None:
        try:
            return next(detail for detail in self.schema_details or [] if detail.schema_id == schema_id)
        except StopIteration:
            return None

    @property
    def is_active(self) -> bool:
        if not self.schema_details:
            return False
        return any(detail.last_active_at for detail in self.schema_details)

    @property
    def id_tuple(self) -> TaskTuple:
        return (self.task_id, self.uid)

    @property
    def latest_schema_id(self) -> int:
        if not self.schema_details:
            return 0
        return max(detail.schema_id for detail in self.schema_details)
