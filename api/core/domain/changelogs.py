from pydantic import BaseModel


class VersionChangelog(BaseModel):
    task_id: str
    task_schema_id: int

    major_from: int
    major_to: int
    similarity_hash_from: str
    similarity_hash_to: str

    changelog: list[str]
