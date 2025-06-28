import asyncio
import logging

from core.storage.mongo.migrations.base import AbstractMigration
from core.storage.mongo.migrations.migrations.m2024_07_21_first import FirstMigration
from core.storage.mongo.migrations.migrations.m2024_07_22_add_task_input_dataset_index import AddTaskInputDatasetIndex
from core.storage.mongo.migrations.migrations.m2024_07_31_dataset_benchmarks import DatasetBenchmarksMigration
from core.storage.mongo.migrations.migrations.m2024_08_15_task_names import AddTaskNamesMigration
from core.storage.mongo.migrations.migrations.m2024_08_16_org_indices import AddOrgIndicesMigration
from core.storage.mongo.migrations.migrations.m2024_08_19_task_run_indices import AddTaskRunIndicesMigration
from core.storage.mongo.migrations.migrations.m2024_08_23_task_run_updated_at import AddTaskRunUpdatedAt
from core.storage.mongo.migrations.migrations.m2024_09_17_add_run_fetch_idx import AddRunFetchIndex
from core.storage.mongo.migrations.migrations.m2024_09_23_add_task_description_field import AddTaskDescriptionField
from core.storage.mongo.migrations.migrations.m2024_09_24_add_changelogs import CreateChangelogsCollectionMigration
from core.storage.mongo.migrations.migrations.m2024_09_27_add_input_evaluations import InputEvaluationsIndexMigration
from core.storage.mongo.migrations.migrations.m2024_10_06_add_run_by_hash_score_idx import (
    AddTaskRunByHashWithScoresIndexMigration,
)
from core.storage.mongo.migrations.migrations.m2024_10_07_add_run_by_status_idx import AddTaskRunByStatusIndexMigration
from core.storage.mongo.migrations.migrations.m2024_10_11_add_run_by_metadata_used_alias import (
    AddTaskRunByMetadataUsedAliasMigration,
)
from core.storage.mongo.migrations.migrations.m2024_10_18_add_run_by_model_idx import AddTaskRunByModelIndexMigration
from core.storage.mongo.migrations.migrations.m2024_10_18_add_run_by_temperature_idx import (
    AddTaskRunByTemperatureIndexMigration,
)
from core.storage.mongo.migrations.migrations.m2024_10_25_add_transcriptions_file_idx import (
    AddTranscriptionsFileIdIndexMigration,
)
from core.storage.mongo.migrations.migrations.m2024_11_11_org_api_keys_indices import AddOrgAPIKeysIndicesMigration
from core.storage.mongo.migrations.migrations.m2024_11_13_review_indices import (
    AddReviewIndicesMigration,
)
from core.storage.mongo.migrations.migrations.m2024_11_18_review_benchmarks import AddReviewBenchmarkIndicesMigration
from core.storage.mongo.migrations.migrations.m2024_11_19_run_io_index import AddTaskRunInputOutputHashesIndexMigration
from core.storage.mongo.migrations.migrations.m2024_11_20_task_deployments_index import (
    AddTaskDeploymentsUniqueIndexMigration,
)
from core.storage.mongo.migrations.migrations.m2025_01_03_task_group_semvers_index import (
    AddTaskGroupSemversUniqueIndexMigration,
)
from core.storage.mongo.migrations.migrations.m2025_01_08_deployment_by_iteration_idx import (
    DeploymentByIterationIdxMigration,
)
from core.storage.mongo.migrations.migrations.m2025_01_18_reviews_non_stale_index import (
    AddReviewsNonStaleIndexMigration,
)
from core.storage.mongo.migrations.migrations.m2025_02_05_unique_ids import AddUniqueIdsMigration
from core.storage.mongo.migrations.migrations.m2025_02_06_anon_user_id_unique_index import (
    AddAnonymousUserIdUniqueIndexMigration,
)
from core.storage.mongo.migrations.migrations.m2025_02_07_review_eval_hash import AddReviewEvalHashIndexMigration
from core.storage.mongo.migrations.migrations.m2025_03_07_org_settings_idx import OrgSettingsIndicesMigration
from core.storage.mongo.migrations.migrations.m2025_03_18_feedback import FeedbackIndicesMigration
from core.storage.mongo.migrations.migrations.m2025_04_14_fix_org_index import FixOrgIndexMigration
from core.storage.mongo.migrations.migrations.m2025_05_01_tools_indices import AddToolsIndicesMigration
from core.storage.mongo.migrations.migrations.m2025_05_05_add_org_slack_and_hashed_key_indices import (
    AddOrgSlackAndHashedKeyIndicesMigration,
)
from core.storage.mongo.migrations.migrations.m2025_05_06_fix_api_key_id_index import FixAPIKeyIdIndexMigration
from core.storage.mongo.mongo_storage import MongoStorage

MIGRATIONS: list[type[AbstractMigration]] = [
    FirstMigration,
    AddTaskInputDatasetIndex,
    DatasetBenchmarksMigration,
    AddTaskNamesMigration,
    AddOrgIndicesMigration,
    AddTaskRunIndicesMigration,
    AddTaskRunUpdatedAt,
    AddRunFetchIndex,
    AddTaskDescriptionField,
    CreateChangelogsCollectionMigration,
    InputEvaluationsIndexMigration,
    AddTaskRunByHashWithScoresIndexMigration,
    AddTaskRunByStatusIndexMigration,
    AddTaskRunByMetadataUsedAliasMigration,
    AddTaskRunByModelIndexMigration,
    AddTaskRunByTemperatureIndexMigration,
    AddTranscriptionsFileIdIndexMigration,
    AddOrgAPIKeysIndicesMigration,
    AddReviewIndicesMigration,
    AddReviewBenchmarkIndicesMigration,
    AddTaskRunInputOutputHashesIndexMigration,
    AddTaskDeploymentsUniqueIndexMigration,
    AddTaskGroupSemversUniqueIndexMigration,
    DeploymentByIterationIdxMigration,
    AddReviewsNonStaleIndexMigration,
    AddUniqueIdsMigration,
    AddAnonymousUserIdUniqueIndexMigration,
    AddReviewEvalHashIndexMigration,
    OrgSettingsIndicesMigration,
    FeedbackIndicesMigration,
    FixOrgIndexMigration,
    AddToolsIndicesMigration,
    AddOrgSlackAndHashedKeyIndicesMigration,
    FixAPIKeyIdIndexMigration,
]


async def _wait_for_migration_lock(storage: MongoStorage, max_retries: int, sleep_delay: float):
    locked = await storage.lock_migrations()
    if locked:
        return

    for _ in range(max_retries):
        locked = await storage.lock_migrations()
        if locked:
            return
        await asyncio.sleep(sleep_delay)

    raise TimeoutError("Could not acquire migration lock")


async def perform_rollback(
    migrations: list[type[AbstractMigration]],
    existing_migrations: list[str],
    min_len: int,
    storage: MongoStorage,
    logger: logging.Logger,
):
    to_rollback = list(reversed(existing_migrations[min_len:]))
    possible_rollbacks = list(reversed(migrations[min_len:]))
    if len(to_rollback) != len(possible_rollbacks):
        logger.warning(f"Skipping rollback of {len(to_rollback)} migrations: {to_rollback}")  # noqa G004
        return

    for migration in possible_rollbacks:
        migration_instance = migration(storage)
        logger.info(f"Starting rollback of {migration_instance.name()}")  # noqa G004
        await migration_instance.rollback()
        await storage.remove_migration(migration_instance.name())
        logger.info(f"Finished rollback of {migration_instance.name()}")  # noqa G004


async def migrate(
    storage: MongoStorage,
    max_retries: int = 50,
    migrations: list[type[AbstractMigration]] | None = None,
    sleep_delay: float = 1,
):
    _logger = logging.getLogger(__name__)

    if migrations is None:
        migrations = MIGRATIONS

    _logger.info("Starting migrations")

    await _wait_for_migration_lock(storage, max_retries=max_retries, sleep_delay=sleep_delay)

    _logger.info("Acquired migration lock")

    existing_migrations = await storage.list_migrations()
    rollback = len(existing_migrations) > len(migrations)
    min_len = min(len(existing_migrations), len(migrations))

    # Safety to make sure the existing migrations have not changed
    # Caution: this does not allow squashing migrations
    for i in range(min_len):
        if existing_migrations[i] != migrations[i].name():
            raise AssertionError(f"Migration {migrations[i].name()} does not match {existing_migrations[i]}")

    if rollback:
        await perform_rollback(migrations, existing_migrations, min_len, storage, _logger)
    else:
        _logger.info(f"Performing {len(migrations[min_len:])} migrations")  # noqa G004
        for migration in migrations[min_len:]:
            migration_instance = migration(storage)
            _logger.info(f"Starting {migration_instance.name()}")  # noqa G004
            await migration_instance.apply()
            await storage.add_migration(migration_instance.name())
            _logger.info(f"Finished {migration_instance.name()}")  # noqa G004

    _logger.info("Finished MIGRATIONS")
    _logger.info("Releasing migration lock")
    await storage.unlock_migrations()


class MigrationCheckError(Exception):
    def __init__(self, message: str, migrations: list[type[AbstractMigration]], existing_migrations: list[str]):
        super().__init__(message)
        self.migrations = migrations
        self.existing_migrations = existing_migrations


async def check_migrations(storage: MongoStorage, migrations: list[type[AbstractMigration]] | None = None):
    """Raises an AssertionError if the migrations are not in sync"""
    if migrations is None:
        migrations = MIGRATIONS

    existing_migrations = await storage.list_migrations()
    min_len = min(len(existing_migrations), len(migrations))
    # Safety to make sure the existing migrations have not changed
    # Caution: this does not allow squashing migrations
    for i in range(min_len):
        if existing_migrations[i] != migrations[i].name():
            raise MigrationCheckError(
                f"Migration {migrations[i].name()} does not match existing {existing_migrations[i]}",
                migrations=migrations,
                existing_migrations=existing_migrations,
            )

    if len(existing_migrations) > len(migrations):
        raise MigrationCheckError(
            f"There are more migrations than expected: {existing_migrations[:min_len]}",
            migrations=migrations,
            existing_migrations=existing_migrations,
        )

    if len(existing_migrations) < len(migrations):
        names = [migration.name() for migration in migrations[min_len:]]
        raise MigrationCheckError(
            f"Migrations are needed: {names}",
            migrations=migrations,
            existing_migrations=existing_migrations,
        )

    print("Migrations are in sync")  # noqa G004
