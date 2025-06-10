from __future__ import annotations

from typing import Any, AsyncGenerator, AsyncIterator

from typing_extensions import override

from core.domain.agent_run import AgentRun
from core.domain.analytics_events.analytics_events import SourceType
from core.domain.task_example import SerializableTaskExample
from core.domain.task_group import TaskGroup, TaskGroupIdentifier
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.storage.changelogs_storage import ChangeLogStorage
from core.storage.evaluator_storage import EvaluatorStorage
from core.storage.feedback_storage import FeedbackStorage
from core.storage.input_evaluations_storage import InputEvaluationStorage
from core.storage.key_value_storage import KeyValueStorage
from core.storage.organization_storage import OrganizationStorage
from core.storage.review_benchmark_storage import ReviewBenchmarkStorage
from core.storage.reviews_storage import ReviewsStorage
from core.storage.task_deployments_storage import TaskDeploymentsStorage
from core.storage.task_group_storage import TaskGroupStorage
from core.storage.task_input_storage import TaskInputsStorage
from core.storage.task_run_storage import TaskRunStorage
from core.storage.task_storage import TaskStorage
from core.storage.task_variants_storage import TaskVariantsStorage
from core.storage.tools_storage import ToolsStorage
from core.storage.transcription_storage import TranscriptionStorage


class NoopTaskRunStorage(TaskRunStorage):
    @override
    async def list_runs_for_memory_id(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    weekly_run_aggregate = list_runs_for_memory_id
    aggregate_task_run_costs = list_runs_for_memory_id
    search_task_runs = list_runs_for_memory_id
    fetch_task_run_resources = list_runs_for_memory_id
    aggregate_task_metadata_fields = list_runs_for_memory_id
    run_count_by_version_id = list_runs_for_memory_id
    run_count_by_agent_uid = list_runs_for_memory_id
    list_latest_runs = list_runs_for_memory_id

    @override
    async def aggregate_token_counts(self, *args: Any, **kwargs: Any) -> Any:
        return {}

    @override
    async def count_filtered_task_runs(self, *args: Any, **kwargs: Any) -> Any:
        return 0

    @override
    async def aggregate_runs(self, *args: Any, **kwargs: Any) -> Any:
        return {}

    @override
    async def store_task_run(self, task_run: AgentRun) -> AgentRun:
        return task_run

    @override
    async def fetch_task_run_resource(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def fetch_cached_run(self, *args: Any, **kwargs: Any) -> Any:
        return None


class NoopTaskStorage(TaskStorage):
    @override
    async def get_public_task_info(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def is_task_public(self, *args: Any, **kwargs: Any) -> bool:
        return False

    @override
    async def get_task_info(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def update_task(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    def active_tasks(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None


class NoopTaskGroupStorage(TaskGroupStorage):
    @override
    async def get_task_group_by_iteration(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def get_task_group_by_id(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def increment_run_count(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def update_task_group(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def update_task_group_by_id(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def add_benchmark_for_dataset(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def remove_benchmark_for_dataset(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    def list_task_groups(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def first_id_for_schema(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def get_latest_group_iteration(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def get_previous_major(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def save_task_group(self, *args: Any, **kwargs: Any) -> tuple[TaskGroup, bool]:
        return TaskGroup(id="", iteration=0, properties=TaskGroupProperties(), tags=[]), False

    @override
    def list_version_majors(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def map_iterations(self, *args: Any, **kwargs: Any) -> Any:
        return {}


class NoopTaskVariantsStorage(TaskVariantsStorage):
    @override
    async def update_task(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def get_latest_task_variant(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def get_task_variant_by_uid(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()


class NoopTaskInputsStorage(TaskInputsStorage):
    @override
    async def create_inputs(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def create_input(self, *args: Any, **kwargs: Any) -> Any:
        return args[1] if len(args) > 1 else None

    @override
    async def attach_example(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def detach_example(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def remove_inputs_from_datasets(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    def list_inputs(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def get_input_by_hash(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def count_inputs(self, *args: Any, **kwargs: Any) -> Any:
        return 0, 0


class NoopOrganizationStorage(OrganizationStorage):
    @property
    @override
    def tenant(self) -> str:
        return ""

    @override
    async def get_public_organization(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def public_organization_by_tenant(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def get_organization_by_slack_channel_id(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def find_tenant_for_api_key(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def update_api_key_last_used_at(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def update_slug(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def create_organization(self, *args: Any, **kwargs: Any) -> Any:
        return args[0] if args else None

    @override
    async def delete_organization(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def find_tenant_for_deprecated_user(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def find_tenant_for_org_id(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def find_tenant_for_owner_id(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def find_anonymous_tenant(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def feedback_slack_hook_for_tenant(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def add_credits_to_tenant(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def decrement_credits(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def migrate_tenant_to_organization(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def migrate_tenant_to_user(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def attempt_lock_for_payment(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def unlock_payment_for_failure(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def unlock_payment_for_success(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def add_low_credits_email_sent(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def check_unlocked_payment_failure(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    def organizations_by_uid(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def get_organization(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def update_customer_id(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def add_provider_config(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def delete_provider_config(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def add_5_credits_for_first_task(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def create_api_key_for_organization(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def get_api_keys_for_organization(self, *args: Any, **kwargs: Any) -> Any:
        return []

    @override
    async def delete_api_key_for_organization(self, *args: Any, **kwargs: Any) -> bool:
        return False

    @override
    async def update_automatic_payment(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def clear_payment_failure(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def set_slack_channel_id(self, *args: Any, **kwargs: Any) -> None:
        pass


class NoopChangeLogStorage(ChangeLogStorage):
    @override
    async def insert_changelog(self, *args: Any, **kwargs: Any) -> Any:
        return args[0] if args else None

    @override
    def list_changelogs(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None


class NoopInputEvaluationStorage(InputEvaluationStorage):
    @override
    async def get_latest_input_evaluation(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def create_input_evaluation(self, *args: Any, **kwargs: Any) -> Any:
        return args[0] if args else None

    @override
    async def get_input_evaluation(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    def list_input_evaluations_unique_by_hash(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def unique_input_hashes(self, *args: Any, **kwargs: Any) -> set[str]:
        return set()


class NoopTranscriptionStorage(TranscriptionStorage):
    @override
    async def insert_transcription(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def get_transcription(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()


class NoopReviewsStorage(ReviewsStorage):
    @override
    async def mark_as_stale(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def insert_review(self, *args: Any, **kwargs: Any) -> Any:
        return args[0] if args else None

    @override
    def list_reviews(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def get_review_by_id(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def get_review_by_hash(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def insert_in_progress_review(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def complete_review(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def fail_review(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def add_comment_to_review(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def find_unique_input_hashes(self, *args: Any, **kwargs: Any) -> set[str]:
        return set()

    @override
    async def eval_hashes_with_user_reviews(self, *args: Any, **kwargs: Any) -> set[str]:
        return set()

    @override
    def reviews_for_eval_hashes(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def eval_hashes_for_review(self, *args: Any, **kwargs: Any) -> set[str]:
        return set()


class NoopReviewBenchmarkStorage(ReviewBenchmarkStorage):
    @override
    async def get_benchmark_versions(self, *args: Any, **kwargs: Any) -> set[int]:
        return set()

    @override
    async def get_review_benchmark(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def add_versions(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def remove_versions(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def mark_as_loading_new_ai_reviewer(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def add_in_progress_run(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def complete_run(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def update_benchmark(self, *args: Any, **kwargs: Any) -> None:
        pass


class NoopTaskDeploymentsStorage(TaskDeploymentsStorage):
    @override
    def list_task_deployments(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def get_task_deployment(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    def get_task_deployment_for_iteration(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def deploy_task_version(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def get_task_deployed_versions_ids(self, *args: Any, **kwargs: Any) -> set[int]:
        return set()


class NoopFeedbackStorage(FeedbackStorage):
    @override
    async def store_feedback(self, *args: Any, **kwargs: Any) -> Any:
        return args[2] if len(args) > 2 else None

    @override
    async def get_feedback(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def add_annotation(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    def list_feedback(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def count_feedback(self, *args: Any, **kwargs: Any) -> int:
        return 0


class NoopToolsStorage(ToolsStorage):
    @override
    async def list_tools(self) -> Any:
        return []

    @override
    async def get_tool_by_id(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def create_tool(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def update_tool(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def delete_tool(self, *args: Any, **kwargs: Any) -> None:
        pass


class NoopEvaluatorStorage(EvaluatorStorage):
    @override
    async def add_task_evaluator(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    def list_task_evaluators(self, *args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        if False:
            yield None

    @override
    async def get_task_evaluator(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def set_task_evaluator_active(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def patch_evaluator(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def deactivate_evaluators(self, *args: Any, **kwargs: Any) -> None:
        pass


class NoopStorage(BackendStorage):
    """A storage that does nothing."""

    @property
    @override
    def tenant(self) -> str:
        return ""

    @property
    @override
    def kv(self) -> KeyValueStorage:
        return NoopKeyValueStorage()

    @property
    @override
    def evaluators(self) -> EvaluatorStorage:
        return NoopEvaluatorStorage()

    @property
    @override
    def task_runs(self) -> TaskRunStorage:
        return NoopTaskRunStorage()

    @property
    @override
    def tasks(self) -> TaskStorage:
        return NoopTaskStorage()

    @property
    @override
    def task_groups(self) -> TaskGroupStorage:
        return NoopTaskGroupStorage()

    @property
    @override
    def task_variants(self) -> TaskVariantsStorage:
        return NoopTaskVariantsStorage()

    @property
    @override
    def task_inputs(self) -> TaskInputsStorage:
        return NoopTaskInputsStorage()

    @property
    @override
    def organizations(self) -> OrganizationStorage:
        return NoopOrganizationStorage()

    @property
    @override
    def changelogs(self) -> ChangeLogStorage:
        return NoopChangeLogStorage()

    @property
    @override
    def input_evaluations(self) -> InputEvaluationStorage:
        return NoopInputEvaluationStorage()

    @property
    @override
    def transcriptions(self) -> TranscriptionStorage:
        return NoopTranscriptionStorage()

    @property
    @override
    def reviews(self) -> ReviewsStorage:
        return NoopReviewsStorage()

    @property
    @override
    def review_benchmarks(self) -> ReviewBenchmarkStorage:
        return NoopReviewBenchmarkStorage()

    @property
    @override
    def task_deployments(self) -> TaskDeploymentsStorage:
        return NoopTaskDeploymentsStorage()

    @property
    @override
    def feedback(self) -> FeedbackStorage:
        return NoopFeedbackStorage()

    @property
    @override
    def tools(self) -> ToolsStorage:
        return NoopToolsStorage()

    @override
    async def is_ready(self) -> bool:
        return True

    @override
    def fetch_tasks(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def get_task(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def task_version_resource_by_id(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def task_variant_latest_by_schema_id(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    async def count_examples(self, *args: Any, **kwargs: Any) -> int:
        return 0

    @override
    async def delete_example(self, *args: Any, **kwargs: Any) -> SerializableTaskExample:
        raise ObjectNotFoundException()

    @override
    async def get_any_input_by_hash(self, *args: Any, **kwargs: Any) -> Any:
        raise ObjectNotFoundException()

    @override
    def get_inputs_by_hash(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def set_task_description(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def get_latest_idx(self, *args: Any, **kwargs: Any) -> int:
        return 0

    @override
    async def get_latest_group_iteration(self, *args: Any, **kwargs: Any) -> int:
        return 0

    @override
    def fetch_example_resources(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        if False:
            yield None

    @override
    async def store_example_resource(
        self,
        task: SerializableTaskVariant,
        example: SerializableTaskExample,
    ) -> SerializableTaskExample:
        return example

    @override
    async def get_or_create_task_group(self, *args: Any, **kwargs: Any) -> TaskGroup:
        return TaskGroup(id="", iteration=0, properties=TaskGroupProperties(), tags=[])

    @override
    async def delete_task(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def prepare_task_run(
        self,
        task: SerializableTaskVariant,
        run: AgentRun,
        user: UserIdentifier | None,
        source: SourceType | None,
    ) -> AgentRun:
        return run

    @override
    async def store_task_resource(self, *args: Any, **kwargs: Any) -> tuple[SerializableTaskVariant, bool]:
        return args[0], False

    @override
    async def store_task_run_resource(
        self,
        task: SerializableTaskVariant,
        run: AgentRun,
        user: UserIdentifier | None,
        source: SourceType | None,
    ) -> AgentRun:
        return run

    @override
    async def example_resource_by_id(self, *args: Any, **kwargs: Any) -> SerializableTaskExample:
        raise ObjectNotFoundException()

    @override
    async def task_group_by_id(
        self,
        task_id: str,
        task_schema_id: int,
        ref: int | VersionEnvironment | TaskGroupIdentifier,
    ) -> TaskGroup:
        return TaskGroup(id="", iteration=0, properties=TaskGroupProperties(), tags=[])


class NoopKeyValueStorage(KeyValueStorage):
    """Dummy, should only be used for testing"""

    @override
    async def get(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def set(self, *args: Any, **kwargs: Any) -> None:
        pass

    @override
    async def pop(self, *args: Any, **kwargs: Any) -> Any:
        return None

    @override
    async def expire(self, *args: Any, **kwargs: Any) -> None:
        pass
