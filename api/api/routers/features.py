from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.dependencies.event_router import EventRouterDep
from api.dependencies.security import SystemStorageDep, UserDep
from api.dependencies.storage import StorageDep
from api.schemas.models import ModelResponse
from api.services.features import (
    FeatureList,
    FeatureOutputPreview,
    FeatureSchemas,
    FeatureSectionPreview,
    FeatureService,
)
from api.services.models import ModelsService
from api.services.uptime_service import UptimeService
from core.domain.features import BaseFeature, DirectToAgentBuilderFeature, FeatureWithImage
from core.domain.models.models import Model
from core.domain.page import Page
from core.domain.task_typology import TaskTypology
from core.storage.task_run_storage import WeeklyRunAggregate
from core.utils.email_utils import safe_domain_from_email
from core.utils.redis_cache import redis_cached
from core.utils.stream_response_utils import safe_streaming_response

router = APIRouter(prefix="/features")


class FeatureSectionResponse(BaseModel):
    sections: list[FeatureSectionPreview] | None = None


@router.get(
    "/sections",
    description="Get the preview of available features sections and tags",
)
async def list_feature_sections(user: UserDep) -> FeatureSectionResponse:
    user_domain = None
    if user is not None:
        # Since user.tenant is not always the user's email domain, we use the email domain to fill the "For You" section
        user_domain = safe_domain_from_email(user.sub)

    return FeatureSectionResponse(sections=await FeatureService.get_feature_sections_preview(user_domain))


class FeatureListResponse(BaseModel):
    features: list[BaseFeature | DirectToAgentBuilderFeature | FeatureWithImage] | None = None


@router.get(
    "/search",
    description="Search for features by tags. Returns a stream with accumulated features.",
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": FeatureListResponse.model_json_schema(),
                },
            },
        },
    },
)
async def list_features_by_tag(
    user: UserDep,
    tags: str,
) -> StreamingResponse:
    # This endpoint use streaming in order to 1) Have a unified logic with the 'domain' endpoint
    # 2) Be evolutive in case some of the data is dynamically generated in the future.

    async def _stream() -> AsyncIterator[BaseModel]:
        async for features_list in FeatureService.get_features_by_tag(tags):
            yield FeatureListResponse(features=features_list)

    return safe_streaming_response(_stream)


@router.get(
    "/domain/{company_domain}",
    description="Get the features available for a specific company domain",
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": FeatureList.model_json_schema(),
                },
            },
        },
    },
)
async def list_feature_by_domain(
    user: UserDep,
    storage: StorageDep,
    event_router: EventRouterDep,
    company_domain: str,
) -> StreamingResponse:
    async def _stream() -> AsyncIterator[BaseModel]:
        async for item in FeatureService(storage).stream_features_by_domain(company_domain, event_router):
            yield item

    return safe_streaming_response(_stream)


class FeaturePreviewRequest(BaseModel):
    feature: BaseFeature
    company_context: str | None = Field(
        description="To provide for company-specific feature suggestions, null otherwise",
    )


@router.post(
    "/preview",
    description="Get a preview of a feature",
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": FeatureOutputPreview.model_json_schema(),
                },
            },
        },
    },
)
async def get_feature_preview(
    user: UserDep,
    request: FeaturePreviewRequest,
) -> StreamingResponse:
    async def _stream() -> AsyncIterator[BaseModel]:
        async for chunk in FeatureService().get_agent_preview(
            request.feature.name,
            request.feature.description,
            request.feature.specifications,
            request.company_context,
        ):
            yield chunk

    return safe_streaming_response(_stream)


@router.post(
    "/schemas",
    description="Get the input and output schema for a feature",
)
async def get_feature_schemas(
    user: UserDep,
    request: FeaturePreviewRequest,
) -> FeatureSchemas:
    return await FeatureService().get_agent_schemas(
        request.feature.name,
        request.feature.description,
        request.feature.specifications,
        request.company_context,
    )


@router.get(
    "/models",
    description="Preview available models and their associated data",
)
async def preview_models() -> Page[ModelResponse]:
    # Models to be included that are not default
    _include_models = {
        Model.DEEPSEEK_R1_0528,
        Model.MISTRAL_LARGE_2_LATEST,
        Model.LLAMA_4_MAVERICK_BASIC,
        Model.GROK_3_BETA,
    }

    # Total number of default models to include
    include_default_models_count = 3

    models: list[ModelResponse] = []
    typology = TaskTypology()  # the default typology, aka text only
    async for model in ModelsService.preview_models(typology=typology):
        if model.is_default and not model.is_not_supported_reason and include_default_models_count > 0:
            models.append(ModelResponse.from_service(model))
            include_default_models_count -= 1
            continue

        if model.id in _include_models:
            models.append(ModelResponse.from_service(model))

    return Page(items=models)


class WeeklyRunsResponse(BaseModel):
    start_of_week: date
    run_count: int
    overhead_ms: int

    @classmethod
    def from_domain(cls, weekly_run: WeeklyRunAggregate):
        return cls(
            start_of_week=weekly_run.start_of_week,
            run_count=weekly_run.run_count,
            overhead_ms=weekly_run.overhead_ms,
        )


@router.get("/weekly-runs")
async def get_weekly_runs(
    system_storage: SystemStorageDep,
    week_count: Annotated[int, Query(ge=1, le=10)],
) -> Page[WeeklyRunsResponse]:
    # Caching the result for 10 minutes
    # Passing the current week as an argument to avoid cache hits when the week changes
    @redis_cached(expiration_seconds=60 * 10)
    async def _fetch_weekly_runs(week_count: int, current_week: int):
        return [
            WeeklyRunsResponse.from_domain(r) async for r in system_storage.task_runs.weekly_run_aggregate(week_count)
        ]

    current_week = date.today().isocalendar().week
    weekly_runs = await _fetch_weekly_runs(week_count=week_count, current_week=current_week)
    return Page(items=weekly_runs)


class UptimeResponse(BaseModel):
    uptime_percent: float | None
    since: date | None
    source: str


@router.get("/uptimes/workflowai")
async def get_workflowai_uptime() -> UptimeResponse:
    uptime_info = await UptimeService().get_workflowai_uptime()
    return UptimeResponse(
        uptime_percent=uptime_info.uptime,
        since=uptime_info.since,
        source=uptime_info.source,
    )


@router.get("/uptimes/openai")
async def get_openai_uptime() -> UptimeResponse:
    uptime_info = await UptimeService().get_openai_uptime()
    return UptimeResponse(
        uptime_percent=uptime_info.uptime,
        since=uptime_info.since,
        source=uptime_info.source,
    )
