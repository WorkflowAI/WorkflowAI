from openai import AsyncOpenAI

from core.domain.consts import METADATA_KEY_FILE_DOWNLOAD_SECONDS
from tests.component.common import IntegrationTestClient


async def test_image_is_not_downloaded(test_client: IntegrationTestClient, openai_client: AsyncOpenAI):
    """Check that for OpenAI the image is not downloaded"""
    test_client.httpx_mock.add_response(
        url="https://example.com/image.png",
        status_code=200,
        content=b"hello",
    )
    test_client.mock_openai_call()
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini-latest",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://example.com/image.png",
                        },
                    },
                ],
            },
        ],
    )
    assert METADATA_KEY_FILE_DOWNLOAD_SECONDS not in response.metadata  # type: ignore
    assert response.choices[0].message.content == '{"greeting": "Hello James!"}'
