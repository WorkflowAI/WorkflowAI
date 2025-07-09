import asyncio
import logging
from collections.abc import Callable
from datetime import date, timedelta
from difflib import get_close_matches
from typing import Any, NamedTuple

import httpx

from core.agents.suggest_model import ModelSuggestionInput, suggest_model
from core.domain.consts import WORKFLOWAI_RUN_URL
from core.domain.errors import ProviderDoesNotSupportModelError
from core.domain.models import Model, Provider
from core.domain.models.model_data import DeprecatedModel, LatestModel, ModelData
from core.domain.models.model_data_mapping import MODEL_DATAS
from core.domain.models.model_provider_data import ModelProviderData
from core.domain.models.utils import get_model_provider_data
from core.domain.task_typology import TaskTypology
from core.domain.task_variant import SerializableTaskVariant
from core.storage import TaskTuple
from core.storage.backend_storage import BackendStorage
from core.storage.task_run_storage import TokenCounts
from core.tools import get_tools_in_instructions
from core.utils.lru.lru_cache import TLRUCache
from core.utils.models.dumps import safe_dump_pydantic_model


# TODO: remove all the fileds that can be accessed from the model_data
class ModelForTask(NamedTuple):
    id: str
    name: str
    modes: list[str]
    icon_url: str
    is_default: bool
    release_date: date
    price_per_input_token_usd: float
    price_per_output_token_usd: float
    context_window_tokens: int
    provider_name: str
    quality_index: int
    speed_index: int
    providers: list[Provider]
    supports_structured_output: bool
    model_data: ModelData
    is_not_supported_reason: str | None = None
    average_cost_per_run_usd: float | None = None
    is_latest: bool = False


def _token_cache_ttl(_: Any, value: TokenCounts):
    if value["count"] == 0:
        return timedelta(seconds=0)
    # 30 seconds
    if value["count"] < 10:
        return timedelta(seconds=30)
    # 1h
    return timedelta(hours=1)


_logger = logging.getLogger(__name__)


class ModelsService:
    # TODO: dynamically exclude reasoning models
    _REASONING_MODELS_CORRECTION = {
        Model.O1_2024_12_17_LOW_REASONING_EFFORT: 0.9,
        Model.O1_2024_12_17: 1.0,
        Model.O1_2024_12_17_HIGH_REASONING_EFFORT: 1.1,
        Model.O3_MINI_2025_01_31_HIGH_REASONING_EFFORT: 1.1,
        Model.O3_MINI_2025_01_31_MEDIUM_REASONING_EFFORT: 1.0,
        Model.O3_MINI_2025_01_31_LOW_REASONING_EFFORT: 0.9,
        Model.DEEPSEEK_R1_2501: 1.0,
        Model.GEMINI_2_0_FLASH_THINKING_EXP_1219: 1.0,
    }
    # Small cache for token counts to speed up aggregation for cost estimates
    # since it might be called repeatedly by the front end when viewing version details
    # Very short TTL to avoid stale data.
    # TODO: we could increase the TTL when a sufficient number o f
    _token_counts_cache = TLRUCache[tuple[int, int, tuple[str, ...] | None, tuple[str, ...] | None], TokenCounts](
        capacity=1000,
        ttl=_token_cache_ttl,
    )
    _token_counts_cache_lock = asyncio.Lock()

    def __init__(self, storage: BackendStorage):
        self.storage = storage
        self._logger = _logger

    @classmethod
    async def _available_models_from_run_endpoint(cls) -> list[Model]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{WORKFLOWAI_RUN_URL}/v1/models/ids")
                response.raise_for_status()
                model_json = response.json()

            out: list[Model] = []
            for model in model_json:
                try:
                    m = Model(model)
                    out.append(m)
                except ValueError:
                    _logger.warning(
                        "Model is not a valid model",
                        extra={"model": model},
                    )
            return out
        except Exception:
            _logger.exception("Error fetching available models from run endpoint")
            return list(Model)

    @classmethod
    def _build_model_for_task(
        cls,
        model: Model,
        task_typology: TaskTypology | None,
        price_calculator: Callable[[ModelProviderData, Model], float | None] | None,
        instructions: str | None,
        requires_tools: bool | None,
    ):
        data = MODEL_DATAS[model]
        if isinstance(data, DeprecatedModel):
            return None

        display_name = data.display_name
        is_default = data.is_default
        model_id = model

        if isinstance(data, LatestModel):
            model = data.model
            data = MODEL_DATAS[data.model]
            is_latest = True
        else:
            # Otherwise is_latest is True when the model has no latest model
            is_latest = data.latest_model is None

        # We have tests in place checking that the model data of latest models is a ModelData
        # So this should never happen
        if not isinstance(data, ModelData):
            _logger.error(
                "Unexpected model data is not a ModelData",
                extra={"model": safe_dump_pydantic_model(model)},
            )
            return None

        def _build(
            is_not_supported_reason: str | None,
            provider_data: ModelProviderData,
            average_cost_per_run_usd: float | None,
        ):
            return ModelForTask(
                id=model_id,
                name=display_name,
                icon_url=data.icon_url,
                is_not_supported_reason=is_not_supported_reason,
                average_cost_per_run_usd=average_cost_per_run_usd,
                modes=data.modes,
                is_latest=is_latest,
                is_default=is_default,
                release_date=data.release_date,
                quality_index=data.quality_index,
                speed_index=data.speed_index,
                model_data=data,
                price_per_input_token_usd=provider_data.text_price.prompt_cost_per_token,
                price_per_output_token_usd=provider_data.text_price.completion_cost_per_token,
                context_window_tokens=data.max_tokens_data.max_tokens,
                provider_name=data.provider_name,
                providers=[p for p, _ in data.providers],
                supports_structured_output=data.supports_structured_output,
            )

        provider_data = data.providers[0][1]

        if (
            requires_tools or len(get_tools_in_instructions(instructions or "")) > 0
        ) and data.supports_tool_calling is False:
            return _build(
                f"{data.display_name} does not support tool calling",
                provider_data,
                None,
            )

        if task_typology and (is_not_supported_reason := data.is_not_supported_reason(task_typology)):
            return _build(is_not_supported_reason, provider_data, None)

        return _build(
            None,
            provider_data,
            price_calculator(provider_data, model) if price_calculator else None,
        )

    @classmethod
    async def preview_models(cls, typology: TaskTypology | None = None):
        models = await cls._available_models_from_run_endpoint()
        for model in models:
            if m := cls._build_model_for_task(model, typology, None, None, None):
                yield m

    async def models_for_task(
        self,
        task: SerializableTaskVariant,
        instructions: str | None,
        requires_tools: bool | None,
    ) -> list[ModelForTask]:
        models = await self._available_models_from_run_endpoint()
        task_typology = task.typology()
        price_calculator = await self._average_price_calculator(
            task.id_tuple,
            task.task_schema_id,
        )

        out: list[ModelForTask] = []
        for model in models:
            if m := self._build_model_for_task(
                model,
                task_typology,
                price_calculator,
                instructions,
                requires_tools,
            ):
                out.append(m)  # noqa: PERF401
        return out

    async def model_for_task_typology(
        self,
        task_typology: TaskTypology,
        instructions: str | None = None,
        requires_tools: bool = False,
    ) -> list[ModelForTask]:
        models = await self._available_models_from_run_endpoint()

        async def no_op_price_calculator():
            def _compute_cost_estimate(model_provider_data: ModelProviderData, model: Model) -> float | None:
                return None

            return _compute_cost_estimate

        out: list[ModelForTask] = []
        for model in models:
            if m := self._build_model_for_task(
                model,
                task_typology,
                await no_op_price_calculator(),
                instructions,
                requires_tools,
            ):
                out.append(m)  # noqa: PERF401
        return out

    async def get_cost_estimates(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        models_providers: set[tuple[Model, Provider]],
    ):
        price_calculator = await self._average_price_calculator(
            task_id,
            task_schema_id,
        )
        # TODO: here we may go in the loop for nothing if the price_calculator is a noop
        # It's ok, this function will be deprecated soon after we move to only providers
        # plus we should have cost estimates most of the time

        cost_estimates: dict[tuple[Model, Provider], float | None] = {}
        for model, provider in models_providers:
            try:
                model_data = get_model_provider_data(provider, model)
            except ProviderDoesNotSupportModelError:
                # This can happen if the model is deprecated for example
                # In this case we do not assign a cost estimate
                # the version should also be marked as deprecated
                continue
            cost_estimates[(model, provider)] = price_calculator(
                model_data,
                model,
            )

        return cost_estimates

    async def _aggregate_token_counts(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        *,
        included_models: list[str] | None = None,
        excluded_models: list[str] | None = None,
    ) -> TokenCounts:
        async with self._token_counts_cache_lock:
            cache_key = (
                task_id[1],
                task_schema_id,
                tuple(included_models) if included_models else None,
                tuple(excluded_models) if excluded_models else None,
            )
            if cache := self._token_counts_cache.get(cache_key):
                return cache

        counts = await self.storage.task_runs.aggregate_token_counts(
            task_id,
            task_schema_id,
            included_models=included_models,
            excluded_models=excluded_models,
        )

        if counts["count"] > 0:
            async with self._token_counts_cache_lock:
                self._token_counts_cache[cache_key] = counts

        return counts

    async def _average_price_calculator(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
    ):
        regular_token_counts, reasoning_token_counts = await asyncio.gather(
            self._aggregate_token_counts(
                task_id,
                task_schema_id,
                excluded_models=list(self._REASONING_MODELS_CORRECTION.keys()),
            ),
            self._aggregate_token_counts(
                task_id,
                task_schema_id,
                included_models=list(self._REASONING_MODELS_CORRECTION.keys()),
            ),
            return_exceptions=True,
        )
        # Log errors
        if isinstance(regular_token_counts, BaseException):
            self._logger.exception(
                "Error fetching regular token counts",
                extra={"task_id": task_id, "task_schema_id": task_schema_id},
            )
        if isinstance(reasoning_token_counts, BaseException):
            self._logger.exception(
                "Error fetching reasoning token counts",
                extra={"task_id": task_id, "task_schema_id": task_schema_id},
            )

        def _compute_cost_estimate(model_provider_data: ModelProviderData, model: Model) -> float | None:
            counts = reasoning_token_counts if model in self._REASONING_MODELS_CORRECTION else regular_token_counts

            if isinstance(counts, BaseException):
                return None
            average_prompt_tokens = counts["average_prompt_tokens"]
            average_completion_tokens = counts["average_completion_tokens"]
            if not average_prompt_tokens or not average_completion_tokens or counts["count"] == 0:
                return None

            average_completion_tokens = average_completion_tokens * self._REASONING_MODELS_CORRECTION.get(model, 1.0)

            prompt_cost_per_token = model_provider_data.text_price.prompt_cost_per_token
            completion_cost_per_token = model_provider_data.text_price.completion_cost_per_token

            return (average_prompt_tokens * prompt_cost_per_token) + (
                average_completion_tokens * completion_cost_per_token
            )

        return _compute_cost_estimate

    async def model_price_calculator(self, task_id: TaskTuple, task_schema_id: int) -> Callable[[Model], float | None]:
        price_calculator = await self._average_price_calculator(
            task_id,
            task_schema_id,
        )

        def _compute_price(model: Model) -> float | None:
            data = MODEL_DATAS[model]
            if isinstance(data, DeprecatedModel):
                return None
            if isinstance(data, LatestModel):
                model = data.model
                data = MODEL_DATAS[data.model]
            if not isinstance(data, ModelData):
                self._logger.error(
                    "Unexpected model data is not a ModelData",
                    extra={"model": safe_dump_pydantic_model(model)},
                )
                return None
            return price_calculator(
                data.providers[0][1],
                model,
            )

        return _compute_price

    @classmethod
    async def suggest_model(cls, model: str) -> Model | None:
        supported_models = [k for k, v in MODEL_DATAS.items() if not isinstance(v, DeprecatedModel)]
        try:
            suggested_model = await suggest_model(
                ModelSuggestionInput(
                    invalid_model=model,
                    supported_models=supported_models,
                ),
            )
            return Model(suggested_model.suggested_model)
        except Exception:
            _logger.exception(
                "Error suggesting model",
                extra={"model": model},
            )

        suggestion = get_close_matches(model, list(Model), n=1, cutoff=0.5)
        if not suggestion:
            _logger.warning(
                "No similar model found for {model}",
                extra={"model": model},
            )
            return None
        return Model(suggestion[0])
