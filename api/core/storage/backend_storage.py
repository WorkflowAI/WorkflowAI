from abc import abstractmethod
from datetime import datetime
from typing import AsyncIterator, Optional, Protocol

from core.domain.agent_run import AgentRun
from core.domain.analytics_events.analytics_events import SourceType
from core.domain.errors import InternalError
from core.domain.task import SerializableTask
from core.domain.task_example import SerializableTaskExample
from core.domain.task_example_query import SerializableTaskExampleQuery
from core.domain.task_group import TaskGroup
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_info import PublicTaskInfo
from core.domain.task_input import TaskInput, TaskInputFields
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tenant_data import PublicOrganizationData
from core.domain.users import UserIdentifier
from core.storage.abstract_storage import AbstractStorage
from core.storage.changelogs_storage import ChangeLogStorage
from core.storage.evaluator_storage import EvaluatorStorage
from core.storage.feedback_storage import FeedbackStorage, FeedbackSystemStorage
from core.storage.input_evaluations_storage import InputEvaluationStorage
from core.storage.organization_storage import OrganizationStorage, OrganizationSystemStorage
from core.storage.review_benchmark_storage import ReviewBenchmarkStorage
from core.storage.reviews_storage import ReviewsStorage
from core.storage.task_deployments_storage import TaskDeploymentsStorage
from core.storage.task_group_storage import TaskGroupStorage
from core.storage.task_input_storage import TaskInputsStorage
from core.storage.task_run_storage import TaskRunStorage, TaskRunSystemStorage
from core.storage.task_storage import TaskStorage, TaskSystemStorage
from core.storage.task_variants_storage import TaskVariantsStorage
from core.storage.tools_storage import ToolsStorage
from core.storage.transcription_storage import TranscriptionStorage


class SystemBackendStorage(Protocol):
    @property
    @abstractmethod
    def organizations(self) -> OrganizationSystemStorage:
        pass

    @property
    @abstractmethod
    def feedback(self) -> FeedbackSystemStorage:
        pass

    @property
    @abstractmethod
    def tasks(self) -> TaskSystemStorage:
        pass

    @property
    @abstractmethod
    def task_runs(self) -> TaskRunSystemStorage:
        pass

    def active_tasks(self, since: datetime) -> AsyncIterator[tuple[PublicOrganizationData, list[PublicTaskInfo]]]: ...


class BackendStorage(AbstractStorage):
    """A storage with additional methods for the backend"""

    @property
    @abstractmethod
    def tenant(self) -> str:
        pass

    @property
    @abstractmethod
    def evaluators(self) -> EvaluatorStorage:
        pass

    @property
    @abstractmethod
    def task_runs(self) -> TaskRunStorage:
        pass

    @property
    @abstractmethod
    def tasks(self) -> TaskStorage:
        pass

    @property
    @abstractmethod
    def task_groups(self) -> TaskGroupStorage:
        pass

    @property
    @abstractmethod
    def task_variants(self) -> TaskVariantsStorage:
        pass

    @property
    @abstractmethod
    def task_inputs(self) -> TaskInputsStorage:
        pass

    @property
    @abstractmethod
    def organizations(self) -> OrganizationStorage:
        pass

    @property
    @abstractmethod
    def changelogs(self) -> ChangeLogStorage:
        pass

    @property
    @abstractmethod
    def input_evaluations(self) -> InputEvaluationStorage:
        pass

    @property
    @abstractmethod
    def transcriptions(self) -> TranscriptionStorage:
        pass

    @property
    @abstractmethod
    def reviews(self) -> ReviewsStorage:
        pass

    @property
    @abstractmethod
    def review_benchmarks(self) -> ReviewBenchmarkStorage:
        pass

    @property
    @abstractmethod
    def task_deployments(self) -> TaskDeploymentsStorage:
        pass

    @property
    @abstractmethod
    def feedback(self) -> FeedbackStorage:
        pass

    @property
    @abstractmethod
    def tools(self) -> ToolsStorage:
        pass

    @abstractmethod
    async def is_ready(self) -> bool:
        pass

    # TODO: paginate
    @abstractmethod
    async def fetch_tasks(
        self,
        limit: int | None = None,
        with_schemas: bool = False,
    ) -> AsyncIterator[SerializableTask]:
        return
        yield

    @abstractmethod
    async def get_task(self, task_id: str, with_schemas: bool = False) -> SerializableTask:
        return
        yield

    @abstractmethod
    async def task_version_resource_by_id(self, task_id: str, version_id: str) -> SerializableTaskVariant:
        pass

    @abstractmethod
    async def task_variant_latest_by_schema_id(self, task_id: str, task_schema_id: int) -> SerializableTaskVariant:
        pass

    @abstractmethod
    async def count_examples(self, query: SerializableTaskExampleQuery) -> int:
        pass

    @abstractmethod
    async def delete_example(self, example_id: str) -> SerializableTaskExample:
        """Delete an example by ID. Example should be removed from all task runs."""
        pass

    @abstractmethod
    async def get_any_input_by_hash(self, task_id: str, task_schema_id: int, input_hash: str) -> TaskInput:
        pass

    @abstractmethod
    def get_inputs_by_hash(
        self,
        task_id: str,
        task_schema_id: int,
        input_hashes: set[str],
        exclude_fields: set[TaskInputFields] | None = None,
    ) -> AsyncIterator[TaskInput]:
        return
        yield

    @abstractmethod
    async def set_task_description(self, task_id: str, description: str) -> None:
        """Set the description of a task"""
        pass

    @abstractmethod
    async def get_latest_idx(self, task_id: str) -> int:
        pass

    @abstractmethod
    async def get_latest_group_iteration(self, task_id: str) -> int:
        pass

    # WRAP Methods from Abstract Storage to use the Serializable versions of models

    # ----------------------------------------------------
    # Examples

    @abstractmethod
    async def fetch_example_resources(
        self,
        query: SerializableTaskExampleQuery,
    ) -> AsyncIterator[SerializableTaskExample]:
        return
        yield

    @abstractmethod
    async def store_example_resource(
        self,
        task: SerializableTaskVariant,
        example: SerializableTaskExample,
    ) -> SerializableTaskExample:
        pass

    @abstractmethod
    async def get_or_create_task_group(
        self,
        task_id: str,
        task_schema_id: int,
        properties: TaskGroupProperties,
        tags: list[str],
        is_external: Optional[bool] = None,
        id: Optional[str] = None,
        user: Optional[UserIdentifier] = None,
        disable_autosave: bool | None = None,
    ) -> TaskGroup:
        """Returns a task run group given an id"""
        pass

    @abstractmethod
    async def delete_task(self, task_id: str) -> None:
        """Delete a task and all associated runs and examples"""
        pass

    @abstractmethod
    async def prepare_task_run(
        self,
        task: SerializableTaskVariant,
        run: AgentRun,
        user: UserIdentifier | None,
        source: SourceType | None,
    ) -> AgentRun:
        pass

    async def get_task_tuple(self, task_id: str):
        task = await self.tasks.get_task_info(task_id)
        if not task:
            raise InternalError("No task found", extras={"task_id": task_id}, fatal=True)
        return task.id_tuple
