# pyright: reportPrivateUsage=false

import asyncio
import datetime
import uuid
from enum import Enum
from typing import Any, Counter, Optional
from unittest.mock import Mock, PropertyMock, patch
from zoneinfo import ZoneInfo

import pytest
from bson import ObjectId
from motor.motor_asyncio import (
    AsyncIOMotorClient,
)
from pydantic import BaseModel

from core.domain.analytics_events.analytics_events import SourceType
from core.domain.fields.local_date_time import DatetimeLocal
from core.domain.fields.zone_info import TimezoneInfo
from core.domain.task import SerializableTask
from core.domain.task_example_query import SerializableTaskExampleQuery
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.users import UserIdentifier
from core.storage import ObjectNotFoundException
from core.storage.mongo.models.pyobjectid import PyObjectID
from core.storage.mongo.models.task_document import TaskDocument
from core.storage.mongo.models.task_example import TaskExampleDocument
from core.storage.mongo.models.task_group import TaskGroupDocument
from core.storage.mongo.models.task_group_idx import TaskGroupIterations
from core.storage.mongo.models.task_input import TaskInputDocument
from core.storage.mongo.models.task_io import TaskIOSchema
from core.storage.mongo.models.task_metadata import TaskMetadataSchema
from core.storage.mongo.models.task_run_document import TaskRunDocument
from core.storage.mongo.models.task_schema_id_document import TaskSchemaIdDocument
from core.storage.mongo.models.task_variant import TaskVariantDocument
from core.storage.mongo.mongo_storage import MongoStorage
from core.storage.mongo.mongo_types import AsyncClient, AsyncCollection
from core.storage.mongo.utils import dump_model, extract_connection_info
from core.storage.task_input_storage import TaskInputsStorage
from core.utils import no_op
from core.utils.encryption import Encryption
from tests.models import task_example_ser, task_variant

TENANT = "test_tenant"
TASK_ID = "task_id"

USER = UserIdentifier(user_id="1234", user_email="test@test.com")


class ModelWithDate(BaseModel):
    date: datetime.date


class ModelWithDatetime(BaseModel):
    datetime: datetime.datetime


class ModelWithTime(BaseModel):
    time: datetime.time


class ModelWithTimezone(BaseModel):
    timezone: TimezoneInfo


class ModelWithURL(BaseModel):
    url: str


class ModelWithLocalDateTime(BaseModel):
    local_datetime: DatetimeLocal


class ModelWithEnum(BaseModel):
    class Category(Enum):
        SAD = "SAD"
        HAPPY = 1

    category: Category


@pytest.mark.parametrize(
    "obj",
    [
        ModelWithDate(date=datetime.date(2021, 1, 1)),
        ModelWithDatetime(datetime=datetime.datetime(2021, 1, 1, 10, 1, tzinfo=datetime.timezone.utc)),
        ModelWithTime(time=datetime.time(10, 0)),
        ModelWithTimezone(timezone=ZoneInfo("Europe/Paris")),
        ModelWithURL(url="http://example.com"),
        ModelWithLocalDateTime(
            local_datetime=DatetimeLocal(
                date=datetime.date(2021, 1, 1),
                local_time=datetime.time(10, 0),
                timezone=ZoneInfo("Europe/Paris"),
            ),
        ),
        ModelWithEnum(category=ModelWithEnum.Category.HAPPY),
        ModelWithEnum(category=ModelWithEnum.Category.SAD),
    ],
)
async def test_insert_and_retrieve(collection: AsyncCollection, obj: BaseModel) -> None:
    # Test that we can insert and retrieve models with different attribute types
    response = await collection.insert_one(obj.model_dump())
    id = response.inserted_id
    raw = await collection.find_one({"_id": id})
    assert raw is not None
    del raw["_id"]
    retrieved = obj.__class__(**raw)
    assert retrieved == obj


async def test_timezones_are_preserved(collection: AsyncCollection) -> None:
    response = await collection.insert_one(
        {
            "datetime": datetime.datetime(2021, 1, 1, 10, 1, tzinfo=ZoneInfo("Europe/Paris")),
        },
    )
    raw = await collection.find_one({"_id": response.inserted_id})
    model = ModelWithDatetime.model_validate(raw)
    assert model.datetime.isoformat() == "2021-01-01T09:01:00+00:00"


async def test_get_schema_id(storage: MongoStorage) -> None:
    # No idx exists for the task -> it is created
    task_id = str(uuid.uuid4())
    idx = await storage.get_schema_id(task_id, 1, "1", "2")
    assert idx == 1

    doc = await storage._task_schema_id_collection.find_one({"slug": task_id})  # pyright: ignore[reportPrivateUsage]
    assert doc is not None
    assert "tenant_uid" in doc
    assert "task_uid" in doc
    # Re-retrieving the schema -> not incremented
    idx = await storage.get_schema_id(task_id, 1, "1", "2")
    assert idx == 1

    # Changing the schema
    idx = await storage.get_schema_id(task_id, 1, "3", "4")
    assert idx == 2


def _task_metadata(id: Optional[str] = None, schema_id: Optional[int] = None, **kwargs: Any) -> TaskMetadataSchema:
    schema = TaskMetadataSchema(
        id=id or TASK_ID,
        schema_id=schema_id or 1,
        input_class_version="input_v1",
        output_class_version="output_v1",
    )
    return TaskMetadataSchema.model_validate({**schema.model_dump(exclude_none=True), **kwargs})


def _task_run(
    task_id: Optional[str] = None,
    task_schema_id: Optional[int] = None,
    version_id: Optional[str] = None,
    model: Optional[str] = None,
    iteration: int = 1,
    task_input: dict[str, Any] = {"hello": "workdli"},
    task_output: dict[str, Any] = {"hello": "workdli"},
    created_at: datetime.datetime = datetime.datetime(2024, 4, 16, tzinfo=datetime.timezone.utc),
    updated_at: datetime.datetime = datetime.datetime(2024, 4, 16, tzinfo=datetime.timezone.utc),
    **kwargs: Any,
) -> TaskRunDocument:
    schema = TaskRunDocument(
        _id=kwargs.get("id", str(uuid.uuid4())),
        tenant=TENANT,
        task=_task_metadata(id=task_id, schema_id=task_schema_id),
        task_input_hash=str(uuid.uuid4()),
        task_input=task_input,
        task_output_hash=str(uuid.uuid4()),
        task_output=task_output,
        created_at=created_at,
        group=TaskRunDocument.Group(
            alias=version_id or "group_alias",
            hash=version_id or "group_hash",
            iteration=iteration,
            properties={"hello": "world", "model": model},
            tags=["bla"],
        ),
    )
    return TaskRunDocument.model_validate({**schema.model_dump(by_alias=True), **kwargs})


def _task_example(
    task_id: Optional[str] = None,
    task_schema_id: Optional[int] = None,
    **kwargs: Any,
) -> TaskExampleDocument:
    schema = TaskExampleDocument(
        tenant=TENANT,
        task=_task_metadata(id=task_id, schema_id=task_schema_id),
        task_input_hash=str(uuid.uuid4()),
        task_input={"hello": "world"},
        task_input_preview='hello: "world"',
        task_output_hash=str(uuid.uuid4()),
        task_output={"hello": "world"},
        task_output_preview='hello: "world"',
    )

    return TaskExampleDocument.model_validate({**schema.model_dump(by_alias=True), "_id": ObjectId(), **kwargs})


def _task_input(
    task_id: Optional[str] = None,
    task_schema_id: Optional[int] = None,
    **kwargs: Any,
) -> TaskInputDocument:
    schema = TaskInputDocument(
        tenant=TENANT,
        task=_task_metadata(id=task_id, schema_id=task_schema_id),
        task_input_hash=str(uuid.uuid4()),
        task_input={"hello": "world"},
        task_input_preview='hello: "world"',
    )

    return TaskInputDocument.model_validate({**schema.model_dump(by_alias=True), "_id": ObjectId(), **kwargs})


def _task_info(**kwargs: Any) -> TaskDocument:
    doc = TaskDocument(
        task_id=TASK_ID,
        name="task_name",
        description="task_description",
        is_public=True,
        tenant=TENANT,
    )
    return TaskDocument.model_validate({**doc.model_dump(by_alias=True), **kwargs})


def _task_variant(
    tenant: str = TENANT,
    task_schema_id: str | int = 1,
    task_id: str = TASK_ID,
    **kwargs: Any,
) -> TaskVariantDocument:
    doc = TaskVariantDocument(
        _id=kwargs.get("id", str(uuid.uuid4())),
        version=str(uuid.uuid4()),
        slug=task_id,
        schema_id=int(task_schema_id),
        name="task_name",
        input_schema=TaskIOSchema(version="input_version", json_schema={}),
        output_schema=TaskIOSchema(version="output_version", json_schema={}),
        tenant=tenant,
    )
    return TaskVariantDocument.model_validate({**doc.model_dump(by_alias=True), **kwargs})


# def _task_schema(schema_id: int = 1, **kwargs: Any) -> TaskSchemaDocument:
#     doc = TaskSchemaDocument(
#         task_id=TASK_ID,
#         schema_id=schema_id,
#         tenant=TENANT,
#     )
#     return TaskSchemaDocument.model_validate({**doc.model_dump(by_alias=True), **kwargs})


def _task_schema_id(**kwargs: Any) -> TaskSchemaIdDocument:
    doc = TaskSchemaIdDocument(slug=TASK_ID, latest_idx=1, idx_mapping={}, tenant=TENANT)
    return TaskSchemaIdDocument.model_validate({**doc.model_dump(by_alias=True), **kwargs})


def _task_group(
    iteration: int = 1,
    task_schema_id: int = 1,
    tenant: str = TENANT,
    **kwargs: Any,
) -> TaskGroupDocument:
    doc = TaskGroupDocument(
        hash=str(uuid.uuid4()),
        task_id=TASK_ID,
        task_schema_id=task_schema_id,
        iteration=iteration,
        alias=str(uuid.uuid4()),
        properties={"model": "model"},
        tags=["bla"],
        tenant=tenant,
    )
    return TaskGroupDocument.model_validate({**doc.model_dump(by_alias=True), **kwargs})


def _task_group_idx(**kwargs: Any) -> TaskGroupIterations:
    doc = TaskGroupIterations(
        task_id=TASK_ID,
        latest_iteration=1,
        tenant=TENANT,
    )
    return TaskGroupIterations.model_validate({**doc.model_dump(by_alias=True), **kwargs})


class TestIsReady:
    async def test_is_ready(self, mock_encryption: Encryption, mongo_test_uri: str) -> None:
        clt: AsyncClient = AsyncIOMotorClient(
            extract_connection_info(mongo_test_uri)[0],
            tlsCAFile=None,
            serverSelectionTimeoutMS=5,
        )  # type: ignore
        storage = MongoStorage(
            tenant=TENANT,
            client=clt,
            event_router=no_op.event_router,
            encryption=mock_encryption,
            db_name="workflowai",
        )
        assert await storage.is_ready()

    async def test_is_not_ready(self, mock_encryption: Encryption) -> None:
        not_the_uri = "mongodb://localhost:27018/workflowai"
        clt: AsyncClient = AsyncIOMotorClient(not_the_uri, tlsCAFile=None, serverSelectionTimeoutMS=5)  # type: ignore
        storage = MongoStorage(
            tenant=TENANT,
            client=clt,
            event_router=no_op.event_router,
            encryption=mock_encryption,
            db_name="workflowai",
        )
        assert await storage.is_ready() is False


class TestPrepareTaskRun:
    async def test_no_existing_example(
        self,
        storage: MongoStorage,
        task_example_col: AsyncCollection,
        task_run_col: AsyncCollection,
        task_run_group_col: AsyncCollection,
        task_variants_col: AsyncCollection,
    ):
        task_run = _task_run()
        examples = [
            # Different tenant
            _task_example(task_input_hash=task_run.task_input_hash, tenant="t1"),
            # Different task id
            _task_example(task_input_hash=task_run.task_input_hash, task_id="t2"),
            # Different task schema
            _task_example(task_input_hash=task_run.task_input_hash, task_schema_id=2),
            # Different input hash
            _task_example(task_input_hash="2"),
        ]

        await task_example_col.insert_many([dump_model(a) for a in examples])
        stored = await storage.prepare_task_run(
            _task_variant().to_resource(),
            task_run.to_resource(),
            USER,
            SourceType.API,
        )

        assert stored.is_active is True

    async def test_external_run(self, storage: MongoStorage, task_run_group_col: AsyncCollection):
        task_run = _task_run(author_tenant="another_tenant")
        stored = await storage.prepare_task_run(
            _task_variant().to_resource(),
            task_run.to_resource(),
            USER,
            None,
        )

        assert stored.group.iteration == 0
        assert stored.group.id == "-"
        assert stored.is_active is None

        assert (await task_run_group_col.count_documents({})) == 0


class TestFetchTasks:
    async def _fetch_tasks(self, storage: MongoStorage) -> list[SerializableTask]:
        return [a async for a in storage.fetch_tasks()]

    async def test_fetch_tasks_with_no_tasks(self, storage: MongoStorage):
        tasks = await self._fetch_tasks(storage)
        assert tasks == []

    async def test_fetch_tasks(self, storage: MongoStorage, task_variants_col: AsyncCollection):
        await task_variants_col.insert_many(
            [
                dump_model(
                    TaskVariantDocument(
                        _id=PyObjectID.new(),
                        version="v1",
                        tenant=TENANT,
                        slug="1",
                        schema_id=1,
                        name="Task1",
                        input_schema=TaskIOSchema(version="input_v1", json_schema={}),
                        output_schema=TaskIOSchema(version="output_v1", json_schema={}),
                        created_at=datetime.datetime(2024, 4, 16, tzinfo=datetime.timezone.utc),
                        is_public=True,
                    ),
                ),
                {
                    "_id": "2",
                    "version": "v2",
                    "tenant": TENANT,
                    "slug": "1",
                    "schema_id": 2,
                    "input_schema": {"version": "input_v2", "json_schema": {}},
                    "output_schema": {"version": "output_v2", "json_schema": {}},
                    "is_public": True,
                },
            ],
        )

        tasks = await self._fetch_tasks(storage)
        assert tasks == [
            SerializableTask(
                id="1",
                name="Task1",
                is_public=True,
                versions=[
                    SerializableTask.PartialTaskVersion(
                        schema_id=1,
                        variant_id="v1",
                        input_schema_version="input_v1",
                        output_schema_version="output_v1",
                        created_at=datetime.datetime(2024, 4, 16, tzinfo=datetime.timezone.utc),
                    ),
                    SerializableTask.PartialTaskVersion(
                        schema_id=2,
                        variant_id="v2",
                        input_schema_version="input_v2",
                        output_schema_version="output_v2",
                        created_at=datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc),
                    ),
                ],
            ),
        ]

    async def test_fetch_tasks_with_schemas(self, storage: MongoStorage, task_variants_col: AsyncCollection):
        input_schema = {
            "type": "object",
            "properties": {"input": {"type": "string", "description": "Input field"}},
            "required": ["input"],
        }
        output_schema = {
            "type": "object",
            "properties": {"output": {"type": "string", "description": "Output field"}},
            "required": ["output"],
        }

        await task_variants_col.insert_many(
            [
                dump_model(
                    TaskVariantDocument(
                        _id=PyObjectID.new(),
                        version="v1",
                        tenant=TENANT,
                        slug="1",
                        schema_id=1,
                        name="Task1",
                        input_schema=TaskIOSchema(version="input_v1", json_schema=input_schema),
                        output_schema=TaskIOSchema(version="output_v1", json_schema=output_schema),
                        created_at=datetime.datetime(2024, 4, 16, tzinfo=datetime.timezone.utc),
                        is_public=True,
                    ),
                ),
                {
                    "_id": "2",
                    "version": "v2",
                    "tenant": TENANT,
                    "slug": "1",
                    "schema_id": 2,
                    "input_schema": {"version": "input_v2", "json_schema": input_schema},
                    "output_schema": {"version": "output_v2", "json_schema": output_schema},
                    "is_public": True,
                },
            ],
        )

        tasks = [a async for a in storage.fetch_tasks(with_schemas=True)]
        assert len(tasks) == 1
        task = tasks[0]

        assert task.id == "1"
        assert task.name == "Task1"
        assert task.is_public is True
        assert len(task.versions) == 2

        # Check that schemas are included in the response
        for version in task.versions:
            assert version.input_schema == input_schema
            assert version.output_schema == output_schema

        # Verify specific version details
        v1_version = next(v for v in task.versions if v.variant_id == "v1")
        v2_version = next(v for v in task.versions if v.variant_id == "v2")

        assert v1_version.schema_id == 1
        assert v1_version.input_schema_version == "input_v1"
        assert v1_version.output_schema_version == "output_v1"
        assert v1_version.created_at == datetime.datetime(2024, 4, 16, tzinfo=datetime.timezone.utc)

        assert v2_version.schema_id == 2
        assert v2_version.input_schema_version == "input_v2"
        assert v2_version.output_schema_version == "output_v2"
        assert v2_version.created_at == datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


# Even though storage is not used here, adding as a dependency will make sure that
# it is cleaned up before the fixture is ran
@pytest.fixture(scope="function")
async def inserted_examples(task_example_col: AsyncCollection, storage: MongoStorage) -> list[TaskExampleDocument]:
    examples = [_task_example() for _ in range(3)]
    await task_example_col.insert_many([dump_model(a) for a in examples])
    return examples


class TestDeleteExample:
    @pytest.fixture(scope="function")
    async def patched_task_inputs(self, storage: MongoStorage):
        with patch.object(storage.__class__, "task_inputs", new_callable=PropertyMock) as mock_property:
            mock = Mock(spec=TaskInputsStorage)
            mock_property.return_value = mock
            yield mock

    async def test_delete_example(
        self,
        task_run_col: AsyncCollection,
        storage: MongoStorage,
        inserted_examples: list[TaskExampleDocument],
        patched_task_inputs: Mock,
    ):
        example_id = str(inserted_examples[0].id)
        task_run = _task_run(example_id=example_id)
        example = await task_run_col.insert_one(dump_model(task_run))
        assert example

        deleted = await storage.delete_example(example_id)
        assert deleted
        assert deleted.id == str(inserted_examples[0].id)

        patched_task_inputs.detach_example.assert_called_once_with(
            task_id=TASK_ID,
            task_schema_id=1,
            input_hash=inserted_examples[0].task_input_hash,
            example_id=str(example_id),
        )

    async def test_not_exist(
        self,
        storage: MongoStorage,
    ):
        with pytest.raises(ObjectNotFoundException):
            await storage.delete_example("6639a2d4b1057aa2c44de73f")


class TestStoreExampleResource:
    @pytest.fixture(scope="function")
    async def patched_task_inputs(self, storage: MongoStorage):
        with patch.object(storage.__class__, "task_inputs", new_callable=PropertyMock) as mock_property:
            mock = Mock(spec=TaskInputsStorage)
            mock_property.return_value = mock
            yield mock

    async def test_runs_updated(self, storage: MongoStorage, task_run_col: AsyncCollection, patched_task_inputs: Mock):
        task_runs = [
            # Updated
            _task_run(id="1", task=_task_metadata(id="t1"), example_id=None, task_input_hash="1"),
            # not updated because id don't match
            _task_run(id="2", task=_task_metadata(id="t2"), task_input_hash="1"),
            # not updated because schema ids don't match
            _task_run(id="3", task=_task_metadata(id="t1", schema_id=2), task_input_hash="1"),
            # not updated because input hashes don't match
            _task_run(id="4", task=_task_metadata(id="t1"), task_input_hash="2"),
            # Updated
            _task_run(id="5", task=_task_metadata(id="t1"), example_id=None, task_input_hash="1"),
        ]
        await task_run_col.insert_many([dump_model(a) for a in task_runs])

        variant = task_variant(task_id="t1", task_schema_id=1)
        example = task_example_ser(task_id="t1", task_schema_id=1, task_input_hash="1")

        await storage.store_example_resource(variant, example)

        runs = [r async for r in task_run_col.find({"example_id": example.id})]
        assert {r["_id"] for r in runs} == {"1", "5"}

        patched_task_inputs.attach_example.assert_called_once_with(
            task_id="t1",
            task_schema_id=1,
            input_hash="1",
            example_id=str(example.id),
            example_preview="output: 1",
        )


class TestDeleteTask:
    async def test_exhaustive(self, storage: MongoStorage, all_collections: list[AsyncCollection]) -> None:
        non_task_collections = {"migrations", "org_settings", "transcriptions"}
        all_collections = [col for col in all_collections if col.name not in non_task_collections]
        for col in all_collections:
            doc: dict[str, Any] = {"tenant": TENANT, "tenant_uid": 1}
            match col.name:
                case "tasks" | "task_schema_id":
                    doc["slug"] = TASK_ID
                case "task_runs" | "task_examples" | "task_inputs":
                    doc["task"] = {"id": TASK_ID}
                case _:
                    doc["task_id"] = TASK_ID

            await col.insert_one(doc)

        for col in all_collections:
            assert await col.count_documents({}) == 1, "sanity"

        await storage.delete_task(TASK_ID)

        for col in all_collections:
            assert await col.count_documents({}) == 0, f"{col.name} was not deleted"

    async def test_delete_task(
        self,
        task_example_col: AsyncCollection,
        task_run_col: AsyncCollection,
        task_run_group_col: AsyncCollection,
        task_run_group_idx_col: AsyncCollection,
        task_variants_col: AsyncCollection,
        task_schema_id_col: AsyncCollection,
        storage: MongoStorage,
    ) -> None:
        # Create 3 items in each col:
        # - 1 with the task that will be deleted
        # - 1 with a different tenant
        # - 1 with a different task id
        await task_example_col.insert_many(
            [
                dump_model(_task_example()),
                dump_model(_task_example(tenant="t2")),
                dump_model(_task_example(task=_task_metadata(id="2"))),
            ],
        )
        await task_run_col.insert_many(
            [
                dump_model(_task_run()),
                dump_model(_task_run(tenant="t2")),
                dump_model(_task_run(task=_task_metadata(id="2"))),
            ],
        )
        await task_run_group_col.insert_many(
            [
                dump_model(_task_group()),
                dump_model(_task_group(tenant="t2")),
                dump_model(_task_group(task_id="2")),
            ],
        )

        await task_run_group_idx_col.insert_many(
            [
                dump_model(_task_group_idx()),
                dump_model(_task_group_idx(tenant="t2")),
                dump_model(_task_group_idx(task_id="2")),
            ],
        )

        await task_variants_col.insert_many(
            [
                dump_model(_task_variant()),
                dump_model(_task_variant(slug="2")),
                dump_model(_task_variant(tenant="t2")),
            ],
        )

        await task_schema_id_col.insert_many(
            [
                dump_model(_task_schema_id()),
                dump_model(_task_schema_id(slug="2")),
                dump_model(_task_schema_id(tenant="t2")),
            ],
        )

        await storage.delete_task(TASK_ID)

        collections = [task_example_col, task_run_col, task_run_group_col, task_variants_col, task_schema_id_col]
        for col in collections:
            # Only 1 item must have been deleted for each collection
            assert await col.count_documents({}) == 2
            assert await col.count_documents({"tenant": TENANT}) == 1
            assert await col.count_documents({"tenant": "t2"}) == 1


def _ex_query(task_id: str = TASK_ID, task_schema_id: int = 1, **kwargs: Any) -> SerializableTaskExampleQuery:
    return SerializableTaskExampleQuery(
        task_id=task_id,
        task_schema_id=task_schema_id,
        **kwargs,
    )


class TestFetchExampleResources:
    @pytest.fixture(scope="function")
    async def examples(self, task_example_col: AsyncCollection, storage: MongoStorage) -> list[TaskExampleDocument]:
        examples = [
            _task_example(),
            _task_example(task_input_hash="2"),
            _task_example(task_input_hash="2"),
            _task_example(task_id="2"),
            _task_example(task_schema_id=2),
        ]
        res = await task_example_col.insert_many([dump_model(a) for a in examples])
        for i, ex in enumerate(examples):
            ex.id = res.inserted_ids[i]
        return examples

    @pytest.mark.parametrize(
        "query,expected",  # expected is a set of example idx in the examples list
        [
            (_ex_query(), {0, 1, 2}),
            (_ex_query(exclude_fields={"task_input"}), {0, 1, 2}),
            (_ex_query(unique_by="task_input_hash"), {0, 1}),
            (_ex_query(exclude_fields={"task_output"}), {0, 1, 2}),
        ],
    )
    async def test_fetch_example_resources(
        self,
        examples: list[TaskExampleDocument],
        storage: MongoStorage,
        query: SerializableTaskExampleQuery,
        expected: set[int],
    ) -> None:
        fetched = [a async for a in storage.fetch_example_resources(query)]
        assert len(fetched) == len(expected)

        idx_set = set[int]()
        for ex in fetched:
            if query.exclude_fields:
                if "task_input" not in query.exclude_fields:
                    assert ex.task_input
                if "task_output" not in query.exclude_fields:
                    assert ex.task_output
            # get the index of the example in the examples list
            try:
                idx = next(i for i, e in enumerate(examples) if str(e.id) == str(ex.id))
            except StopIteration:
                assert False, f"Example with id {ex.id} not found in the examples list"
            idx_set.add(idx)

        assert idx_set == expected


class TestListTaskGroups:
    @pytest.fixture(scope="function")
    async def test_groups(self, storage: MongoStorage, task_run_group_col: AsyncCollection) -> list[TaskGroupDocument]:
        groups = [
            _task_group(),
            _task_group(iteration=2, properties={"task_schema_id": 1}),
            _task_group(iteration=1, tenant="t2"),
            _task_group(iteration=2, task_id="2"),
        ]
        await task_run_group_col.insert_many([dump_model(a) for a in groups])
        return groups


class TestGetOrCreateTaskGroup:
    async def test_non_existing(self, storage: MongoStorage, task_run_group_col: AsyncCollection) -> None:
        group = await storage.get_or_create_task_group(TASK_ID, 1, TaskGroupProperties(model="h1"), [], None)
        assert group.iteration == 1

        doc = await task_run_group_col.find_one({"task_id": TASK_ID, "task_schema_id": 1, "iteration": 1})
        assert doc
        # TODO[uid]: add task_uid
        # assert "task_uid" in doc
        doc["tenant_uid"] = 1
        assert TaskGroupDocument.model_validate(doc).to_resource() == group

        group_1 = await storage.get_or_create_task_group(TASK_ID, 1, TaskGroupProperties(model="h1"), [], None)
        assert group_1.iteration == 1
        assert group_1.id == group.id

    async def test_new_properties(self, storage: MongoStorage) -> None:
        group = await storage.get_or_create_task_group(TASK_ID, 1, TaskGroupProperties(model="h1"), [], None)
        assert group.iteration == 1

        group_1 = await storage.get_or_create_task_group(TASK_ID, 1, TaskGroupProperties(model="h2"), [], None)
        assert group_1.iteration == 2
        assert group_1.id != group.id
        assert group_1.properties == TaskGroupProperties(model="h2")

        group_2 = await storage.get_or_create_task_group(TASK_ID, 1, TaskGroupProperties(model="h1"), [], None)
        assert group_2.iteration == 1
        assert group_2.id == group.id

    async def test_new_schema_id(self, storage: MongoStorage) -> None:
        group = await storage.get_or_create_task_group(TASK_ID, 1, TaskGroupProperties(model="h1"), [], None)
        assert group.iteration == 1

        group_1 = await storage.get_or_create_task_group(TASK_ID, 2, TaskGroupProperties(model="h1"), [], None)
        assert group_1.iteration == 2
        assert group_1.id == group.id  # By default the id is equal to a hash of the properties

    async def test_similarity_hash(self, storage: MongoStorage, task_run_group_col: AsyncCollection) -> None:
        group = await storage.get_or_create_task_group(TASK_ID, 1, TaskGroupProperties(model="h1"), [], None)
        assert group.similarity_hash

        # now fetch the doc directly from the db
        doc = await task_run_group_col.find_one({"task_id": TASK_ID, "task_schema_id": 1, "iteration": 1})
        assert doc
        assert doc["iteration"] == 1, "sanity"
        assert doc["properties"] == {"model": "h1"}, "sanity"
        assert doc["similarity_hash"] == group.similarity_hash


class TestGetOrCreateRunGroup:
    async def test_race_conditions(self, storage: MongoStorage) -> None:
        grps = [_task_group(hash=f"{i}", iteration=0, alias=f"{i}") for i in range(3)]
        grps = grps * 3

        async def _insert_with_rand_delay(grp: TaskGroupDocument) -> None:
            # Sleep between 0 and 100 ms
            # await asyncio.sleep(random.randint(0, 100) / 1000.0)
            await storage._get_or_create_run_group(  # pyright: ignore [reportPrivateUsage]
                grp,
                run_is_external=False,
                user=UserIdentifier(user_id="123", user_email="test@test.com"),
            )

        vals = await asyncio.gather(*[_insert_with_rand_delay(grp) for grp in grps])
        assert len(vals) == 9

        iteration_counts = Counter(g.iteration for g in grps)
        assert iteration_counts.get(1) == 3
        assert iteration_counts.get(2) == 3
        assert iteration_counts.get(3) == 3

        for g in grps:
            assert g.created_by is not None
            assert g.created_by.user_id == "123"
            assert g.created_by.user_email == "test@test.com"


class TestTaskVersionResourceByID:
    async def test_task_version_by_id(self, storage: MongoStorage, task_variants_col: AsyncCollection) -> None:
        task = _task_variant()
        await task_variants_col.insert_one(dump_model(task))

        res = await storage.task_version_resource_by_id(TASK_ID, task.version)
        assert res
        assert res.id == task.version

        with pytest.raises(ObjectNotFoundException):
            await storage.task_version_resource_by_id("bla", task.version)


class TestStoreTaskResource:
    async def test_no_task_info(
        self,
        storage: MongoStorage,
        task_variants_col: AsyncCollection,
        tasks_col: AsyncCollection,
    ):
        ser = task_variant()

        stored, created = await storage.store_task_resource(ser)
        assert created

        assert stored.id
        assert stored.task_uid > 0

        task_info = await tasks_col.find_one({"tenant": TENANT, "task_id": TASK_ID})
        assert task_info is not None
        assert task_info["task_id"] == TASK_ID
        assert task_info["tenant"] == TENANT
        assert task_info["name"] == "task_name"
        assert task_info["uid"] == stored.task_uid
        assert task_info["tenant_uid"] == 1

        # I can do it again
        stored, created = await storage.store_task_resource(ser)
        assert not created

        # Check that the task info is not updated
        new_task_info = await tasks_col.find_one({"tenant": TENANT, "task_id": TASK_ID})
        assert new_task_info == task_info

        variant_doc = await task_variants_col.find_one({"tenant": TENANT, "slug": TASK_ID})
        assert variant_doc is not None
        assert variant_doc["tenant_uid"] == 1
        assert variant_doc["task_uid"] == stored.task_uid

    async def test_existing_task_info(
        self,
        storage: MongoStorage,
        task_variants_col: AsyncCollection,
        tasks_col: AsyncCollection,
    ):
        await tasks_col.insert_one(
            dump_model(TaskDocument(tenant=TENANT, task_id=TASK_ID, uid=10, name="another_task_name", is_public=True)),
        )
        task_info = await tasks_col.find_one({"tenant": TENANT, "task_id": TASK_ID})

        ser = task_variant(id="")
        stored, created = await storage.store_task_resource(ser)
        assert created

        assert stored.id
        assert stored.task_schema_id == 1
        assert stored.is_public is True
        assert stored.name == "another_task_name"
        assert stored.task_uid == 10

        # Check that the task info is not updated
        new_task_info = await tasks_col.find_one({"tenant": TENANT, "task_id": TASK_ID})
        assert new_task_info == task_info

        # Check that I can add a task with the same schema id but a different variant by adding a metadata
        new_ser = task_variant(
            id="",
            name="",
            is_public=False,
            input_schema={
                "type": "object",
                "properties": {"input": {"type": "string", "description": "hello"}},
                "required": ["input"],
            },
        )
        assert new_ser.id != ser.id, "Sanity"
        new_stored, created = await storage.store_task_resource(new_ser)
        assert created
        assert new_stored.task_schema_id == 1
        assert new_stored.id != stored.id
        assert new_stored.is_public is True
        assert new_stored.name == "another_task_name"

    async def test_store_duplicates(
        self,
        storage: MongoStorage,
        task_variants_col: AsyncCollection,
        tasks_col: AsyncCollection,
    ):
        # Check that we can store 2 identical task variants for different task ids
        ser = task_variant()
        stored, created = await storage.store_task_resource(ser)
        assert created
        assert stored.id == ser.id
        assert stored.task_id == ser.task_id

        assert await tasks_col.count_documents({}) == 1

        # Make sure the created_at is not updated
        copied = ser.model_copy(deep=True)
        copied.created_at = datetime.datetime(2024, 4, 16, tzinfo=datetime.timezone.utc)
        copied.task_id = "another"
        stored2, created = await storage.store_task_resource(copied)
        assert created

        # The id of the task variant is task_id specific...
        assert stored2.id == ser.id
        assert stored2.task_id == "another"
        assert stored2.created_at == copied.created_at != stored.created_at

        assert await tasks_col.count_documents({}) == 2

        stored_tasks = [t async for t in task_variants_col.find({})]
        assert len(stored_tasks) == 2

    async def test_update_created_at(self, storage: MongoStorage) -> None:
        ser = task_variant()
        ser.created_at = datetime.datetime(2024, 4, 15, tzinfo=datetime.timezone.utc)
        stored, created = await storage.store_task_resource(ser.model_copy())
        assert created
        assert stored.created_at == ser.created_at

        # Now update the created at and store the variant again
        ser.created_at = datetime.datetime(2025, 4, 16, tzinfo=datetime.timezone.utc)
        _, created2 = await storage.store_task_resource(ser.model_copy(), update_created_at=False)
        assert not created2
        fetched = await storage._task_variants_collection.find_one({"tenant": TENANT, "slug": TASK_ID})
        assert fetched
        assert fetched["created_at"] == datetime.datetime(2024, 4, 15, tzinfo=datetime.timezone.utc)

        # Same thing with update_created_at=True
        _, created3 = await storage.store_task_resource(ser.model_copy(), update_created_at=True)
        assert not created3
        fetched2 = await storage._task_variants_collection.find_one({"tenant": TENANT, "slug": TASK_ID})
        assert fetched2
        assert fetched2["created_at"] == datetime.datetime(2025, 4, 16, tzinfo=datetime.timezone.utc)


class TestGetInputsByHash:
    async def test_all(
        self,
        storage: MongoStorage,
        task_example_col: AsyncCollection,
        task_run_col: AsyncCollection,
        task_inputs_col: AsyncCollection,
    ):
        task_inputs = [
            _task_input(task_input_hash="1", task_input={"a": 1}),
            _task_input(task_input_hash="2", task_input={"a": 2}),
        ]
        examples = [
            _task_example(task_input_hash="1", task_input={"a": 11}),
            _task_example(task_input_hash="3", task_input={"a": 3}),
        ]
        runs = [
            _task_run(task_input_hash="2", task_input={"a": 111}),
            _task_run(task_input_hash="3", task_input={"a": 112}),
            _task_run(task_input_hash="4", task_input={"a": 4}),
        ]

        await asyncio.gather(
            task_inputs_col.insert_many([dump_model(a) for a in task_inputs]),
            task_example_col.insert_many([dump_model(a) for a in examples]),
            task_run_col.insert_many([dump_model(a) for a in runs]),
        )

        inputs = [i async for i in storage.get_inputs_by_hash(TASK_ID, 1, {"1", "2", "3", "4"})]
        assert len(inputs) == 4
        inputs.sort(key=lambda x: x.task_input_hash)

        # First two come from task_inputs
        assert inputs[0].task_input == {"a": 1}
        assert inputs[1].task_input == {"a": 2}
        # Next two come from task_examples
        assert inputs[2].task_input == {"a": 3}
        # Last one comes from task_runs
        assert inputs[3].task_input == {"a": 4}

    async def test_exclude_set(
        self,
        storage: MongoStorage,
        task_example_col: AsyncCollection,
        task_run_col: AsyncCollection,
        task_inputs_col: AsyncCollection,
    ):
        task_inputs = [
            _task_input(task_input_hash="1", task_input={"a": 1}),
            _task_input(task_input_hash="2", task_input={"a": 2}),
        ]
        examples = [
            _task_example(task_input_hash="1", task_input={"a": 11}),
            _task_example(task_input_hash="3", task_input={"a": 3}),
        ]
        runs = [
            _task_run(task_input_hash="2", task_input={"a": 111}),
            _task_run(task_input_hash="3", task_input={"a": 112}),
            _task_run(task_input_hash="4", task_input={"a": 4}),
        ]

        await asyncio.gather(
            task_inputs_col.insert_many([dump_model(a) for a in task_inputs]),
            task_example_col.insert_many([dump_model(a) for a in examples]),
            task_run_col.insert_many([dump_model(a) for a in runs]),
        )

        inputs = [i async for i in storage.get_inputs_by_hash(TASK_ID, 1, {"1", "2", "3", "4"}, {"task_input"})]
        assert len(inputs) == 4

        for i in inputs:
            assert i.task_input is None


class TestGetInputByHash:
    async def test_all(
        self,
        storage: MongoStorage,
        task_example_col: AsyncCollection,
        task_run_col: AsyncCollection,
        task_inputs_col: AsyncCollection,
    ):
        task_inputs = [
            _task_input(task_input_hash="1", task_input={"a": 1}),
        ]
        examples = [
            _task_example(task_input_hash="1", task_input={"a": 11}),
        ]
        runs = [
            _task_run(task_input_hash="2", task_input={"a": 111}),
        ]

        await asyncio.gather(
            task_inputs_col.insert_many([dump_model(a) for a in task_inputs]),
            task_example_col.insert_many([dump_model(a) for a in examples]),
            task_run_col.insert_many([dump_model(a) for a in runs]),
        )

        input = await storage.get_any_input_by_hash(TASK_ID, 1, "1")
        assert input.task_input == {"a": 1}

    async def test_from_example(
        self,
        storage: MongoStorage,
        task_example_col: AsyncCollection,
    ):
        examples = [
            _task_example(task_input_hash="1", task_input={"a": 11}),
        ]

        await task_example_col.insert_many([dump_model(a) for a in examples])

        input = await storage.get_any_input_by_hash(TASK_ID, 1, "1")
        assert input.task_input == {"a": 11}

    async def test_from_run(
        self,
        storage: MongoStorage,
        task_run_col: AsyncCollection,
    ):
        runs = [
            _task_run(task_input_hash="1", task_input={"a": 111}),
        ]

        await task_run_col.insert_many([dump_model(a) for a in runs])

        input = await storage.get_any_input_by_hash(TASK_ID, 1, "1")
        assert input.task_input == {"a": 111}


class TestGetTask:
    async def test_get_task(
        self,
        storage: MongoStorage,
        task_variants_col: AsyncCollection,
        tasks_col: AsyncCollection,
    ):
        task_info = _task_info(description="This is a test description", name="task_name", is_public=True)
        await tasks_col.insert_one(dump_model(task_info))

        tasks = [
            _task_variant(),
            _task_variant(slug="2", is_public=True),
            _task_variant(tenant="t2"),
            _task_variant(task_schema_id="2"),
        ]
        await task_variants_col.insert_many([dump_model(a) for a in tasks])

        res = await storage.get_task(TASK_ID)
        assert res
        assert res.id == TASK_ID
        assert len(res.versions) == 2
        # Test that the task is corretly "enriched" by the task_info
        assert res.name == "task_name"
        assert res.is_public is True
        assert res.description == "This is a test description"

        res = await storage.get_task("2")
        assert res
        assert res.is_public

        with pytest.raises(ObjectNotFoundException):
            await storage.get_task("bla")


class TestGetLatestGroupIteration:
    @pytest.fixture(scope="function")
    async def setup_groups(self, task_run_group_col: AsyncCollection):
        groups = [
            _task_group(task_id="task1", task_schema_id=1, iteration=1),
            _task_group(task_id="task1", task_schema_id=1, iteration=2),
            _task_group(task_id="task1", task_schema_id=1, iteration=3),
            _task_group(task_id="task1", task_schema_id=2, iteration=8),
            _task_group(task_id="task2", task_schema_id=1, iteration=1),
            _task_group(task_id="task1", task_schema_id=1, iteration=4, tenant="other_tenant"),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

    async def test_get_latest_group_iteration_exists(self, storage: MongoStorage, setup_groups: Any):
        result = await storage.task_groups.get_latest_group_iteration("task1", 1)
        assert result is not None
        assert result.schema_id == 1
        assert result.iteration == 3

    async def test_get_latest_group_iteration_different_schema(self, storage: MongoStorage, setup_groups: Any):
        result = await storage.task_groups.get_latest_group_iteration("task1", 2)
        assert result is not None
        assert result.schema_id == 2
        assert result.iteration == 8

    async def test_get_latest_group_iteration_different_task(self, storage: MongoStorage, setup_groups: Any):
        result = await storage.task_groups.get_latest_group_iteration("task2", 1)
        assert result is not None
        assert result.schema_id == 1
        assert result.iteration == 1

    async def test_get_latest_group_iteration_not_exists(self, storage: MongoStorage, setup_groups: Any):
        result = await storage.task_groups.get_latest_group_iteration("non_existent_task", 1)
        assert result is None

    async def test_get_latest_group_iteration_respects_tenant(self, storage: MongoStorage, setup_groups: Any):
        result = await storage.task_groups.get_latest_group_iteration("task1", 1)
        assert result is not None
        assert result.iteration == 3  # The highest iteration in the current tenant

    async def test_get_latest_group_iteration_empty_collection(self, storage: MongoStorage):
        result = await storage.task_groups.get_latest_group_iteration("task1", 1)
        assert result is None


class TestSetTaskDescription:
    async def test_set_task_description(self, storage: MongoStorage, tasks_col: AsyncCollection):
        # Prepare test data
        task_id = "test_task"
        initial_description = "Initial description"
        new_description = "New description"

        # Insert a task
        task_info = TaskDocument(tenant=TENANT, task_id=task_id, name="Test Task", description=initial_description)
        await tasks_col.insert_one(dump_model(task_info))

        # Update the description
        await storage.set_task_description(task_id, new_description)

        # Verify the update
        updated_variant = await tasks_col.find_one({"task_id": task_id})
        assert updated_variant is not None
        assert updated_variant["description"] == new_description


class TestBuildListTasksPipeline:
    def test_basic_pipeline(self, storage: MongoStorage) -> None:
        # Test basic pipeline without limit and without schemas
        pipeline = storage._build_list_tasks_pipeline({}, None)  # pyright: ignore[reportPrivateUsage]

        expected_pipeline = [
            {"$match": {"tenant": "test_tenant"}},
            {
                "$group": {
                    "_id": "$slug",
                    "id": {"$first": "$slug"},
                    "name": {"$first": "$name"},
                    "is_public": {"$first": "$is_public"},
                    "latest_created_at": {"$max": "$created_at"},
                    "versions": {
                        "$push": {
                            "schema_id": "$schema_id",
                            "variant_id": "$version",
                            "description": "$description",
                            "input_schema_version": "$input_schema.version",
                            "output_schema_version": "$output_schema.version",
                            "created_at": "$created_at",
                        },
                    },
                },
            },
            {"$sort": {"latest_created_at": -1}},
        ]

        assert pipeline == expected_pipeline

    def test_pipeline_with_limit(self, storage: MongoStorage) -> None:
        # Test pipeline with limit but without schemas
        pipeline = storage._build_list_tasks_pipeline({}, 5)  # pyright: ignore[reportPrivateUsage]

        expected_pipeline = [
            {"$match": {"tenant": "test_tenant"}},
            {
                "$group": {
                    "_id": "$slug",
                    "id": {"$first": "$slug"},
                    "name": {"$first": "$name"},
                    "is_public": {"$first": "$is_public"},
                    "latest_created_at": {"$max": "$created_at"},
                    "versions": {
                        "$push": {
                            "schema_id": "$schema_id",
                            "variant_id": "$version",
                            "description": "$description",
                            "input_schema_version": "$input_schema.version",
                            "output_schema_version": "$output_schema.version",
                            "created_at": "$created_at",
                        },
                    },
                },
            },
            {"$sort": {"latest_created_at": -1}},
            {"$limit": 5},
        ]

        assert pipeline == expected_pipeline

    def test_pipeline_with_filter(self, storage: MongoStorage) -> None:
        # Test pipeline with custom filter but without schemas
        custom_filter = {"name": "test_task"}
        pipeline = storage._build_list_tasks_pipeline(custom_filter, None)  # pyright: ignore[reportPrivateUsage]

        expected_pipeline = [
            {"$match": {"name": "test_task", "tenant": "test_tenant"}},
            {
                "$group": {
                    "_id": "$slug",
                    "id": {"$first": "$slug"},
                    "name": {"$first": "$name"},
                    "is_public": {"$first": "$is_public"},
                    "latest_created_at": {"$max": "$created_at"},
                    "versions": {
                        "$push": {
                            "schema_id": "$schema_id",
                            "variant_id": "$version",
                            "description": "$description",
                            "input_schema_version": "$input_schema.version",
                            "output_schema_version": "$output_schema.version",
                            "created_at": "$created_at",
                        },
                    },
                },
            },
            {"$sort": {"latest_created_at": -1}},
        ]

        assert pipeline == expected_pipeline

    def test_pipeline_with_filter_and_limit(self, storage: MongoStorage) -> None:
        # Test pipeline with both filter and limit but without schemas
        custom_filter = {"is_public": True}
        pipeline = storage._build_list_tasks_pipeline(custom_filter, 10)  # pyright: ignore[reportPrivateUsage]

        expected_pipeline = [
            {"$match": {"is_public": True, "tenant": "test_tenant"}},
            {
                "$group": {
                    "_id": "$slug",
                    "id": {"$first": "$slug"},
                    "name": {"$first": "$name"},
                    "is_public": {"$first": "$is_public"},
                    "latest_created_at": {"$max": "$created_at"},
                    "versions": {
                        "$push": {
                            "schema_id": "$schema_id",
                            "variant_id": "$version",
                            "description": "$description",
                            "input_schema_version": "$input_schema.version",
                            "output_schema_version": "$output_schema.version",
                            "created_at": "$created_at",
                        },
                    },
                },
            },
            {"$sort": {"latest_created_at": -1}},
            {"$limit": 10},
        ]

        assert pipeline == expected_pipeline

    def test_pipeline_with_schemas(self, storage: MongoStorage) -> None:
        # Test pipeline with schemas included
        pipeline = storage._build_list_tasks_pipeline({}, None, with_schemas=True)  # pyright: ignore[reportPrivateUsage]

        expected_pipeline = [
            {"$match": {"tenant": "test_tenant"}},
            {
                "$group": {
                    "_id": "$slug",
                    "id": {"$first": "$slug"},
                    "name": {"$first": "$name"},
                    "is_public": {"$first": "$is_public"},
                    "latest_created_at": {"$max": "$created_at"},
                    "versions": {
                        "$push": {
                            "schema_id": "$schema_id",
                            "variant_id": "$version",
                            "description": "$description",
                            "input_schema_version": "$input_schema.version",
                            "output_schema_version": "$output_schema.version",
                            "created_at": "$created_at",
                            "input_schema": "$input_schema.json_schema",
                            "output_schema": "$output_schema.json_schema",
                        },
                    },
                },
            },
            {"$sort": {"latest_created_at": -1}},
        ]

        assert pipeline == expected_pipeline

    def test_pipeline_with_schemas_filter_and_limit(self, storage: MongoStorage) -> None:
        # Test pipeline with schemas, filter, and limit
        custom_filter = {"is_public": True}
        pipeline = storage._build_list_tasks_pipeline(custom_filter, 5, with_schemas=True)  # pyright: ignore[reportPrivateUsage]

        expected_pipeline = [
            {"$match": {"is_public": True, "tenant": "test_tenant"}},
            {
                "$group": {
                    "_id": "$slug",
                    "id": {"$first": "$slug"},
                    "name": {"$first": "$name"},
                    "is_public": {"$first": "$is_public"},
                    "latest_created_at": {"$max": "$created_at"},
                    "versions": {
                        "$push": {
                            "schema_id": "$schema_id",
                            "variant_id": "$version",
                            "description": "$description",
                            "input_schema_version": "$input_schema.version",
                            "output_schema_version": "$output_schema.version",
                            "created_at": "$created_at",
                            "input_schema": "$input_schema.json_schema",
                            "output_schema": "$output_schema.json_schema",
                        },
                    },
                },
            },
            {"$sort": {"latest_created_at": -1}},
            {"$limit": 5},
        ]

        assert pipeline == expected_pipeline
