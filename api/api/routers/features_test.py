from unittest.mock import Mock, patch

from httpx import AsyncClient

from core.domain.models.models import Model


class TestPreviewModels:
    @patch("api.services.models.ModelsService._available_models_from_run_endpoint", return_value=list(Model))
    async def test_preview_models(self, models_from_run_endpoint: Mock, test_api_client: AsyncClient):
        response = await test_api_client.get("/features/models")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) > 0

        model_ids = {item["id"] for item in items}
        assert len(model_ids) == 7  # this might change if one of the included models is also a default model
        assert Model.GPT_4O_AUDIO_PREVIEW_2024_12_17 not in model_ids
        assert Model.DEEPSEEK_R1_0528 in model_ids
        assert Model.MISTRAL_LARGE_2_LATEST in model_ids
        assert Model.LLAMA_4_MAVERICK_BASIC in model_ids
        assert Model.CLAUDE_4_SONNET_LATEST in model_ids
        assert Model.GROK_3_BETA in model_ids
        models_from_run_endpoint.assert_called_once()
