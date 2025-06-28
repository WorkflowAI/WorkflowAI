import time
from datetime import datetime, timezone

import httpx
import pytest
from pytest_httpx import HTTPXMock

from core.domain.metrics import Metric
from core.storage.betterstack.betterstack_client import BetterStackClient
from tests.utils import request_json_body


@pytest.fixture()
async def betterstack_client(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url="https://in.logs.betterstack.com/metrics",
        status_code=202,
    )
    clt = BetterStackClient(betterstack_api_key="test", default_retry_delay=0.01)
    yield clt
    await clt.close()


class TestSendMetrics:
    async def test_send_metrics(self, betterstack_client: BetterStackClient, httpx_mock: HTTPXMock):
        now = datetime(2024, 1, 1, 0, 0, 0, microsecond=1, tzinfo=timezone.utc)
        await betterstack_client.send_metrics(
            [
                Metric(name="test", gauge=1, timestamp=now.timestamp(), tags={"e": "test", "v": "test"}),
                Metric(
                    name="test1",
                    counter=3,
                    timestamp=now.timestamp() + 1,
                    tags={"e": "test", "v": "test1"},
                ),
            ],
            tags={"c": "d"},
        )

        assert len(httpx_mock.get_requests()) == 1
        body = request_json_body(httpx_mock.get_requests()[0])
        assert body == [
            {
                "name": "test",
                "gauge": {"value": 1},
                "dt": 1704067200000,
                "tags": {"c": "d", "e": "test", "v": "test"},
            },
            {
                "name": "test1",
                "counter": {"value": 3},
                "dt": 1704067201000,
                "tags": {"c": "d", "e": "test", "v": "test1"},
            },
        ]

    async def test_send_metrics_retries(self, betterstack_client: BetterStackClient, httpx_mock: HTTPXMock):
        httpx_mock.reset()
        httpx_mock.add_response(
            method="POST",
            url="https://in.logs.betterstack.com/metrics",
            status_code=429,
        )
        httpx_mock.add_response(
            method="POST",
            url="https://in.logs.betterstack.com/metrics",
            status_code=202,
        )

        await betterstack_client.send_metrics(
            [
                Metric(
                    name="test",
                    gauge=1,
                    timestamp=time.time(),
                    tags={},
                ),
            ],
            tags={"e": "test"},
        )
        assert len(httpx_mock.get_requests()) == 2

    async def test_send_metrics_retry_connect_error(self, betterstack_client: BetterStackClient, httpx_mock: HTTPXMock):
        httpx_mock.reset()
        httpx_mock.add_exception(httpx.ConnectError("test"))
        httpx_mock.add_response(
            method="POST",
            url="https://in.logs.betterstack.com/metrics",
            status_code=202,
        )

        await betterstack_client.send_metrics([], tags={"e": "test"})
        assert len(httpx_mock.get_requests()) == 2

    async def test_send_metrics_max_retry(self, betterstack_client: BetterStackClient, httpx_mock: HTTPXMock):
        httpx_mock.reset()
        httpx_mock.add_exception(httpx.ConnectError("test"), is_reusable=True)

        with pytest.raises(httpx.ConnectError):
            await betterstack_client.send_metrics([], tags={"e": "test"})
        assert len(httpx_mock.get_requests()) == 3
