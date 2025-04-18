from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from pymongo.errors import DuplicateKeyError

from core.domain.ban import Ban
from core.domain.task_info import TaskInfo
from core.storage import ObjectNotFoundException
from core.storage.models import TaskUpdate
from core.storage.mongo.models.task_document import TaskDocument
from core.storage.mongo.mongo_storage import MongoStorage
from core.storage.mongo.mongo_types import AsyncCollection
from core.storage.mongo.partials.mongo_tasks import MongoTaskStorage
from core.storage.mongo.partials.task_variants import MongoTaskVariantsStorage
from core.storage.mongo.utils import dump_model


@pytest.fixture(scope="function")
def mock_task_variants_storage():
    return Mock(spec=MongoTaskVariantsStorage)


@pytest.fixture(scope="function")
def task_storage(storage: MongoStorage, mock_task_variants_storage: Mock):
    tasks = storage.tasks
    tasks._task_variants = mock_task_variants_storage  # pyright: ignore [reportPrivateUsage]
    return tasks


class TestUnique:
    async def test_uid_unique(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        await tasks_col.insert_one({"task_id": "bla", "tenant": "test_tenant", "uid": 1})

        with pytest.raises(DuplicateKeyError):
            await tasks_col.insert_one({"task_id": "bla1", "tenant": "tenant1", "uid": 1})

    async def test_uid_upsert(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        inserted = await tasks_col.insert_one({"task_id": "bla", "tenant": "test_tenant", "uid": 1})

        # Updating existing task should not change the uid
        await task_storage.update_task("bla", TaskUpdate(is_public=True))

        updated = await tasks_col.find_one({"uid": 1})
        assert updated and updated["_id"] == inserted.inserted_id

        await task_storage.update_task("blabli", TaskUpdate(is_public=False))
        upserted = await tasks_col.find_one({"task_id": "blabli"})
        assert upserted and upserted["uid"]


class TestSetTaskPublic:
    async def test_not_exist(
        self,
        task_storage: MongoTaskStorage,
        tasks_col: AsyncCollection,
        mock_task_variants_storage: Mock,
    ):
        assert await tasks_col.find_one({"task_id": "bla"}) is None

        await task_storage.update_task("bla", TaskUpdate(is_public=True))

        doc = await tasks_col.find_one({"task_id": "bla"})
        assert doc
        assert doc["tenant"] == "test_tenant"
        assert doc["is_public"] is True

        mock_task_variants_storage.update_task.assert_called_once_with("bla", True, None)

    async def test_exist(
        self,
        task_storage: MongoTaskStorage,
        tasks_col: AsyncCollection,
        mock_task_variants_storage: Mock,
    ):
        await tasks_col.insert_one({"task_id": "bla", "tenant": "test_tenant", "is_public": False})

        await task_storage.update_task("bla", TaskUpdate(is_public=True))

        doc = await tasks_col.find_one({"task_id": "bla"})
        assert doc
        assert doc["tenant"] == "test_tenant"
        assert doc["is_public"] is True

        mock_task_variants_storage.update_task.assert_called_once_with("bla", True, None)


class TestIsTaskPublic:
    async def test_not_exist(self, task_storage: MongoTaskStorage):
        assert await task_storage.is_task_public("bla") is False

    async def test_exist(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        await tasks_col.insert_one({"task_id": "bla", "tenant": "test_tenant", "is_public": True})

        assert await task_storage.is_task_public("bla") is True

    async def test_flow(self, task_storage: MongoTaskStorage):
        assert await task_storage.is_task_public("bla") is False

        await task_storage.update_task("bla", TaskUpdate(is_public=True))

        assert await task_storage.is_task_public("bla") is True

        await task_storage.update_task("bla", TaskUpdate(is_public=False))

        assert await task_storage.is_task_public("bla") is False


class TestIsTaskBanned:
    async def test_is_task_banned(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        banned_at = datetime(2024, 1, 1, 0, 0, 0, 0, timezone.utc)

        await task_storage.update_task(
            "task_id",
            TaskUpdate(
                ban=Ban(
                    reason="task_run_non_compliant",
                    related_ids=["run1"],
                    banned_at=banned_at,
                ),
            ),
        )

        doc = await tasks_col.find_one({"task_id": "task_id"})
        assert doc
        assert doc["ban"] == {
            "reason": "task_run_non_compliant",
            "related_ids": ["run1"],
            "banned_at": banned_at,
        }


class TestTaskHide:
    async def test_hide(self, task_storage: MongoTaskStorage):
        await task_storage.update_task("bla", TaskUpdate(hide_schema=1))

        info = await task_storage.get_task_info("bla")
        assert info.uid
        info = TaskInfo(
            uid=info.uid,
            task_id="bla",
            name="",
            is_public=False,
            hidden_schema_ids=[1],
        )

        await task_storage.update_task("bla", TaskUpdate(unhide_schema=1))

        assert await task_storage.get_task_info("bla") == TaskInfo(
            uid=info.uid,
            task_id="bla",
            name="",
            is_public=False,
            hidden_schema_ids=[],
        )


class TestSchemaLastActiveAt:
    # task_storage is added first to make sure the collection is cleaned up
    @pytest.fixture(autouse=True)
    async def inserted_task_doc(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        doc = TaskDocument(task_id="bla", tenant="test_tenant")
        await tasks_col.insert_one(dump_model(doc))
        return doc

    async def test_update_last_active_at(self, task_storage: MongoTaskStorage):
        now = datetime.now(timezone.utc)
        await task_storage.update_task("bla", TaskUpdate(schema_last_active_at=(1, now)))

        actual = await task_storage.get_task_info("bla")
        assert actual.schema_details is not None
        assert len(actual.schema_details) == 1
        assert actual.schema_details[0].schema_id == 1
        assert actual.schema_details[0].last_active_at
        assert abs(actual.schema_details[0].last_active_at - now) < timedelta(seconds=1)

    async def test_update_last_active_at_twice(self, task_storage: MongoTaskStorage):
        now = datetime.now(timezone.utc)
        await task_storage.update_task_schema_details("bla", 1, now - timedelta(minutes=20))
        await task_storage.update_task_schema_details("bla", 1, now)
        await task_storage.update_task_schema_details("bla", 1, now)

        actual = await task_storage.get_task_info("bla")
        assert actual.schema_details is not None
        assert len(actual.schema_details) == 1
        assert actual.schema_details[0].schema_id == 1
        assert actual.schema_details[0].last_active_at
        assert abs(actual.schema_details[0].last_active_at - now) < timedelta(seconds=1)

    async def test_update_last_active_at_with_different_schema_id(self, task_storage: MongoTaskStorage):
        now = datetime.now(timezone.utc)
        await task_storage.update_task("bla", TaskUpdate(schema_last_active_at=(1, now - timedelta(minutes=20))))
        await task_storage.update_task("bla", TaskUpdate(schema_last_active_at=(2, now)))

        actual = await task_storage.get_task_info("bla")
        assert actual.schema_details is not None
        assert len(actual.schema_details) == 2
        assert actual.schema_details[0].schema_id == 1
        assert actual.schema_details[1].schema_id == 2
        assert actual.schema_details[0].last_active_at
        assert abs(actual.schema_details[0].last_active_at - (now - timedelta(minutes=20))) < timedelta(seconds=1)
        assert actual.schema_details[1].last_active_at
        assert abs(actual.schema_details[1].last_active_at - now) < timedelta(seconds=1)

        await task_storage.update_task("bla", TaskUpdate(schema_last_active_at=(1, now)))

        actual = await task_storage.get_task_info("bla")
        assert actual.schema_details is not None
        assert len(actual.schema_details) == 2
        assert actual.schema_details[0].schema_id == 1
        assert actual.schema_details[1].schema_id == 2
        assert actual.schema_details[0].last_active_at
        assert actual.schema_details[1].last_active_at
        assert abs(actual.schema_details[0].last_active_at - now) < timedelta(seconds=1)
        assert abs(actual.schema_details[1].last_active_at - now) < timedelta(seconds=1)


class TestGetPublicTaskInfo:
    async def test_get_public_task_info_success(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        # Create a task document with all required fields
        doc = TaskDocument(
            task_id="test_task",
            name="Test Task",
            is_public=True,
            tenant="test_tenant",
            tenant_uid=1,
            uid=123,
        )
        await tasks_col.insert_one(dump_model(doc))

        # Get the public task info
        result = await task_storage.get_public_task_info(123)

        # Verify the result
        assert result.task_id == "test_task"
        assert result.name == "Test Task"
        assert result.is_public is True
        assert result.tenant == "test_tenant"
        assert result.tenant_uid == 1
        assert result.uid == 123

    async def test_get_public_task_info_not_found(self, task_storage: MongoTaskStorage):
        with pytest.raises(ObjectNotFoundException) as exc_info:
            await task_storage.get_public_task_info(999)
        assert str(exc_info.value) == "Task with uid 999 not found"


class TestUpdateTaskBefore:
    async def test_update_task_before_true(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        # Insert initial task
        initial_task = TaskDocument(
            task_id="test_task",
            name="Initial Name",
            is_public=False,
            tenant="test_tenant",
        )
        await tasks_col.insert_one(dump_model(initial_task))

        # Update task with before=True
        update = TaskUpdate(name="New Name", is_public=True)
        result = await task_storage.update_task("test_task", update, before=True)

        # Verify the result is the document before the update
        assert result.name == "Initial Name"
        assert result.is_public is False

        # Verify the document in the database was actually updated
        doc = await tasks_col.find_one({"task_id": "test_task"})
        assert doc is not None
        assert doc["name"] == "New Name"
        assert doc["is_public"] is True

    async def test_update_task_before_false(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        # Insert initial task
        initial_task = TaskDocument(
            task_id="test_task",
            name="Initial Name",
            is_public=False,
            tenant="test_tenant",
        )
        await tasks_col.insert_one(dump_model(initial_task))

        # Update task with before=False (default)
        update = TaskUpdate(name="New Name", is_public=True)
        result = await task_storage.update_task("test_task", update, before=False)

        # Verify the result is the document after the update
        assert result.name == "New Name"
        assert result.is_public is True

        # Verify the document in the database matches
        doc = await tasks_col.find_one({"task_id": "test_task"})
        assert doc is not None
        assert doc["name"] == "New Name"
        assert doc["is_public"] is True

    async def test_update_task_before_upsert(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        # Try to update non-existent task with before=True
        # The task wil not be upserted
        update = TaskUpdate(name="New Task", is_public=True)
        with pytest.raises(ObjectNotFoundException):
            await task_storage.update_task("non_existent", update, before=True)

        # Verify the document was created in the database
        doc = await tasks_col.find_one({"task_id": "non_existent"})
        assert doc is None


class TestActiveTasks:
    async def _setup_tasks(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection, now: datetime):
        tasks = [
            TaskDocument(
                task_id="task1",
                name="Task 1",
                is_public=True,
                tenant="test_tenant",
                tenant_uid=1,
                uid=101,
                schema_details=[
                    TaskDocument.SchemaDetails(
                        schema_id=1,
                        last_active_at=now - timedelta(days=1),
                    ),
                ],
            ),
            TaskDocument(
                task_id="task2",
                name="Task 2",
                is_public=True,
                tenant="test_tenant",
                tenant_uid=1,
                uid=102,
                schema_details=[
                    TaskDocument.SchemaDetails(
                        schema_id=1,
                        last_active_at=now - timedelta(hours=1),
                    ),
                ],
            ),
            TaskDocument(
                task_id="task3",
                name="Task 3",
                is_public=True,
                tenant="test_tenant",
                tenant_uid=1,
                uid=103,
                schema_details=[
                    TaskDocument.SchemaDetails(
                        schema_id=1,
                        last_active_at=now - timedelta(minutes=30),
                    ),
                ],
            ),
            TaskDocument(
                task_id="task4",
                name="Task 4",
                is_public=False,  # Not public, should not be returned
                tenant="test_tenant",
                tenant_uid=1,
                uid=104,
                schema_details=[
                    TaskDocument.SchemaDetails(
                        schema_id=1,
                        last_active_at=now - timedelta(minutes=15),
                    ),
                ],
            ),
        ]
        await tasks_col.insert_many([dump_model(task) for task in tasks])

    async def test_active_tasks_since(
        self,
        task_storage: MongoTaskStorage,
        tasks_col: AsyncCollection,
    ):
        # Create some test tasks with different last_active_at timestamps
        now = datetime.now(timezone.utc)
        await self._setup_tasks(task_storage, tasks_col, now)

        t2h_ago = {t.task_id async for t in task_storage.active_tasks(now - timedelta(hours=2))}
        assert t2h_ago == {"task2", "task3", "task4"}, "2h ago, task2 and task3 should be active"

        t1h_ago = {t.task_id async for t in task_storage.active_tasks(now - timedelta(minutes=59))}
        assert t1h_ago == {"task3", "task4"}, "1h ago, task3 and task4 should be active"

        t1d_ago = {t.task_id async for t in task_storage.active_tasks(now - timedelta(days=1))}
        assert t1d_ago == {"task1", "task2", "task3", "task4"}, "1d ago, all tasks should be active"

    async def test_active_tasks_with_multiple_schemas(self, task_storage: MongoTaskStorage, tasks_col: AsyncCollection):
        now = datetime.now(timezone.utc)
        # Create a task with multiple schema details
        task = TaskDocument(
            task_id="multi_schema_task",
            name="Multi Schema Task",
            is_public=True,
            tenant="test_tenant",
            tenant_uid=1,
            uid=105,
            schema_details=[
                TaskDocument.SchemaDetails(
                    schema_id=1,
                    last_active_at=now - timedelta(days=2),
                ),
                TaskDocument.SchemaDetails(
                    schema_id=2,
                    last_active_at=now - timedelta(hours=1),
                ),
            ],
        )
        await tasks_col.insert_one(dump_model(task))

        since = now - timedelta(days=1)
        task_ids = {t.task_id async for t in task_storage.active_tasks(since)}
        assert task_ids == {"multi_schema_task"}
