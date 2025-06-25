import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, cast

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from core.domain.major_minor import MajorMinor
from core.domain.message import Message
from core.domain.task_group import TaskGroupQuery
from core.domain.task_group_update import TaskGroupUpdate
from core.storage import ObjectNotFoundException
from core.storage.mongo.conftest import TENANT
from core.storage.mongo.models.task_group import TaskGroupDocument
from core.storage.mongo.mongo_storage import MongoStorage
from core.storage.mongo.mongo_storage_test import TASK_ID
from core.storage.mongo.mongo_types import AsyncCollection
from core.storage.mongo.partials.task_groups import MongoTaskGroupStorage
from core.storage.mongo.utils import dump_model


@pytest.fixture(scope="function")
def task_groups_storage(storage: MongoStorage) -> MongoTaskGroupStorage:
    return cast(MongoTaskGroupStorage, storage.task_groups)


def _task_group(
    iteration: int = 1,
    schema_id: int = 1,
    semver: tuple[int, int] | None = None,
    hash: str = "",
    **kwargs: Any,
) -> TaskGroupDocument:
    # Default properties
    default_properties = {"model": "gpt-4o-latest", "provider": "fireworks", "temperature": 0.5}
    # Update properties if provided
    properties = kwargs.pop("properties", default_properties)
    # Merge with default properties
    properties = {**default_properties, **properties}
    # Create the TaskGroupDocument with the updated properties
    doc = TaskGroupDocument(
        hash=hash or str(uuid.uuid4()),
        task_id=TASK_ID,
        task_schema_id=schema_id,
        iteration=iteration,
        alias=hash or str(uuid.uuid4()),
        properties=properties,  # Use updated properties here
        tags=["bla"],
        tenant=TENANT,
        major=semver[0] if semver else None,
        minor=semver[1] if semver else None,
    )
    return TaskGroupDocument.model_validate({**doc.model_dump(by_alias=True), **kwargs})


class TestTaskGroupByIDFilter:
    def test_iteration(self, task_groups_storage: MongoTaskGroupStorage) -> None:
        assert task_groups_storage._task_group_by_iteration_filter("t1", 1, 2) == {  # pyright: ignore [reportPrivateUsage]
            "task_id": "t1",
            "task_schema_id": 1,
            "iteration": 2,
        }


class TestUnicity:
    async def test_different_tenants(self, task_run_group_col: AsyncCollection, storage: MongoStorage) -> None:
        kwargs: Any = {"iteration": 2, "aliases": {"bla"}, "alias": "foo"}
        await task_run_group_col.insert_one(dump_model(_task_group(**kwargs)))

        with pytest.raises(DuplicateKeyError):
            await task_run_group_col.insert_one(dump_model(_task_group(**kwargs)))

        await task_run_group_col.insert_one(dump_model(_task_group(tenant="t1", **kwargs)))

        await task_run_group_col.insert_one(dump_model(_task_group(task_id="t1", **kwargs)))
        await task_run_group_col.insert_one(dump_model(_task_group(task_schema_id=3, **kwargs)))

    # Using storage dep to get a clean database
    async def test_iteration(self, task_run_group_col: AsyncCollection, storage: MongoStorage) -> None:
        await task_run_group_col.insert_one(dump_model(_task_group(iteration=2, alias="bla1")))

        with pytest.raises(DuplicateKeyError):
            await task_run_group_col.insert_one(dump_model(_task_group(iteration=2, alias="bla")))

    async def test_aliases(self, task_run_group_col: AsyncCollection, storage: MongoStorage) -> None:
        # Insert a group
        await task_run_group_col.insert_one(dump_model(_task_group(iteration=2, aliases={"bla"}, alias="foo")))

        # Check that a group with a same aliases cannot be inserted
        with pytest.raises(DuplicateKeyError):
            await task_run_group_col.insert_one(
                dump_model(_task_group(iteration=3, aliases={"bla", "bla1"}, alias="foo1")),
            )
        # Change the alias and check that we are
        await task_run_group_col.insert_one(dump_model(_task_group(iteration=3, aliases={"bla1"}, alias="foo1")))
        await task_run_group_col.insert_one(dump_model(_task_group(iteration=4, aliases=[], alias="foo2")))
        await task_run_group_col.insert_one(dump_model(_task_group(iteration=5, aliases=None, alias="foo3")))


class TestGetTaskGroup:
    async def test_success(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ) -> None:
        group = _task_group(iteration=2)
        inserted = await task_run_group_col.insert_one(dump_model(group))
        group.id = inserted.inserted_id

        res = await task_groups_storage.get_task_group_by_iteration(TASK_ID, 1, 2)
        assert res == group.to_resource()
        assert res.schema_id == group.task_schema_id


class TestUpdateTaskGroup:
    async def test_update_is_favorite(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        group = _task_group(iteration=2, aliases={"bla"})
        group_id = await task_run_group_col.insert_one(dump_model(group))

        # Test updating is_favorite to True
        res = await task_groups_storage.update_task_group(TASK_ID, 1, 2, TaskGroupUpdate(is_favorite=True))
        assert res.is_favorite is True
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        expected_doc = dump_model(group) | {"is_favorite": True, "favorited_by": None}
        assert {k: v for k, v in doc.items() if k != "_id"} == expected_doc

        # Test updating is_favorite to False
        res = await task_groups_storage.update_task_group(TASK_ID, 1, 2, TaskGroupUpdate(is_favorite=False))
        assert res.is_favorite is None
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        expected_doc = dump_model(group) | {"favorited_by": None}
        assert {k: v for k, v in doc.items() if k != "_id"} == expected_doc

    async def test_update_notes(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        group = _task_group(iteration=2, aliases={"bla"})
        group_id = await task_run_group_col.insert_one(dump_model(group))

        # Test updating notes
        res = await task_groups_storage.update_task_group(TASK_ID, 1, 2, TaskGroupUpdate(notes="New notes"))
        assert res.notes == "New notes"
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        assert doc["notes"] == "New notes"

        # Test removing notes
        res = await task_groups_storage.update_task_group(TASK_ID, 1, 2, TaskGroupUpdate(notes=""))
        assert res.notes is None
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        assert "notes" not in doc

        # Test re-adding notes
        res = await task_groups_storage.update_task_group(TASK_ID, 1, 2, TaskGroupUpdate(notes="Re-added notes"))
        assert res.notes == "Re-added notes"
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        assert doc["notes"] == "Re-added notes"


class TestAddBenchmarkForDataset:
    @pytest.fixture(scope="function", autouse=True)
    async def inserted_groups(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        groups = [
            _task_group(iteration=2, aliases={"bla"}),
            _task_group(iteration=3),
            _task_group(iteration=2, task_id="t_other"),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])
        return groups

    async def test_single(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
        inserted_groups: list[TaskGroupDocument],
    ):
        await task_groups_storage.add_benchmark_for_dataset(TASK_ID, 1, "ds1", {2})

        doc = [g async for g in task_run_group_col.find({"iteration": 2})]
        assert len(doc) == 2
        doc.sort(key=lambda x: x["task_id"])

        assert doc[0]["task_id"] == "t_other"
        assert doc[0].get("benchmark_for_datasets") is None

        assert doc[1]["task_id"] == TASK_ID
        assert doc[1]["benchmark_for_datasets"] == ["ds1"]

    async def test_multiple(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
        inserted_groups: list[TaskGroupDocument],
    ):
        await task_groups_storage.add_benchmark_for_dataset(TASK_ID, 1, "ds1", {2, 3})

        doc = [g async for g in task_run_group_col.find({"benchmark_for_datasets": "ds1"})]
        assert len(doc) == 2


class TestListTaskGroups:
    @pytest.fixture(scope="function", autouse=True)
    async def inserted_groups(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        groups = [
            _task_group(iteration=2, aliases={"bla"}, hash="1"),
            _task_group(iteration=3, hash="2"),
            _task_group(iteration=4, task_id="t_other", hash="3"),
            _task_group(iteration=4, benchmark_for_datasets=["ds1", "ds2"], hash="4"),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

        # Inserting an invalid doc to make sure we don't crash
        invalid_doc = dump_model(_task_group())
        # Some groups can not have an iteration for a very brief time after creation
        del invalid_doc["iteration"]
        await task_run_group_col.insert_one(invalid_doc)
        return groups

    async def test_all(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        res = [g async for g in task_groups_storage.list_task_groups(TaskGroupQuery(task_id=TASK_ID, task_schema_id=1))]
        assert len(res) == 3

        # Sanity check
        await task_run_group_col.update_many({"iteration": {"$exists": False}}, {"$set": {"iteration": 6}})

        res = [g async for g in task_groups_storage.list_task_groups(TaskGroupQuery(task_id=TASK_ID, task_schema_id=1))]
        assert len(res) == 4

    async def test_dataset_id(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, task_schema_id=1, benchmark_for_dataset_id="ds1"),
            )
        ]
        assert len(res) == 1

    async def test_projection(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, task_schema_id=1),
                include=["iteration"],
            )
        ]
        assert len(res) == 3
        assert res[0].aliases is None
        assert res[0].benchmark_for_datasets is None
        assert res[0].tags == []
        assert res[0].properties.model_dump(exclude_none=True) == {}
        assert res[0].iteration != 0

    async def test_projection_id_only(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, task_schema_id=1),
                include=["id"],
            )
        ]
        assert len(res) == 3
        assert res[0].aliases is None
        assert res[0].benchmark_for_datasets is None
        assert res[0].tags == []
        assert res[0].properties.model_dump(exclude_none=True) == {}
        assert res[0].iteration != 0

    async def test_include_properties(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID),
                include={"properties.model", "properties.provider", "properties.temperature", "iteration"},
            )
        ]
        assert len(res) == 3

    async def test_is_deployed(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        res = [g async for g in task_groups_storage.list_task_groups(TaskGroupQuery(task_id=TASK_ID, is_deployed=True))]
        assert len(res) == 1
        groups = [
            _task_group(task_schema_id=3, iteration=2, aliases={"environment=dev"}),
            _task_group(task_schema_id=3, iteration=3, aliases={"environment=prod"}),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])
        res = [g async for g in task_groups_storage.list_task_groups(TaskGroupQuery(task_id=TASK_ID, is_deployed=True))]
        assert len(res) == 3

    async def test_task_list_without_task_schema_id(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        groups = [
            _task_group(task_schema_id=3, iteration=2, aliases={"environment=dev"}),
            _task_group(task_schema_id=3, iteration=3, aliases={"environment=prod"}),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])
        await task_run_group_col.update_many({"iteration": {"$exists": False}}, {"$set": {"iteration": 6}})

        res = [g async for g in task_groups_storage.list_task_groups(TaskGroupQuery(task_id=TASK_ID))]
        assert len(res) == 6

    async def test_is_deployed_with_empty_aliases(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        groups = [
            _task_group(task_schema_id=3, iteration=2, aliases=[]),
            _task_group(task_schema_id=3, iteration=3, aliases={"environment=prod"}),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])
        await task_run_group_col.update_many({"iteration": {"$exists": False}}, {"$set": {"iteration": 6}})

        res = [g async for g in task_groups_storage.list_task_groups(TaskGroupQuery(task_id=TASK_ID, is_deployed=True))]
        assert len(res) == 2

    async def test_filter_iterations(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        res = [
            g async for g in task_groups_storage.list_task_groups(TaskGroupQuery(task_id=TASK_ID, iterations={2, 3}))
        ]
        assert len(res) == 2

    async def test_list_semver(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        res = [
            _task_group(iteration=5, semver=(1, 0)),
            _task_group(iteration=6, semver=(1, 1)),
            _task_group(iteration=7, semver=(2, 0)),
            _task_group(iteration=8),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in res])
        res = {
            g.iteration: g.semver
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, is_saved=True),
                include=["semver"],
            )
        }
        assert len(res) == 3
        assert res[5] == (1, 0)
        assert res[6] == (1, 1)
        assert res[7] == (2, 0)

        # TODO: check that the right index is used

    async def test_semver_filter(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        res = [
            _task_group(iteration=5, semver=(1, 0)),
            _task_group(iteration=6, semver=(1, 1)),
            _task_group(iteration=7, semver=(2, 0)),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in res])
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, semvers={MajorMinor(1, 0), MajorMinor(1, 1)}),
            )
        ]
        its = {g.iteration for g in res}
        assert its == {5, 6}

    async def test_filter_by_single_id(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        """Test filtering task groups by a single id."""
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, ids={"1"}),
            )
        ]
        assert len(res) == 1
        assert res[0].id == "1"
        assert res[0].iteration == 2

    async def test_filter_by_multiple_ids(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        """Test filtering task groups by multiple ids."""
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, ids={"1", "2"}),
            )
        ]
        assert len(res) == 2
        ids_found = {g.id for g in res}
        assert ids_found == {"1", "2"}
        iterations_found = {g.iteration for g in res}
        assert iterations_found == {2, 3}

    async def test_filter_by_nonexistent_id(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        """Test filtering task groups by non-existent id."""
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, ids={"nonexistent"}),
            )
        ]
        assert len(res) == 0

    async def test_filter_by_empty_ids_set(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        """Test filtering task groups by empty ids set."""
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, ids=set()),
            )
        ]
        # When ids is an empty set, the condition is falsy so no filter is applied
        assert len(res) == 3  # All groups from fixture for TASK_ID

    async def test_filter_by_ids_none(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        """Test filtering task groups when ids is None."""
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, ids=None),
            )
        ]
        # Should return all groups for the task
        assert len(res) == 3  # All groups from fixture for TASK_ID

    async def test_filter_by_ids_combined_with_other_filters(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        """Test combining ids filter with other filters."""
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, task_schema_id=1, ids={"1", "4"}),
            )
        ]
        assert len(res) == 2
        ids_found = {g.id for g in res}
        assert ids_found == {"1", "4"}
        # Both should have task_schema_id=1
        for group in res:
            assert group.schema_id == 1

    async def test_filter_by_ids_cross_task(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        """Test that ids filter respects task_id boundaries."""
        # Try to get hash "3" which belongs to "t_other" task, not TASK_ID
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id=TASK_ID, ids={"3"}),
            )
        ]
        # Should return empty since hash "3" belongs to a different task_id
        assert len(res) == 0

        # Verify it exists for the correct task_id
        res = [
            g
            async for g in task_groups_storage.list_task_groups(
                TaskGroupQuery(task_id="t_other", ids={"3"}),
            )
        ]
        assert len(res) == 1
        assert res[0].id == "3"


class TestSimilarityHash:
    async def test_similarity_hash(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        task_id = "similarity_test"
        # Create base properties
        base_properties: dict[str, Any] = {
            "temperature": 0.7,
            "instructions": "Test instructions",
            "few_shot": {"count": 3, "selection": "random"},
            "task_variant_id": "variant_1",
        }

        # Create groups with different properties and unique combinations of tenant, task_id, and iteration
        groups = [
            _task_group(iteration=1, task_id=task_id, properties=base_properties),
            _task_group(
                iteration=2,
                task_id=task_id,
                properties={**base_properties, "model": "gpt-4"},
            ),
            _task_group(
                iteration=3,
                task_id=task_id,
                properties={**base_properties, "max_tokens": 100},
            ),
            _task_group(
                iteration=4,
                task_id=task_id,
                properties={**base_properties, "provider": "openai"},
            ),
            _task_group(
                iteration=5,
                task_id=task_id,
                properties={**base_properties, "runner_name": "custom_runner"},
            ),
            _task_group(
                iteration=6,
                task_id=task_id,
                properties={**base_properties, "template_name": "custom_template"},
            ),
            _task_group(
                iteration=7,
                task_id=task_id,
                properties={**base_properties, "temperature": 0.8},
            ),
            _task_group(
                iteration=8,
                task_id=task_id,
                properties={**base_properties, "instructions": "New instructions"},
            ),
            _task_group(
                iteration=9,
                task_id=task_id,
                properties={**base_properties, "task_variant_id": "variant_2"},
            ),
        ]

        # Insert groups into the database
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

        # Fetch all groups
        fetched_groups = [
            g async for g in task_groups_storage.list_task_groups(TaskGroupQuery(task_id=task_id, task_schema_id=1))
        ]

        # Sort groups by the `iteration` field
        fetched_groups_sorted = sorted(fetched_groups, key=lambda g: g.iteration)

        # Ensure there are exactly 10 fetched groups
        assert len(fetched_groups_sorted) == 9, f"Error: Expected 10 groups, but got {len(fetched_groups_sorted)}"

        # Check similarity hashes
        base_hash = fetched_groups_sorted[0].similarity_hash
        assert fetched_groups_sorted[1].similarity_hash == base_hash  # model change should not affect hash
        assert fetched_groups_sorted[2].similarity_hash == base_hash  # max_tokens change should not affect hash
        assert fetched_groups_sorted[3].similarity_hash == base_hash  # provider change should not affect hash
        assert fetched_groups_sorted[4].similarity_hash == base_hash  # runner_name change should not affect hash
        assert fetched_groups_sorted[5].similarity_hash == base_hash  # template_name change should not affect hash
        assert fetched_groups_sorted[6].similarity_hash != base_hash  # temperature change should affect hash
        assert fetched_groups_sorted[7].similarity_hash != base_hash  # instructions change should affect hash
        assert fetched_groups_sorted[8].similarity_hash != base_hash  # task_variant_id change should affect hash

        # Check that groups with different hashes are unique
        unique_hashes = set(g.similarity_hash for g in fetched_groups_sorted)
        assert len(unique_hashes) == 4  # base + 4 changes that affect the hash


class TestSaveTaskGroup:
    async def test_save_task_group(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        # Create a task group
        task_group = _task_group(iteration=1, task_id=TASK_ID, hash="hash", similarity_hash="similarity_hash")
        await task_run_group_col.insert_one(dump_model(task_group))

        # Save the task group
        updated, saved = await task_groups_storage.save_task_group(TASK_ID, "hash")

        assert saved
        assert updated.semver == (1, 1)

        # Check that the task group was updated
        updated_doc = await task_run_group_col.find_one({"task_id": TASK_ID, "hash": "hash"})
        assert updated_doc is not None
        assert updated_doc["major"] == 1
        assert updated_doc["minor"] == 1

        # Check that re-saving is a noop
        updated, saved = await task_groups_storage.save_task_group(TASK_ID, "hash")
        assert not saved
        assert updated.semver == (1, 1)

    async def test_save_task_group_race_condition(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        # Insert 3 groups
        groups = [
            _task_group(iteration=1, task_id=TASK_ID, hash="hash1", similarity_hash="similarity_hash"),
            _task_group(iteration=2, task_id=TASK_ID, hash="hash2", similarity_hash="similarity_hash1"),
            _task_group(iteration=3, task_id=TASK_ID, hash="hash3", similarity_hash="similarity_hash"),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

        # Now save them all at the same time
        await asyncio.gather(
            task_groups_storage.save_task_group(TASK_ID, "hash1"),
            task_groups_storage.save_task_group(TASK_ID, "hash2"),
            task_groups_storage.save_task_group(TASK_ID, "hash3"),
        )

        # Check the groups with similarity_hash
        docs = [grp async for grp in task_run_group_col.find({})]
        assert len(docs) == 3, "sanity"

        # It's annoying here because the major / minor could have been assigned in any order

        # We will get version 1.1, 1.2 and 2.1 or 1.1, 2.1 and 2.2
        majors = sorted([doc["major"] for doc in docs])
        assert majors in [[1, 1, 2], [1, 2, 2]]
        minors = sorted([doc["minor"] for doc in docs])
        assert minors == [1, 1, 2]


class TestListVersionMajors:
    async def test_list_version_majors(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        # Create 2 groups and save them
        groups = [
            _task_group(
                iteration=1,
                task_id=TASK_ID,
                hash="hash1",
                similarity_hash="similarity_hash",
                properties={"instructions": "bla"},
                created_by={"user_email": "user1@example.com"},
                _id=ObjectId("659b81500000000000000000"),
            ),
            _task_group(iteration=2, task_id=TASK_ID, hash="hash2", similarity_hash="similarity_hash"),
            _task_group(
                iteration=3,
                task_id=TASK_ID,
                hash="hash3",
                similarity_hash="similarity_hash1",
                properties={"instructions": "bla1"},
            ),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

        await task_groups_storage.save_task_group(TASK_ID, "hash1")
        await task_groups_storage.save_task_group(TASK_ID, "hash2")
        await task_groups_storage.save_task_group(TASK_ID, "hash3")

        majors = [v async for v in task_groups_storage.list_version_majors(TASK_ID, None)]
        assert len(majors) == 2

        # Check that the majors are sorted by major and minor
        assert majors[0].major == 1
        # Created at is the first id generation time
        assert majors[0].created_at == datetime(2024, 1, 8, 5, 0, 0, 0, tzinfo=timezone.utc)
        assert majors[0].minors[0].minor == 1
        assert majors[0].created_by and majors[0].created_by.user_email == "user1@example.com"
        assert majors[0].minors[1].minor == 2
        assert majors[0].minors[0].created_by is not None
        assert majors[1].major == 2
        assert majors[1].minors[0].minor == 1

    async def test_list_version_majors_with_messages(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        # Create 2 groups and save them
        groups = [
            _task_group(
                iteration=1,
                task_id=TASK_ID,
                hash="hash1",
                similarity_hash="similarity_hash",
                properties={"messages": [Message.with_text(role="user", text="Hello, world!")]},
                created_by={"user_email": "user1@example.com"},
                _id=ObjectId("659b81500000000000000000"),
            ),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

        await task_groups_storage.save_task_group(TASK_ID, "hash1")

        majors = [v async for v in task_groups_storage.list_version_majors(TASK_ID, None)]
        assert len(majors) == 1

        # Check that the majors are sorted by major and minor
        assert majors[0].major == 1
        assert majors[0].properties.messages == [Message.with_text(role="user", text="Hello, world!")]


class TestPreviousMajor:
    async def test_previous_major(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        # Create groups with different major versions
        groups = [
            _task_group(
                iteration=1,
                task_id=TASK_ID,
                hash="hash1",
                similarity_hash="similarity_hash",
                major=1,
                minor=1,
            ),
            _task_group(
                iteration=2,
                task_id=TASK_ID,
                hash="hash2",
                similarity_hash="similarity_hash1",
                major=2,
                minor=1,
            ),
            _task_group(
                iteration=3,
                task_id=TASK_ID,
                hash="hash3",
                similarity_hash="similarity_hash2",
                major=3,
                minor=1,
            ),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

        # Test getting previous major for major=3
        previous = await task_groups_storage.get_previous_major(TASK_ID, 1, 3)
        assert previous is not None
        assert previous.semver == (2, 1)

        # Test getting previous major for major=2
        previous = await task_groups_storage.get_previous_major(TASK_ID, 1, 2)
        assert previous is not None
        assert previous.semver == (1, 1)

        # Test getting previous major for major=1 (should return None)
        previous = await task_groups_storage.get_previous_major(TASK_ID, 1, 1)
        assert previous is None

    async def test_previous_major_different_schema(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        # Create groups with different schema IDs
        groups = [
            _task_group(
                iteration=1,
                task_id=TASK_ID,
                task_schema_id=1,
                hash="hash1",
                similarity_hash="similarity_hash",
                major=1,
                minor=1,
            ),
            _task_group(
                iteration=2,
                task_id=TASK_ID,
                task_schema_id=2,
                hash="hash2",
                similarity_hash="similarity_hash1",
                major=2,
                minor=1,
            ),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

        # Test that we don't get previous major from different schema
        previous = await task_groups_storage.get_previous_major(TASK_ID, 2, 2)
        assert previous is None

    async def test_previous_major_different_task(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        # Create groups with different task IDs
        groups = [
            _task_group(
                iteration=1,
                task_id=TASK_ID,
                hash="hash1",
                similarity_hash="similarity_hash",
                major=1,
                minor=1,
            ),
            _task_group(
                iteration=2,
                task_id="different_task",
                hash="hash2",
                similarity_hash="similarity_hash1",
                major=2,
                minor=1,
            ),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

        # Test that we don't get previous major from different task
        previous = await task_groups_storage.get_previous_major("different_task", 1, 2)
        assert previous is None

    async def test_previous_major_with_multiple_minors(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        # Create groups with multiple minor versions
        groups = [
            _task_group(
                iteration=1,
                task_id=TASK_ID,
                hash="hash1",
                similarity_hash="similarity_hash",
                major=1,
                minor=1,
            ),
            _task_group(
                iteration=2,
                task_id=TASK_ID,
                hash="hash2",
                similarity_hash="similarity_hash",
                major=1,
                minor=2,
            ),
            _task_group(
                iteration=3,
                task_id=TASK_ID,
                hash="hash3",
                similarity_hash="similarity_hash1",
                major=2,
                minor=1,
            ),
        ]
        await task_run_group_col.insert_many([dump_model(g) for g in groups])

        # Test that we get the highest minor version of the previous major
        previous = await task_groups_storage.get_previous_major(TASK_ID, 1, 2)
        assert previous is not None
        assert previous.semver == (1, 2)


class TestUpdateTaskGroupByID:
    async def test_update_is_favorite_by_hash(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        group = _task_group(hash="bla", aliases={"bla"})
        group_id = await task_run_group_col.insert_one(dump_model(group))

        # Test updating is_favorite to True
        res = await task_groups_storage.update_task_group_by_id(TASK_ID, "bla", TaskGroupUpdate(is_favorite=True))
        assert res.is_favorite is True
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        expected_doc = dump_model(group) | {"is_favorite": True, "favorited_by": None}
        assert {k: v for k, v in doc.items() if k != "_id"} == expected_doc

        # Test updating is_favorite to False
        res = await task_groups_storage.update_task_group_by_id(TASK_ID, "bla", TaskGroupUpdate(is_favorite=False))
        assert res.is_favorite is None
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        expected_doc = dump_model(group) | {"favorited_by": None}
        assert {k: v for k, v in doc.items() if k != "_id"} == expected_doc

    async def test_update_is_favorite_by_semver(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        group = _task_group(major=1, minor=1)
        group_id = await task_run_group_col.insert_one(dump_model(group))

        res = await task_groups_storage.update_task_group_by_id(
            TASK_ID,
            MajorMinor(major=1, minor=1),
            TaskGroupUpdate(is_favorite=True),
        )
        assert res.is_favorite is True
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        expected_doc = dump_model(group) | {"is_favorite": True, "favorited_by": None}
        assert {k: v for k, v in doc.items() if k != "_id"} == expected_doc

        # Check with a different minor
        with pytest.raises(ObjectNotFoundException):  # noqa: F821
            await task_groups_storage.update_task_group_by_id(
                TASK_ID,
                MajorMinor(major=1, minor=2),
                TaskGroupUpdate(is_favorite=True),
            )

    async def test_update_notes(self, task_groups_storage: MongoTaskGroupStorage, task_run_group_col: AsyncCollection):
        group = _task_group(iteration=2, aliases={"bla"})
        group_id = await task_run_group_col.insert_one(dump_model(group))

        # Test updating notes
        res = await task_groups_storage.update_task_group(TASK_ID, 1, 2, TaskGroupUpdate(notes="New notes"))
        assert res.notes == "New notes"
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        assert doc["notes"] == "New notes"

        # Test removing notes
        res = await task_groups_storage.update_task_group(TASK_ID, 1, 2, TaskGroupUpdate(notes=""))
        assert res.notes is None
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        assert "notes" not in doc

        # Test re-adding notes
        res = await task_groups_storage.update_task_group(TASK_ID, 1, 2, TaskGroupUpdate(notes="Re-added notes"))
        assert res.notes == "Re-added notes"
        doc = await task_run_group_col.find_one({"_id": group_id.inserted_id})
        assert doc
        assert doc["notes"] == "Re-added notes"


class TestGetTaskGroupByID:
    async def test_get_task_group_by_id(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        group = _task_group(hash="bla", iteration=2, aliases={"bla"})
        await task_run_group_col.insert_one(dump_model(group))

        res = await task_groups_storage.get_task_group_by_id(TASK_ID, "bla")
        assert res.id == "bla"
        assert res.iteration == 2

        # Try and project only the id
        res = await task_groups_storage.get_task_group_by_id(TASK_ID, "bla", include=["id"])
        assert res.id == "bla"
        assert not res.properties.model_dump(exclude_unset=True)


class TestFirstIDForSchema:
    async def test_first_id_for_schema(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        group = _task_group(hash="bla", iteration=2)
        await task_run_group_col.insert_one(dump_model(group))

        res = await task_groups_storage.first_id_for_schema(TASK_ID, 1)
        assert res == "bla"

    async def test_first_id_invalid_doc(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        group = dump_model(_task_group(hash="blabla", iteration=2))
        del group["iteration"]
        await task_run_group_col.insert_one(group)

        res = await task_groups_storage.first_id_for_schema(TASK_ID, 1)
        assert res == "blabla"


class TestMapIterations:
    async def test_map_iterations(
        self,
        task_groups_storage: MongoTaskGroupStorage,
        task_run_group_col: AsyncCollection,
    ):
        group = _task_group(hash="bla", iteration=2)
        await task_run_group_col.insert_one(dump_model(group))

        group2 = _task_group(hash="bla2", iteration=3)
        await task_run_group_col.insert_one(dump_model(group2))

        res = await task_groups_storage.map_iterations(TASK_ID, 1, {2, 3})
        assert res == {2: "bla", 3: "bla2"}
