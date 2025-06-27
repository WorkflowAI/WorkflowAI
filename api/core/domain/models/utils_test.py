import pytest

from core.domain.models import Model
from core.domain.models.model_data import FinalModelData
from core.domain.models.utils import get_model_data


class TestGetModelData:
    @pytest.mark.parametrize("model", list(Model))
    def test_get_model_data_is_final_model_data(self, model: Model):
        model_data = get_model_data(model)
        assert isinstance(model_data, FinalModelData)
