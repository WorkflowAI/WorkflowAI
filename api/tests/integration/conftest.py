"""
A conftest file to allow testing the API e2e using frameworks
by spinning up a local instance of the API.
"""

import asyncio
import os
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest

_INT_DB_NAME = "workflowai_e2e_test"

_CLICKHOUSE_TEST_CONNECTION_STRING = "clickhouse://default:admin@localhost:8123/db_int_test"
_WORKFLOWAI_MONGO_INT_CONNECTION_STRING = f"mongodb://admin:admin@localhost:27017/{_INT_DB_NAME}"


@pytest.fixture(scope="session", autouse=True)
def setup_environment():
    with patch.dict(
        os.environ,
        {
            "WORKFLOWAI_MONGO_CONNECTION_STRING": _WORKFLOWAI_MONGO_INT_CONNECTION_STRING,
            "WORKFLOWAI_MONGO_INT_CONNECTION_STRING": _WORKFLOWAI_MONGO_INT_CONNECTION_STRING,
            "CLICKHOUSE_TEST_CONNECTION_STRING": "clickhouse://default:admin@localhost:8123/db_test",
            "CLICKHOUSE_CONNECTION_STRING": _CLICKHOUSE_TEST_CONNECTION_STRING,
            "STORAGE_AES": "ruQBOB/yrSJYw+hozAGewJx5KAadHAMPnATttB2dmig=",
            "STORAGE_HMAC": "ATWcst2v/c/KEypN99ujwOySMzpwCqdaXvHLGDqBt+c=",
            "CLERK_WEBHOOKS_SECRET": "",
            "STRIPE_WEBHOOK_SECRET": "",
            "STRIPE_API_KEY": "",
            # WorkflowAI API, points to a local instance of the WorkflowAI API
            "WORKFLOWAI_API_URL": "http://0.0.0.0:8000",
            # A JWT that is ok with the JWK below
            "WORKFLOWAI_API_KEY": "eyJhbGciOiJFUzI1NiJ9.eyJ0ZW5hbnQiOiJjaGllZm9mc3RhZmYuYWkiLCJzdWIiOiJndWlsbGF1bWVAY2hpZWZvZnN0YWZmLmFpIiwib3JnSWQiOiJvcmdfMmlQbGZKNVg0THdpUXliTTlxZVQwMFlQZEJlIiwib3JnU2x1ZyI6InRlc3QtMjEiLCJpYXQiOjE3MTU5ODIzNTEsImV4cCI6MTgzMjE2NjM1MX0.QH1D8ppCYT4LONE0XzR11mvyZ7n4Ljc9MC0eJYM2FBtqSoGnr4_GCdcMEZb3NZZI5dKXbjTUk_8kRU1vrn7n2A",
            "WORKFLOWAI_JWK": "eyJrdHkiOiJFQyIsIngiOiJLVUpZYzd2V0R4Um55NW5BdC1VNGI4MHRoQ1ZuaERUTDBzUmZBRjR2cDdVIiwieSI6IjM0dWx1VDgyT0RFRFJXVU9KNExrZzFpanljclhqMWc1MmZRblpqeFc5cTAiLCJjcnYiOiJQLTI1NiIsImlkIjoiMSJ9Cg==",
            # S3 Storage
            "WORKFLOWAI_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;",
            "WORKFLOWAI_STORAGE_TASK_RUNS_CONTAINER": "workflowai-test-task-runs",
            # Worker
            "JOBS_BROKER_URL": "memory://",  # Mapping to internal job broker
            # Redis
            "REDIS_CONNECTION_STRING": "redis://localhost:6379/10",
            # Misc
            "MODERATION_ENABLED": "false",
            "CLERK_SECRET_KEY": "",
            "LOOPS_API_KEY": "",
            "PAYMENT_FAILURE_EMAIL_ID": "",
            "LOW_CREDITS_EMAIL_ID": "",
            "AMPLITUDE_API_KEY": "",  # not sending anything to amplitude
            "BETTERSTACK_API_KEY": "",  # not sending anything to betterstack
        },
    ):
        yield


def _build_storage(mock_encryption: Mock):
    from core.storage.mongo.mongo_storage import MongoStorage
    from core.utils import no_op

    base_storage = MongoStorage(
        tenant="",
        encryption=mock_encryption,
        event_router=no_op.event_router,
        connection_string=_WORKFLOWAI_MONGO_INT_CONNECTION_STRING,
    )
    assert base_storage._db_name == _INT_DB_NAME, "DB Name must be workflowai_int_test"  # pyright: ignore [reportPrivateUsage]
    return base_storage


@pytest.fixture(scope="session")
async def fresh_clickhouse():
    from core.storage.clickhouse.clickhouse_client_test import fresh_clickhouse_client

    # After the reviews
    return await fresh_clickhouse_client(dsn=_CLICKHOUSE_TEST_CONNECTION_STRING)


@pytest.fixture(scope="session")
async def fresh_mongo_db(mock_encryption_session: Mock):
    """Deletes and migrate the database at the beginning of the start session"""
    from core.storage.mongo.migrations.migrate import migrate

    # Deleting the db and running migrations
    base_storage = _build_storage(mock_encryption=mock_encryption_session)

    # Clean up the database
    await base_storage.client.drop_database(_INT_DB_NAME)  # type: ignore

    await migrate(base_storage)

    return base_storage


async def _wait_for_server_ready():
    async with httpx.AsyncClient() as client:
        for _ in range(20):
            try:
                await client.get("http://0.0.0.0:8000/probes/readiness")
                return
            except Exception:
                await asyncio.sleep(0.1)
    pytest.fail("Server not ready")


# TODO: implement a lock mechanism to allow running in parallel
@pytest.fixture(scope="session")
async def api_server(
    request: pytest.FixtureRequest,
    fresh_mongo_db: Any,
    fresh_clickhouse: Any,
    # Making sure the blob storage is created
    test_blob_storage: None,
):
    """Starts a server in a separate thread so that it can be called via API directly"""
    import threading

    import uvicorn

    from api.main import app

    # Create a server instance that can be shutdown gracefully
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="error")
    server = uvicorn.Server(config)

    # Use threading instead of multiprocessing to avoid pickling issues
    server_thread = threading.Thread(
        target=server.run,
        daemon=True,
    )
    server_thread.start()

    try:
        await _wait_for_server_ready()
    except Exception:
        # Try to shutdown gracefully if startup failed
        server.should_exit = True
        raise

    yield "http://0.0.0.0:8000"

    # Graceful shutdown
    server.should_exit = True
    server_thread.join(timeout=5)  # Wait up to 5 seconds for graceful shutdown
