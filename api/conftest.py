import json
import os
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from freezegun import freeze_time
from httpx import ASGITransport, AsyncClient

from core.domain.models.providers import Provider
from core.domain.organization_settings import PublicOrganizationData
from core.domain.task_info import TaskInfo
from core.domain.task_io import SerializableTaskIO
from core.domain.task_variant import SerializableTaskVariant
from core.domain.users import User
from core.utils.schemas import JsonSchema
from tests.asgi_transport import patch_asgi_transport
from tests.utils import fixtures_json

_PATCHED_BEDROCK_REGION_MAP = {
    "claude-3-5-sonnet-20241022": "us-west-2",
    "claude-3-5-sonnet-20240620": "us-west-2",
    "claude-3-opus-20240229": "us-west-2",
    "claude-3-sonnet-20240229": "us-west-2",
    "claude-3-haiku-20240307": "us-west-2",
    "llama-3.1-405b": "us-west-2",
    "llama-3.1-70b": "us-west-2",
    "llama-3.1-8b": "us-west-2",
    "mistral-large-2-2407": "us-west-2",
    "llama-3.2-90b": "us-west-2",
    "llama-3.2-11b": "us-west-2",
    "llama-3.2-3b": "us-west-2",
    "llama-3.2-1b": "us-west-2",
}

# TODO: add an autouse fixture to set the env variables
if "WORKFLOWAI_TEST_MONGO_CONNECTION_STRING" not in os.environ:
    os.environ["WORKFLOWAI_TEST_MONGO_CONNECTION_STRING"] = "mongodb://admin:admin@localhost:27017/workflowai_test"
if "WORKFLOWAI_MONGO_CONNECTION_STRING" not in os.environ:
    os.environ["WORKFLOWAI_MONGO_CONNECTION_STRING"] = "mongodb://admin:admin@localhost:27017/workflowai_test"
if "WORKFLOWAI_TENANT" not in os.environ:
    os.environ["WORKFLOWAI_TENANT"] = "test"
if "STORAGE_HMAC" not in os.environ:
    os.environ["STORAGE_AES"] = "ruQBOB/yrSJYw+hozAGewJx5KAadHAMPnATttB2dmig="
if "STORAGE_HMAC" not in os.environ:
    os.environ["STORAGE_HMAC"] = "ATWcst2v/c/KEypN99ujwOySMzpwCqdaXvHLGDqBt+c="
if "WORKFLOWAI_JWKS_URL" not in os.environ:
    os.environ["WORKFLOWAI_JWKS_URL"] = ""

if "WORKFLOWAI_JWK" not in os.environ:
    os.environ["WORKFLOWAI_JWK"] = (
        "eyJrdHkiOiJFQyIsIngiOiJLVUpZYzd2V0R4Um55NW5BdC1VNGI4MHRoQ1ZuaERUTDBzUmZBRjR2cDdVIiwieSI6IjM0dWx1VDgyT0RFRFJXVU9KNExrZzFpanljclhqMWc1MmZRblpqeFc5cTAiLCJjcnYiOiJQLTI1NiIsImlkIjoiMSJ9Cg=="
    )
if "AWS_BEDROCK_MODEL_REGION_MAP" not in os.environ:
    os.environ["AWS_BEDROCK_MODEL_REGION_MAP"] = json.dumps(_PATCHED_BEDROCK_REGION_MAP)
if "AWS_BEDROCK_SECRET_KEY" not in os.environ:
    os.environ["AWS_BEDROCK_SECRET_KEY"] = "secret"
if "AWS_BEDROCK_ACCESS_KEY" not in os.environ:
    os.environ["AWS_BEDROCK_ACCESS_KEY"] = "access"
if "CLERK_WEBHOOKS_SECRET" not in os.environ:
    os.environ["CLERK_WEBHOOKS_SECRET"] = "whsec_LCi7t70Dv3NryHc386aaOzjgDPl/Ta/D"

if "STRIPE_WEBHOOK_SECRET" not in os.environ:
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_LCi7t70Dv3NryHc386aaOzjgDPl/Ta/D"
if "STRIPE_API_KEY" not in os.environ:
    os.environ["STRIPE_API_KEY"] = "sk-proj-123"

if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = "sk-proj-123"
if "GROQ_API_KEY" not in os.environ:
    os.environ["GROQ_API_KEY"] = "gsk-proj-123"

if "AZURE_OPENAI_CONFIG" not in os.environ:
    os.environ["AZURE_OPENAI_CONFIG"] = (
        '{"deployments": {"eastus": { "url": "https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/", "api_key": "sk-proj-123", "models": ["gpt-4o-2024-11-20", "gpt-4o-mini-2024-07-18"]}}, "default_region": "eastus"}'
    )

# add ['GOOGLE_VERTEX_AI_PROJECT_ID', 'GOOGLE_VERTEX_AI_LOCATION', 'GOOGLE_VERTEX_AI_CREDENTIALS']
if "GOOGLE_VERTEX_AI_PROJECT_ID" not in os.environ:
    os.environ["GOOGLE_VERTEX_AI_PROJECT_ID"] = "worfklowai"
if "GOOGLE_VERTEX_AI_LOCATION" not in os.environ:
    os.environ["GOOGLE_VERTEX_AI_LOCATION"] = "us-central1"
if "GOOGLE_VERTEX_AI_CREDENTIALS" not in os.environ:
    os.environ["GOOGLE_VERTEX_AI_CREDENTIALS"] = '{"type":"service_account","project_id":"worfklowai"}'

if "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = "sk-proj-123"


if "FIREWORKS_API_KEY" not in os.environ:
    os.environ["FIREWORKS_API_KEY"] = "sk-proj-123"
if "FIREWORKS_API_URL" not in os.environ:
    os.environ["FIREWORKS_API_URL"] = "https://api.fireworks.ai/inference/v1/chat/completions"

if "MISTRAL_API_KEY" not in os.environ:
    os.environ["MISTRAL_API_KEY"] = "sk-proj-123"

if "ANTHROPIC_API_KEY" not in os.environ:
    os.environ["ANTHROPIC_API_KEY"] = "sk-proj-1234"

if "WORKFLOWAI_API_URL" not in os.environ:
    os.environ["WORKFLOWAI_API_URL"] = "http://0.0.0.0:8000"
if "WORKFLOWAI_API_KEY" not in os.environ:
    os.environ["WORKFLOWAI_API_KEY"] = "sk-proj-123"

if "WORKFLOWAI_STORAGE_CONNECTION_STRING" not in os.environ:
    # Use the default storage connection string for tests
    os.environ["WORKFLOWAI_STORAGE_CONNECTION_STRING"] = (
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    )

if "WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER" not in os.environ:
    # Use the default storage container for tests
    os.environ["WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER"] = "workflowai-test-task-runs"

if "FIRECRAWL_API_KEY" not in os.environ:
    os.environ["FIRECRAWL_API_KEY"] = "firecrawl-api-key"

if "SCRAPINGBEE_API_KEY" not in os.environ:
    os.environ["SCRAPINGBEE_API_KEY"] = "scrapingbee-api-key"

if "SERPER_API_KEY" not in os.environ:
    os.environ["SERPER_API_KEY"] = "serper-api-key"

if "PERPLEXITY_API_KEY" not in os.environ:
    os.environ["PERPLEXITY_API_KEY"] = "perplexity-api-key"

if "MODERATION_ENABLED" not in os.environ:
    os.environ["MODERATION_ENABLED"] = "false"

if "CLICKHOUSE_TEST_CONNECTION_STRING" not in os.environ:
    os.environ["CLICKHOUSE_TEST_CONNECTION_STRING"] = "clickhouse://default:admin@localhost:8123/db_test"

os.environ["JOBS_BROKER_URL"] = "memory://"


@pytest.fixture(scope="function")
def mock_storage() -> AsyncMock:
    from core.storage.backend_storage import BackendStorage
    from core.storage.changelogs_storage import ChangeLogStorage
    from core.storage.evaluator_storage import EvaluatorStorage
    from core.storage.input_evaluations_storage import InputEvaluationStorage
    from core.storage.organization_storage import OrganizationStorage
    from core.storage.review_benchmark_storage import ReviewBenchmarkStorage
    from core.storage.reviews_storage import ReviewsStorage
    from core.storage.task_deployments_storage import TaskDeploymentsStorage
    from core.storage.task_group_storage import TaskGroupStorage
    from core.storage.task_input_storage import TaskInputsStorage
    from core.storage.task_run_storage import TaskRunStorage
    from core.storage.task_storage import TaskStorage
    from core.storage.task_variants_storage import TaskVariantsStorage

    mock = AsyncMock(spec=BackendStorage)
    mock.evaluators = AsyncMock(spec=EvaluatorStorage)
    mock.task_variants = AsyncMock(spec=TaskVariantsStorage)
    mock.tasks = AsyncMock(spec=TaskStorage)
    mock.task_runs = AsyncMock(spec=TaskRunStorage)
    mock.task_inputs = AsyncMock(spec=TaskInputsStorage)
    mock.task_groups = AsyncMock(spec=TaskGroupStorage)
    mock.organizations = AsyncMock(spec=OrganizationStorage)
    mock.changelogs = AsyncMock(spec=ChangeLogStorage)
    mock.reviews = AsyncMock(spec=ReviewsStorage)
    mock.review_benchmarks = AsyncMock(spec=ReviewBenchmarkStorage)
    mock.task_deployments = AsyncMock(spec=TaskDeploymentsStorage)
    mock.input_evaluations = AsyncMock(spec=InputEvaluationStorage)
    return mock


@pytest.fixture
def mock_cache_fetcher(mock_storage: Mock):
    return mock_storage.task_runs.fetch_cached_run


@pytest.fixture(scope="function")
def mock_wai(mock_storage: Mock) -> Mock:
    from core.deprecated.workflowai import WorkflowAI

    wai = AsyncMock(spec=WorkflowAI)
    wai.storage = mock_storage
    return wai


@pytest.fixture(scope="function")
def mock_wai_context(mock_wai: Any):
    from core.deprecated.workflowai import WorkflowAI

    with patch.object(WorkflowAI, "from_ctx") as mock_wai_context:
        mock_wai_context.return_value = mock_wai
        yield mock_wai


@pytest.fixture(scope="function")
def mock_user_dep() -> Mock:
    from api.dependencies.security import user_auth_dependency

    mock = Mock(spec=user_auth_dependency)
    mock.return_value = User(tenant="test", sub="g")
    return mock


def _reset_encryption_mock(mock: Mock):
    mock.reset_mock()

    mock.encrypt.side_effect = lambda value: value + "_encrypted"  # type:ignore

    def _decrypt(value: str) -> str:
        if not value.endswith("_encrypted"):
            raise ValueError("Invalid value")
        return value[:-10]

    mock.decrypt.side_effect = _decrypt


# A fixture to use for the entire session
@pytest.fixture(scope="session")
def mock_encryption_session():
    from core.utils.encryption import Encryption

    mock = Mock(spec=Encryption)
    _reset_encryption_mock(mock)
    return mock


@pytest.fixture
def mock_encryption(mock_encryption_session: Mock) -> Mock:
    _reset_encryption_mock(mock_encryption_session)
    return mock_encryption_session


@pytest.fixture(scope="function")
def mock_key_ring() -> Mock:
    from api.services.keys import KeyRing

    return AsyncMock(spec=KeyRing)


@pytest.fixture(scope="function")
def mock_tenant_dep() -> Mock:
    from api.dependencies.security import final_tenant_data

    mock = AsyncMock(spec=final_tenant_data)
    mock.return_value = PublicOrganizationData(tenant="test", uid=1)
    return mock


@pytest.fixture(scope="function")
def mock_user_org_dep() -> Mock:
    from api.dependencies.security import user_organization

    mock = AsyncMock(spec=user_organization)
    from core.domain.organization_settings import TenantData

    mock.return_value = TenantData(tenant="test", slug="test")
    return mock


@pytest.fixture(scope="function")
def mock_url_public_org_dep() -> Mock:
    from api.dependencies.security import url_public_organization

    mock = AsyncMock(spec=url_public_organization)
    from core.domain.organization_settings import PublicOrganizationData

    mock.return_value = PublicOrganizationData(tenant="test1", slug="test2")
    return mock


@pytest.fixture(scope="function")
def mock_system_storage_dep(mock_storage: Mock) -> Mock:
    from api.dependencies.security import system_org_storage

    mock = Mock(spec=system_org_storage)
    mock.return_value = mock_storage.organizations
    return mock


@pytest.fixture(scope="function")
def mock_group_service() -> Mock:
    from api.services.groups import GroupService

    return AsyncMock(spec=GroupService)


@pytest.fixture(scope="function")
def mock_analytics_service() -> Mock:
    from api.services.analytics import AnalyticsService

    return AsyncMock(spec=AnalyticsService)


@pytest.fixture(scope="function")
def mock_run_service() -> Mock:
    from api.services.run import RunService

    return AsyncMock(spec=RunService)


@pytest.fixture(scope="function")
def mock_event_router() -> Mock:
    from core.domain.events import EventRouter

    return Mock(spec=EventRouter)


@pytest.fixture()
def mock_file_storage():
    from core.storage.azure.azure_blob_file_storage import FileStorage

    return AsyncMock(name="file_storage", spec=FileStorage)


@pytest.fixture(scope="function")
def mock_reviews_service() -> Mock:
    from api.services.reviews import ReviewsService

    return Mock(spec=ReviewsService)


@pytest.fixture(scope="function")
def mock_models_service() -> Mock:
    from api.services.models import ModelsService

    return Mock(spec=ModelsService)


@pytest.fixture(scope="function")
def mock_internal_tasks_service() -> Mock:
    from api.services.internal_tasks.improve_prompt_service import ImprovePromptService
    from api.services.internal_tasks.internal_tasks_service import InternalTasksService
    from api.services.internal_tasks.task_input_service import TaskInputService

    mock_service = Mock(spec=InternalTasksService)
    mock_service.input_import = Mock(spec=TaskInputService)
    mock_service.improve_prompt = Mock(spec=ImprovePromptService)

    return mock_service


@pytest.fixture()
def mock_provider_factory():
    from core.providers.base.abstract_provider import AbstractProvider
    from core.providers.factory.abstract_provider_factory import AbstractProviderFactory

    def _mock_provider(name: Provider):
        m = Mock(spec=AbstractProvider)
        m.config_id = None
        m.requires_downloading_file.return_value = False
        m.sanitize_template.side_effect = lambda x: x  # pyright: ignore[reportUnknownLambdaType]
        m.sanitize_agent_instructions.side_effect = lambda x: x  # pyright: ignore[reportUnknownLambdaType]
        m.name.return_value = name
        return m

    google = _mock_provider(Provider.GOOGLE)
    gemini = _mock_provider(Provider.GOOGLE_GEMINI)
    openai = _mock_provider(Provider.OPEN_AI)
    anthropic = _mock_provider(Provider.ANTHROPIC)
    bedrock = _mock_provider(Provider.AMAZON_BEDROCK)
    azure_openai = _mock_provider(Provider.AZURE_OPEN_AI)

    def _side_effect(provider: Provider):
        if provider == Provider.GOOGLE:
            return google
        if provider == Provider.GOOGLE_GEMINI:
            return gemini
        if provider == Provider.OPEN_AI:
            return openai
        if provider == Provider.ANTHROPIC:
            return anthropic
        if provider == Provider.AMAZON_BEDROCK:
            return bedrock
        if provider == Provider.AZURE_OPEN_AI:
            return azure_openai
        assert False, "Invalid provider"

    mock = Mock(spec=AbstractProviderFactory)
    mock.get_provider.side_effect = _side_effect
    mock.get_providers.side_effect = lambda p: [_side_effect(p)]  # pyright: ignore
    mock.google = google
    mock.gemini = gemini
    mock.openai = openai
    mock.anthropic = anthropic
    mock.bedrock = bedrock
    mock.azure_openai = azure_openai
    return mock


# We make sure we have a test storage container for the tests
@pytest.fixture(scope="session")
async def test_blob_storage():
    from azure.core.pipeline.transport import AioHttpTransport
    from azure.storage.blob.aio import BlobServiceClient

    container_name = "workflowai-test-task-runs"

    with mock.patch.dict(
        os.environ,
        {
            "WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER": container_name,
        },
    ):
        clt = BlobServiceClient.from_connection_string(
            os.environ["WORKFLOWAI_STORAGE_CONNECTION_STRING"],
            transport=AioHttpTransport(
                connection_timeout=300.0,
                read_timeout=300.0,
                retries=3,
                maximum_valid_request_size=500 * 1024 * 1024,
            ),
        )

        try:
            # Check if the container exists
            await clt.get_container_client(container_name).get_container_properties()
        except Exception:
            # Creating the container dynamically since it will not exist in the test environment
            await clt.create_container(container_name)
        yield


# TODO: we should really move this conf to `/api/routers` it should not be used elsewhere
@pytest.fixture(scope="function")
def test_app(
    mock_storage: Mock,
    mock_wai: Mock,
    mock_user_dep: Mock,
    mock_encryption: Mock,
    mock_key_ring: Mock,
    mock_tenant_dep: Mock,
    mock_group_service: Mock,
    mock_event_router: Mock,
    mock_user_org_dep: Mock,
    mock_system_storage_dep: Mock,
    mock_url_public_org_dep: Mock,
    mock_internal_tasks_service: Mock,
    mock_reviews_service: Mock,
    mock_models_service: Mock,
    mock_provider_factory: Mock,
):
    from api.dependencies.encryption import EncryptionDep, encryption_dependency
    from api.dependencies.event_router import event_router_dependency
    from api.dependencies.provider_factory import _provider_factory  # pyright: ignore [reportPrivateUsage]
    from api.dependencies.security import (
        BearerDep,
        KeyRingDep,
        OrgSystemStorageDep,
        UserDep,
        UserOrganizationDep,
        final_tenant_data,
        key_ring_dependency,
        system_org_storage,
        url_public_organization,
        user_auth_dependency,
        user_organization,
    )
    from api.dependencies.services import (
        group_service,
        internal_tasks,
        models_service,
        reviews_service,
        workflowai_dependency,
    )
    from api.dependencies.storage import storage_dependency
    from api.main import app
    from api.services.keys import KeyRing

    # Ultimately we shoud have a client builder to avoid this boilerplate
    app.dependency_overrides = {}

    mock_storage.tasks.get_task_info.return_value = TaskInfo(task_id="test", uid=1)
    app.dependency_overrides[storage_dependency] = lambda: mock_storage

    async def _mock_user_auth_dependency(
        keys: KeyRingDep,
        request: BearerDep,
    ) -> User:
        return await mock_user_dep(keys, request)  # type:ignore

    async def _mock_tenant_dependancy(
        user: UserDep,
        user_org: UserOrganizationDep,
        system_storage: OrgSystemStorageDep,
        request: Request,
        encryption: EncryptionDep,
    ):
        return await mock_tenant_dep(user, user_org, system_storage, request, encryption)

    app.dependency_overrides[user_auth_dependency] = _mock_user_auth_dependency
    app.dependency_overrides[workflowai_dependency] = lambda: mock_wai

    async def _user_organization_dependency(
        user: UserDep,
        system_storage: OrgSystemStorageDep,
    ):
        return await mock_user_org_dep(user, system_storage)

    async def _url_public_organization_dependency(
        user: UserDep,
        system_storage: OrgSystemStorageDep,
    ):
        return await mock_url_public_org_dep(user, system_storage)

    app.dependency_overrides[user_organization] = _user_organization_dependency
    app.dependency_overrides[url_public_organization] = _url_public_organization_dependency

    async def _system_org_storage_dependency(encryption: EncryptionDep):
        return mock_system_storage_dep(encryption)

    app.dependency_overrides[system_org_storage] = _system_org_storage_dependency

    async def _mock_key_ring_dependency() -> KeyRing:
        return mock_key_ring

    app.dependency_overrides[key_ring_dependency] = _mock_key_ring_dependency
    app.dependency_overrides[encryption_dependency] = lambda: mock_encryption
    app.dependency_overrides[final_tenant_data] = _mock_tenant_dependancy

    app.dependency_overrides[group_service] = lambda: mock_group_service
    app.dependency_overrides[event_router_dependency] = lambda: mock_event_router
    app.dependency_overrides[internal_tasks] = lambda: mock_internal_tasks_service
    app.dependency_overrides[reviews_service] = lambda: mock_reviews_service
    app.dependency_overrides[models_service] = lambda: mock_models_service
    app.dependency_overrides[_provider_factory] = lambda: mock_provider_factory
    return app


@pytest_asyncio.fixture(scope="function")  # type:ignore
async def test_api_client(test_app: FastAPI, request: pytest.FixtureRequest):
    async with patch_asgi_transport():
        headers = {"Authorization": "Bearer b"}  # Default to authenticated
        if request.node.get_closest_marker("unauthenticated"):  # pyright: ignore [reportUnknownMemberType]
            headers.pop("Authorization", None)  # Remove auth for unauthenticated tests
        yield AsyncClient(
            transport=ASGITransport(app=test_app),  # pyright: ignore [reportArgumentType]
            base_url="http://0.0.0.0",
            headers=headers,
        )


# Register custom marker
def pytest_configure(config: pytest.Config):
    config.addinivalue_line("markers", "unauthenticated: mark test to run without authentication")


# TODO: these have nothing to do here. We sdhould move to schemas_test once we have remove field_based_evaluation_config_test
@pytest.fixture(scope="function")
def schema_1() -> JsonSchema:
    raw = fixtures_json("jsonschemas", "schema_1.json")
    return JsonSchema(raw)


@pytest.fixture(scope="function")
def schema_2() -> JsonSchema:
    raw = fixtures_json("jsonschemas", "schema_2.json")
    return JsonSchema(raw)


@pytest.fixture(scope="function")
def schema_3() -> JsonSchema:
    raw = fixtures_json("jsonschemas", "schema_3.json")
    return JsonSchema(raw)


@pytest.fixture(scope="function")
def mock_storage_for_tenant(mock_storage: Mock):
    with patch("api.services.storage.storage_for_tenant", return_value=mock_storage) as m:
        yield m


@pytest.fixture(scope="function")
def frozen_time():
    with freeze_time("2024-08-12T00:00:00Z") as frozen_time:
        yield frozen_time


@pytest.fixture(scope="function")
def patched_bedrock_config():
    with patch.dict(
        os.environ,
        {
            "AWS_BEDROCK_MODEL_REGION_MAP": json.dumps(_PATCHED_BEDROCK_REGION_MAP),
        },
    ):
        yield _PATCHED_BEDROCK_REGION_MAP


@pytest.fixture(scope="function")
def hello_task():
    return SerializableTaskVariant(
        id="hello_task",
        task_schema_id=1,
        name="Hello Task",
        input_schema=SerializableTaskIO.from_json_schema(
            {
                "properties": {"name": {"type": "string"}},
            },
            streamline=True,
        ),
        output_schema=SerializableTaskIO.from_json_schema(
            {
                "properties": {"say_hello": {"type": "string"}},
            },
            streamline=True,
        ),
    )


@pytest.fixture(scope="function")
def patch_metric_send():
    with patch("core.domain.metrics.Metric.send", autospec=True) as m:
        yield m
