from datetime import datetime

from core.domain.task_info import TaskInfo


class TestIsActive:
    def test_no_schema_details(self):
        task_info = TaskInfo(task_id="test_task")
        assert not task_info.is_active

    def test_schema_details_empty(self):
        task_info = TaskInfo(task_id="test_task", schema_details=[])
        assert not task_info.is_active

    def test_all_schemas_inactive(self):
        task_info = TaskInfo(
            task_id="test_task",
            schema_details=[
                TaskInfo.SchemaDetails(schema_id=1, last_active_at=None),
                TaskInfo.SchemaDetails(schema_id=2, last_active_at=None),
            ],
        )
        assert not task_info.is_active

    def test_one_schema_active(self):
        task_info = TaskInfo(
            task_id="test_task",
            schema_details=[
                TaskInfo.SchemaDetails(schema_id=1, last_active_at=None),
                TaskInfo.SchemaDetails(schema_id=2, last_active_at=datetime.now()),
            ],
        )
        assert task_info.is_active

    def test_all_schemas_active(self):
        task_info = TaskInfo(
            task_id="test_task",
            schema_details=[
                TaskInfo.SchemaDetails(schema_id=1, last_active_at=datetime.now()),
                TaskInfo.SchemaDetails(schema_id=2, last_active_at=datetime.now()),
            ],
        )
        assert task_info.is_active
