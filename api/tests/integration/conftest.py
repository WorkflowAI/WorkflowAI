import asyncio
import os
from typing import Any
from unittest import mock
from unittest.mock import Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pytest import FixtureRequest
from pytest_httpx import HTTPXMock
from taskiq import InMemoryBroker

from tests.asgi_transport import patch_asgi_transport
from tests.integration.common import IntegrationTestClient


@pytest.fixture
def assert_all_responses_were_requested() -> bool:
    return False


@pytest.fixture(scope="session", autouse=True)
def setup_environment():
    with patch.dict(
        os.environ,
        {
            "WORKFLOWAI_MONGO_CONNECTION_STRING": "mongodb://admin:admin@localhost:27017/workflowai_int_test",
            "WORKFLOWAI_MONGO_INT_CONNECTION_STRING": "mongodb://admin:admin@localhost:27017/workflowai_int_test",
            "CLICKHOUSE_TEST_CONNECTION_STRING": "clickhouse://default:admin@localhost:8123/db_test",
            "CLICKHOUSE_CONNECTION_STRING": "clickhouse://default:admin@localhost:8123/db_test",
            "STORAGE_AES": "ruQBOB/yrSJYw+hozAGewJx5KAadHAMPnATttB2dmig=",
            "STORAGE_HMAC": "ATWcst2v/c/KEypN99ujwOySMzpwCqdaXvHLGDqBt+c=",
            "AWS_BEDROCK_MODEL_REGION_MAP": "{}",
            "AWS_BEDROCK_SECRET_KEY": "secret",
            "AWS_BEDROCK_ACCESS_KEY": "access",
            "CLERK_WEBHOOKS_SECRET": "whsec_LCi7t70Dv3NryHc386aaOzjgDPl/Ta/D",
            "STRIPE_WEBHOOK_SECRET": "whsec_LCi7t70Dv3NryHc386aaOzjgDPl/Ta/D",
            "STRIPE_API_KEY": "sk-proj-123",
            "OPENAI_API_KEY": "sk-proj-123",
            "GROQ_API_KEY": "gsk-proj-123",
            "AZURE_OPENAI_CONFIG": '{"deployments": {"eastus": { "url": "https://workflowai-azure-oai-staging-eastus.openai.azure.com/openai/deployments/", "api_key": "sk-proj-123", "models": ["gpt-4o-2024-11-20", "gpt-4o-mini-2024-07-18"]}}, "default_region": "eastus"}',
            "GOOGLE_VERTEX_AI_PROJECT_ID": "worfklowai",
            "GOOGLE_VERTEX_AI_LOCATION": "us-central1",
            "GOOGLE_VERTEX_AI_CREDENTIALS": '{"type":"service_account","project_id":"worfklowai"}',
            "GEMINI_API_KEY": "sk-proj-123",
            "FIREWORKS_API_KEY": "sk-proj-123",
            "FIREWORKS_API_URL": "https://api.fireworks.ai/inference/v1/chat/completions",
            "MISTRAL_API_KEY": "sk-proj-123",
            "ANTHROPIC_API_KEY": "sk-proj-1234",
            "WORKFLOWAI_API_URL": "http://0.0.0.0:8000",
            "WORKFLOWAI_API_KEY": "sk-proj-123",
            "WORKFLOWAI_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;",
            "WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER": "workflowai-test-task-runs",
            "FIRECRAWL_API_KEY": "firecrawl-api-key",
            "SCRAPINGBEE_API_KEY": "scrapingbee-api-key",
            "SCRAPINGBEE_API_URL": "https://api.scrapingbee.com/scrape",
            "MODERATION_ENABLED": "false",
            "JOBS_BROKER_URL": "memory://",
            "CLERK_SECRET_KEY": "sk_test_123",
            "LOOPS_API_KEY": "loops-api-key",
            "PAYMENT_FAILURE_EMAIL_ID": "123",
            "LOW_CREDITS_EMAIL_ID": "123",
        },
    ):
        yield


@pytest.fixture(scope="function")
def patched_broker():
    from api.broker import broker

    yield broker


@pytest.fixture(scope="function", autouse=True)
def patched_amplitude(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url="https://amplitude-mock", status_code=200)
    with mock.patch.dict(
        os.environ,
        {
            "AMPLITUDE_API_KEY": "test_api_key",
            "AMPLITUDE_URL": "https://amplitude-mock",
        },
    ):
        yield


@pytest.fixture(scope="function", autouse=True)
def patched_google_auth():
    with mock.patch(
        "core.providers.google.google_provider_auth.get_token",
        autospec=True,
        return_value="test_token",
    ) as mock_get_token:
        yield mock_get_token


# The private key used to generate a token compatible with the JWK below
# Use in jwt.io to generate a new token if needed
# _test_private_key = """
# -----BEGIN PRIVATE KEY-----
# MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgselKFg5Ve0M3/1/X
# NR8jT8pC+bqWeLi8ohVBJOJ+YCuhRANCAAQpQlhzu9YPFGfLmcC35ThvzS2EJWeE
# NMvSxF8AXi+ntd+Lpbk/NjgxA0VlDieC5INYo8nK149YOdn0J2Y8Vvat
# -----END PRIVATE KEY-----
# """

_TEST_JWT = "eyJhbGciOiJFUzI1NiJ9.eyJ0ZW5hbnQiOiJjaGllZm9mc3RhZmYuYWkiLCJzdWIiOiJndWlsbGF1bWVAY2hpZWZvZnN0YWZmLmFpIiwib3JnSWQiOiJvcmdfMmlQbGZKNVg0THdpUXliTTlxZVQwMFlQZEJlIiwib3JnU2x1ZyI6InRlc3QtMjEiLCJpYXQiOjE3MTU5ODIzNTEsImV4cCI6MTgzMjE2NjM1MX0.QH1D8ppCYT4LONE0XzR11mvyZ7n4Ljc9MC0eJYM2FBtqSoGnr4_GCdcMEZb3NZZI5dKXbjTUk_8kRU1vrn7n2A"


@pytest.fixture(scope="function", autouse=True)
def patch_environment_variables():
    with mock.patch.dict(
        os.environ,
        {
            "WORKFLOWAI_JWK": "eyJrdHkiOiJFQyIsIngiOiJLVUpZYzd2V0R4Um55NW5BdC1VNGI4MHRoQ1ZuaERUTDBzUmZBRjR2cDdVIiwieSI6IjM0dWx1VDgyT0RFRFJXVU9KNExrZzFpanljclhqMWc1MmZRblpqeFc5cTAiLCJjcnYiOiJQLTI1NiIsImlkIjoiMSJ9Cg==",
        },
    ):
        yield


_INT_DB_NAME = "workflowai_int_test"


def _build_storage(mock_encryption: Mock):
    from core.storage.mongo.mongo_storage import MongoStorage
    from core.utils import no_op

    base_storage = MongoStorage(
        tenant="",
        encryption=mock_encryption,
        event_router=no_op.event_router,
    )
    assert base_storage._db_name == _INT_DB_NAME, "DB Name must be workflowai_int_test"  # pyright: ignore [reportPrivateUsage]
    return base_storage


@pytest.fixture(scope="session")
async def int_clickhouse_client():
    from core.storage.clickhouse.clickhouse_client_test import fresh_clickhouse_client

    with patch.dict(
        os.environ,
        {
            "CLICKHOUSE_CONNECTION_STRING": os.environ.get(
                "CLICKHOUSE_TEST_CONNECTION_STRING",
                "clickhouse://default:admin@localhost:8123/db_int_test",
            ),
        },
    ):
        # After the reviews
        yield await fresh_clickhouse_client(dsn=os.environ["CLICKHOUSE_CONNECTION_STRING"])


@pytest.fixture(scope="session", autouse=True)
async def wrap_db_cleanup(mock_encryption_session: Mock):
    from core.storage.mongo.migrations.migrate import migrate

    with patch.dict(
        os.environ,
        {
            "WORKFLOWAI_MONGO_CONNECTION_STRING": os.environ.get(
                "WORKFLOWAI_MONGO_INT_CONNECTION_STRING",
                f"mongodb://admin:admin@localhost:27017/{_INT_DB_NAME}",
            ),
        },
    ):
        # Deleting the db and running migrations
        base_storage = _build_storage(mock_encryption=mock_encryption_session)

        # Clean up the database
        await base_storage.client.drop_database(_INT_DB_NAME)  # type: ignore

        await migrate(base_storage)

        yield base_storage


@pytest.fixture(autouse=True)
async def integration_storage(
    mock_encryption: Mock,
    request: pytest.FixtureRequest,
    int_clickhouse_client: Any,
):
    no_truncate = request.node.get_closest_marker("no_truncate") is not None  # type: ignore

    connection_string = os.getenv(
        "CLICKHOUSE_TEST_CONNECTION_STRING",
        "clickhouse://default:admin@localhost:8123/db_test",
    )
    assert connection_string.endswith("/db_test"), "DB Name must be db_test"
    storage = _build_storage(mock_encryption=mock_encryption)
    # Removing runs
    if not no_truncate:
        assert int_clickhouse_client.connection_string.endswith("/db_test"), "DB Name must be db_test"
        await int_clickhouse_client.command("TRUNCATE TABLE runs;")

        # Remove all data from all collections
        db = storage.client[_INT_DB_NAME]
        names = await db.list_collection_names()
        await asyncio.gather(
            *(db[c].delete_many({}) for c in names),
        )

    return storage


@pytest.fixture(scope="module")
def test_storage_container():
    with mock.patch.dict(
        os.environ,
        {
            "WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER": "workflowai-test-task-runs",
            "GOOGLE_VERTEX_AI_LOCATION": "us-central1",
            "GOOGLE_VERTEX_AI_PROJECT": "test_project_id",
            "GOOGLE_VERTEX_AI_CREDENTIALS": '{"type":"service_account","project_id":"worfklowai","private_key_id":"9a24c7bc5e8c94cef69bb714d48a796fc8f530f8","private_key":"","client_email":"llm-runner@worfklowai.iam.gserviceaccount.com","client_id":"112189683594878284966","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/llm-runner%40worfklowai.iam.gserviceaccount.com","universe_domain":"googleapis.com"}',
        },
    ):
        from core.storage.azure.azure_blob_file_storage import AzureBlobFileStorage

        blob_storage = AzureBlobFileStorage(
            connection_string=os.environ["WORKFLOWAI_STORAGE_CONNECTION_STRING"],
            container_name=os.environ["WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER"],
        )
        yield blob_storage


@patch.dict(
    os.environ,
    {"BETTER_STACK_API_KEY": "test_bs_api_key"},
)
@pytest.fixture(scope="function")
async def int_api_client(
    patched_broker: InMemoryBroker,
    request: FixtureRequest,
    integration_storage: Any,
    httpx_mock: HTTPXMock,
    # Making sure the blob storage is created
    test_blob_storage: None,
):
    # Making sure the call is patched before applying all imports
    from api.main import app
    from tests.integration.common import wait_for_completed_tasks

    httpx_mock.add_response(url="https://in.logs.betterstack.com/metrics", status_code=202)

    """A client used for integration tests. No mocking is done"""
    app.dependency_overrides = {}

    with mock.patch("api.services.storage._base_client", integration_storage.client):
        with mock.patch("api.services.storage._db_name", "workflowai_int_test"):
            async with patch_asgi_transport():
                headers: dict[str, str] = {}
                if not request.node.get_closest_marker("unauthenticated"):  # type: ignore
                    headers["Authorization"] = f"Bearer {_TEST_JWT}"

                client = AsyncClient(
                    transport=ASGITransport(app=app),  # pyright: ignore [reportArgumentType]
                    base_url="http://0.0.0.0",
                    headers=headers,
                )

                yield client

                # Making sure all tasks are completed before exiting
                await wait_for_completed_tasks(patched_broker)


def pytest_configure(config: pytest.Config):
    config.addinivalue_line("markers", "unauthenticated: mark test to run without authentication")


# TODO: do not use, use mock internal task instead
@pytest.fixture(scope="function")
def mock_run_detect_chain_of_thought_task():
    from core.agents.detect_chain_of_thought_task import DetectChainOfThoughtUsageTaskOutput

    with patch(
        "api.services.groups.run_detect_chain_of_thought_task",
        autospec=True,
        return_value=DetectChainOfThoughtUsageTaskOutput(should_use_chain_of_thought=True),
    ) as mock:
        yield mock


@pytest.fixture(scope="function")
async def test_client(int_api_client: AsyncClient, httpx_mock: HTTPXMock, patched_broker: InMemoryBroker):
    clt = IntegrationTestClient(int_api_client, httpx_mock, patched_broker)
    await clt.refresh_org_data()
    return clt
