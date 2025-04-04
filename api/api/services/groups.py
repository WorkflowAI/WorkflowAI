import logging
from typing import Any, NamedTuple, Optional

from api.services.analytics import AnalyticsService
from core.agents.detect_chain_of_thought_task import (
    DetectChainOfThoughtUsageTaskInput,
    run_detect_chain_of_thought_task,
)
from core.domain.consts import METADATA_KEY_DEPLOYMENT_ENVIRONMENT, METADATA_KEY_REQUESTED_ITERATION
from core.domain.errors import (
    InternalError,
    InvalidRunOptionsError,
)
from core.domain.events import EventRouter
from core.domain.models import Model
from core.domain.models import Provider as ProviderKind
from core.domain.task_group import TaskGroup, TaskGroupIdentifier
from core.domain.task_group_properties import TaskGroupProperties
from core.domain.task_variant import SerializableTaskVariant
from core.domain.tenant_data import ProviderSettings
from core.domain.tool import Tool
from core.domain.users import UserIdentifier
from core.domain.version_environment import VersionEnvironment
from core.domain.version_reference import VersionReference
from core.runners.abstract_runner import AbstractRunner
from core.runners.workflowai.noop_external_runner import NoopExternalRunner
from core.runners.workflowai.workflowai_runner import WorkflowAIRunner
from core.storage import ObjectNotFoundException
from core.storage.backend_storage import BackendStorage
from core.tools import get_tools_in_instructions


class SanitizedVersion(NamedTuple):
    properties: TaskGroupProperties
    id: TaskGroupIdentifier | None = None
    iteration: int | None = None
    environment: VersionEnvironment | None = None
    is_external: bool | None = None


class GroupService:
    def __init__(
        self,
        storage: BackendStorage,
        event_router: EventRouter,
        analytics_service: AnalyticsService,
        user: UserIdentifier,
    ):
        self.storage = storage
        self.event_router = event_router

        self.analytics_service = analytics_service
        self.user = user
        self._logger = logging.getLogger(self.__class__.__name__)

    async def create_task_group(
        self,
        task_id: str,
        task_schema_id: int,
        properties: TaskGroupProperties,
        user: UserIdentifier | None,
        disable_autosave: bool | None = None,
    ):
        runner, _ = await self.sanitize_groups_for_internal_runner(
            task_id=task_id,
            task_schema_id=task_schema_id,
            reference=VersionReference(properties=properties),
            detect_chain_of_thought=True,
        )
        properties = runner.properties

        return await self.storage.get_or_create_task_group(
            task_id,
            task_schema_id,
            properties,
            tags=[],
            is_external=False,
            id=None,
            user=user,
            disable_autosave=disable_autosave,
        )

    async def _sanitize_task_variant(
        self,
        task_id: str,
        task_schema_id: int,
        properties: TaskGroupProperties,
        variant: Optional[SerializableTaskVariant] = None,
    ):
        if variant:
            if properties.task_variant_id != variant.id:
                self._logger.warning(
                    "Task variant id does not match task id",
                    extra={"task_variant_id": properties.task_variant_id, "task_id": task_id},
                )
            return variant

        if variant_id := properties.task_variant_id:
            try:
                task_variant = await self.storage.task_version_resource_by_id(task_id, variant_id)
                if task_variant.task_id != task_id or task_variant.task_schema_id != task_schema_id:
                    # We raise an error since it should never happen
                    self._logger.error(
                        "Group was created for a different task id or schema id than the one provided",
                        extra={
                            "task_variant_id": variant_id,
                            "task_id": task_id,
                            "task_schema_id": task_schema_id,
                        },
                    )
                    # but we allow to continue by selecting the latest task variant
                else:
                    return task_variant
            except ObjectNotFoundException:
                # It is possible that a user create a group with a task_variant_id property
                # but that is very unlikely so we should still log.
                self._logger.exception(
                    "Task variant not found",
                    extra={
                        "group": properties.model_dump(exclude_none=True),
                        "task_id": task_id,
                        "task_schema_id": task_schema_id,
                        "task_variant_id": properties.task_variant_id,
                    },
                )
                pass

        return await self.storage.task_variant_latest_by_schema_id(task_id, task_schema_id)

    @staticmethod
    def _get_provider_kind_or_raise(provider: str) -> ProviderKind:
        try:
            return ProviderKind(provider)
        except (ValueError, NameError):
            raise InvalidRunOptionsError(f"Provider {provider} is not valid")

    @staticmethod
    def _get_model_or_raise(model: str) -> Model:
        try:
            return Model(model)
        except (ValueError, NameError):
            raise InvalidRunOptionsError(f"Model {model} is not valid")

    async def _sanitize_group_properties(
        self,
        task: SerializableTaskVariant,
        properties: TaskGroupProperties,
    ) -> TaskGroupProperties:
        if properties.task_variant_id != task.id:
            if not properties.task_variant_id:
                properties.task_variant_id = task.id
            else:
                raise InternalError(
                    "Task variant id does not match task id",
                    extra={
                        "task_variant_id": properties.task_variant_id,
                        "task_id": task.id,
                    },
                )

        return properties

    async def sanitize_version_reference(
        self,
        task_id: str,
        task_schema_id: int,
        reference: VersionReference,
        is_external: bool | None = None,
    ):
        if reference.properties:
            return SanitizedVersion(reference.properties, is_external=is_external)

        if isinstance(reference.version, int):
            group = await self.storage.task_groups.get_task_group_by_iteration(
                task_id,
                task_schema_id,
                reference.version,
            )

            return SanitizedVersion(
                group.properties,
                id=group.id,
                iteration=reference.version,
                is_external=group.is_external,
            )

        if isinstance(reference.version, VersionEnvironment):
            deployment = await self.storage.task_deployments.get_task_deployment(
                task_id,
                task_schema_id,
                reference.version,
            )
            return SanitizedVersion(
                deployment.properties,
                iteration=deployment.iteration,
                environment=reference.version,
            )

        if not reference.version:
            raise InternalError(
                "Invalid group version",
                capture=True,
                extras={"task_id": task_id, "task_schema_id": task_schema_id, "version": reference.version},
            )

        # Now it's either a string or a major minor
        group = await self.storage.task_groups.get_task_group_by_id(
            task_id,
            reference.version,
        )
        return SanitizedVersion(
            group.properties,
            id=reference.version,
            iteration=group.iteration,
            is_external=group.is_external,
        )

    async def _is_chain_of_thought_detected(
        self,
        task_instructions: str | None,
        task_output_schema: dict[str, Any],
    ) -> bool:
        if task_instructions in (None, ""):
            # No need to detect COT if there are no instructions
            return False

        task_input = DetectChainOfThoughtUsageTaskInput(
            task_instructions=task_instructions,
            task_output_schema=task_output_schema,
        )
        task_output = await run_detect_chain_of_thought_task(task_input)

        return task_output.should_use_chain_of_thought

    @classmethod
    def _set_enabled_tools(cls, group_properties: TaskGroupProperties):
        enabled_tools = set(group_properties.enabled_tools or [])
        tools_in_instructions = get_tools_in_instructions(group_properties.instructions or "")
        enabled_tools.update(tools_in_instructions)

        group_properties.enabled_tools = (
            sorted(
                enabled_tools,
                key=lambda x: x.name.lower() if isinstance(x, Tool) else x.value.replace("@", "").lower(),
            )
            if enabled_tools
            else None
        )

    async def _build_runner_from_properties(
        self,
        task: SerializableTaskVariant,
        sanitized_version: SanitizedVersion,
        custom_configs: list[ProviderSettings] | None,
        disable_fallback: bool,
    ) -> AbstractRunner[Any]:
        metadata: dict[str, Any] = {}
        if sanitized_version.environment:
            metadata[METADATA_KEY_DEPLOYMENT_ENVIRONMENT] = sanitized_version.environment
        if sanitized_version.iteration:
            metadata[METADATA_KEY_REQUESTED_ITERATION] = sanitized_version.iteration

        runner = WorkflowAIRunner(
            task=task,
            cache_fetcher=self.storage.task_runs.fetch_cached_run,
            properties=sanitized_version.properties,
            metadata=metadata or None,
            custom_configs=custom_configs,
            disable_fallback=disable_fallback,
        )
        await runner.validate_run_options()
        return runner

    async def _detect_and_assign_chain_of_thought(
        self,
        task_id: str,
        task_instructions: str | None,
        task_output_schema: dict[str, Any],
        properties: TaskGroupProperties,
    ):
        if properties.is_chain_of_thought_enabled is not None:
            return

        try:
            is_chain_of_thought_enabled = await self._is_chain_of_thought_detected(
                task_instructions=task_instructions,
                task_output_schema=task_output_schema,
            )
        except Exception as e:
            # COT is not critical, so we prefer not blocking the group creation if any error occurs
            self._logger.exception(
                "Error detecting chain of thought",
                exc_info=e,
                extra={"task_id": task_id, "instructions": task_instructions, "output_schema": task_output_schema},
            )
            is_chain_of_thought_enabled = None
        properties.is_chain_of_thought_enabled = is_chain_of_thought_enabled

    async def sanitize_groups_for_internal_runner(  # noqa: C901
        self,
        task_id: str,
        task_schema_id: int,
        reference: VersionReference,
        variant: Optional[SerializableTaskVariant] = None,
        detect_chain_of_thought: bool = False,  # COT detection is only run when creating a group from POST /groups for now.
        # detect_structured_generation: bool = False,  # Structured generation detection is only run when creating a group from POST /groups for now.
        provider_settings: list[ProviderSettings] | None = None,
        disable_fallback: bool = False,
    ) -> tuple[AbstractRunner[Any], bool]:
        """
        The internal runner uses the full schema of a task (i-e not only the types that are described
        by the task_schema_id but also the additional metadata attributes like examples, description, etc, see
        core.utils.schemas.strip_metadata).

        The full schema of a task is at the moment stored in a task variant so we need to make sure to have
        the right task variant to make a group reproducible.
        """
        version = await self.sanitize_version_reference(task_id, task_schema_id, reference)
        variant = await self._sanitize_task_variant(task_id, task_schema_id, version.properties, variant)

        if version.is_external:
            return NoopExternalRunner(
                task=variant,
                group=TaskGroup(iteration=version.iteration or 0, properties=version.properties),
                cache_fetcher=self.storage.task_runs.fetch_cached_run,
            ), True

        if not version.iteration:
            # Check for enabled tools
            self._set_enabled_tools(version.properties)

            # Check for chain of thought
            if detect_chain_of_thought:
                await self._detect_and_assign_chain_of_thought(
                    task_id=task_id,
                    task_instructions=version.properties.instructions,
                    task_output_schema=variant.output_schema.json_schema,
                    properties=version.properties,
                )
            # Check for structured generation
            # if detect_structured_generation:
            #     await self._enable_structured_generation_if_supported(
            #         properties=version.properties,
            #         task_name=variant.name,
            #         output_schema=variant.output_schema.json_schema,
            #     )

        elif detect_chain_of_thought:  # or detect_structured_generation
            self._logger.warning(
                "Skipping chain of thought or structured generation detection since we have an iteration",
                extra={"task_id": task_id, "task_schema_id": task_schema_id, "version": version},
            )
        runner = await self._build_runner_from_properties(
            variant,
            version,
            custom_configs=provider_settings,
            disable_fallback=disable_fallback,
        )
        is_different_version = version.properties.model_dump(exclude_none=True) != runner.properties.model_dump(
            exclude_none=True,
        )

        return runner, is_different_version

    async def get_or_create_group(
        self,
        task_id: str,
        task_schema_id: int,
        reference: VersionReference,
        variant: Optional[SerializableTaskVariant] = None,
    ) -> TaskGroup:
        runner, _ = await self.sanitize_groups_for_internal_runner(
            task_id=task_id,
            task_schema_id=task_schema_id,
            reference=reference,
            variant=variant,
        )
        return await self.storage.get_or_create_task_group(
            task_id,
            task_schema_id,
            runner.properties,
            runner.group_tags(),
            user=self.user,
        )
