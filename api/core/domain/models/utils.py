import datetime

from core.domain.models import Model, Provider
from core.domain.models.model_provider_data import ModelProviderData
from core.domain.models.model_provider_datas_mapping import MODEL_PROVIDER_DATAS, ProviderDataByModel

from .model_data import DeprecatedModel, FinalModelData, LatestModel
from .model_datas_mapping import MODEL_DATAS


def get_model_data(model: Model) -> FinalModelData:
    model_data = MODEL_DATAS[model]
    if isinstance(model_data, LatestModel):
        return MODEL_DATAS[model_data.model]  # pyright: ignore [reportReturnType]
    if isinstance(model_data, DeprecatedModel):
        return MODEL_DATAS[model_data.replacement_model]  # pyright: ignore [reportReturnType]
    return model_data


def get_provider_data_by_model(provider: Provider) -> ProviderDataByModel:
    return MODEL_PROVIDER_DATAS[provider]


def get_model_provider_data(provider: Provider, model: Model) -> ModelProviderData:
    return get_model_data(model).provider_data(provider)


# TODO: this is deprecated, do not use
def is_model_available_at_provider(provider: Provider, model: Model, today: datetime.date) -> bool:
    try:
        model_data = MODEL_PROVIDER_DATAS[provider][model]
    except KeyError:
        return False
    return model_data.is_available(today)
