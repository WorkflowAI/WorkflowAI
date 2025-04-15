from abc import ABC, abstractmethod

from pymongo.errors import OperationFailure

from core.storage.mongo.mongo_storage import MongoStorage
from core.storage.mongo.mongo_types import AsyncCollection


class AbstractMigration(ABC):
    """A migration that can be applied to the storage"""

    def __init__(self, storage: MongoStorage) -> None:
        self.storage = storage

    TASK_PREFIX = ("tenant", 1), ("task_id", 1)

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @abstractmethod
    async def apply(self) -> None:
        """Apply the migration"""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the migration"""
        pass

    async def _drop_index_if_exists(self, collection: AsyncCollection, name: str):
        try:
            await collection.drop_index(name)
        except OperationFailure as e:
            if e.code == 27:  # IndexNotFound
                pass
            else:
                raise e

    @property
    def _task_variants_collection(self) -> AsyncCollection:
        return self.storage._task_variants_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_runs_collection(self) -> AsyncCollection:
        return self.storage._task_runs_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_examples_collections(self) -> AsyncCollection:
        return self.storage._task_examples_collections  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_schema_id_collection(self) -> AsyncCollection:
        return self.storage._task_schema_id_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_run_group_idx_collection(self) -> AsyncCollection:
        return self.storage._task_run_group_idx_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_run_group_collection(self) -> AsyncCollection:
        return self.storage._task_run_group_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _organization_collection(self) -> AsyncCollection:
        return self.storage._organization_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_schemas_collection(self) -> AsyncCollection:
        return self.storage._task_schemas_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_benchmarks_collection(self) -> AsyncCollection:
        return self.storage._task_benchmarks_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_evaluators_collection(self) -> AsyncCollection:
        return self.storage._task_evaluators_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_inputs_collection(self) -> AsyncCollection:
        return self.storage._task_inputs_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _tasks_collection(self) -> AsyncCollection:
        return self.storage._tasks_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _dataset_benchmarks_collection(self) -> AsyncCollection:
        return self.storage._dataset_benchmarks_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _changelogs_collection(self) -> AsyncCollection:
        return self.storage._changelogs_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _input_evaluations_collection(self) -> AsyncCollection:
        return self.storage._input_evaluations_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _transcriptions_collection(self) -> AsyncCollection:
        return self.storage._transcriptions_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _reviews_collection(self) -> AsyncCollection:
        return self.storage._reviews_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _review_benchmarks_collection(self) -> AsyncCollection:
        return self.storage._review_benchmarks_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_deployments_collection(self) -> AsyncCollection:
        return self.storage._task_deployments_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _task_group_semvers_collection(self) -> AsyncCollection:
        return self.storage._task_group_semvers_collection  # pyright: ignore [reportPrivateUsage]

    @property
    def _feedback_collection(self) -> AsyncCollection:
        return self.storage._feedback_collection  # pyright: ignore [reportPrivateUsage]
