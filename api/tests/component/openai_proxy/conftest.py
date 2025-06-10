import pytest
from openai import AsyncOpenAI

from tests.component.common import IntegrationTestClient
from tests.component.conftest import _TEST_JWT  # pyright: ignore [reportPrivateUsage]


@pytest.fixture()
def openai_client(test_client: IntegrationTestClient):
    yield AsyncOpenAI(http_client=test_client.int_api_client, api_key=_TEST_JWT).with_options(
        # Disable retries
        max_retries=0,
    )
