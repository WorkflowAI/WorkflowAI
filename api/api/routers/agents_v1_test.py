from httpx import AsyncClient


class TestExtractTemplate:
    async def test_extract_template_error(
        self,
        test_api_client: AsyncClient,
    ):
        response = await test_api_client.post(
            url="/v1/_/agents/blblbl/templates/extract",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Hello, {{ name }}!",
                            },
                        ],
                    },
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "Back to you {{ name }!",
                            },
                        ],
                    },
                ],
            },
        )
        assert response.status_code == 400
        assert response.json() == {
            "error": {
                "code": "bad_request",
                "status_code": 400,
                "message": "Invalid template: unexpected '}'",
                "details": {
                    "line_number": 1,
                    "unexpected_char": "}",
                    "source": "Back to you {{ name }!",
                    "message_index": 1,
                    "content_index": 0,
                },
            },
        }
