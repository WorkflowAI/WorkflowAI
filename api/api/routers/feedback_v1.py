from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field

from api.dependencies.event_router import SystemEventRouterDep
from api.dependencies.security import RequiredUserDep, SystemStorageDep
from api.dependencies.services import FeedbackServiceDep, FeedbackTokenGeneratorDep
from api.dependencies.task_info import TaskTupleDep
from api.services.feedback_svc import FeedbackService
from api.tags import RouteTags
from core.domain.feedback import Feedback, FeedbackAnnotation
from core.domain.page import Page
from core.utils.fields import datetime_zero

# A router dedicated to posting feedback
# The authentication will be different, since it will rely on a feedback token
# which is a signed token instead of an API key
feedback_router = APIRouter(prefix="/v1/feedback", tags=[RouteTags.FEEDBACK])


class CreateFeedbackRequest(BaseModel):
    feedback_token: str = Field(description="The feedback token, as returned in the run payload")
    outcome: Literal["positive", "negative"]
    comment: str | None = Field(default=None, description="An optional comment for the feedback")
    user_id: str | None = Field(
        default=None,
        description="An ID for the user that is posting the feedback. "
        "Only a single feedback per user (including anonymous) per feedback_token is allowed. "
        "Posting a new feedback will overwrite the existing one.",
    )


class CreateFeedbackResponse(BaseModel):
    id: str
    outcome: Literal["positive", "negative"]
    comment: str | None
    user_id: str | None


@feedback_router.post(
    "",
    description="Post a feedback. This endpoint does not require "
    "authentication since the feedback_token itself serves as a signed token",
)
async def create_run_feedback(
    request: CreateFeedbackRequest,
    system_storage: SystemStorageDep,
    token_generator: FeedbackTokenGeneratorDep,
    event_router: SystemEventRouterDep,
) -> CreateFeedbackResponse:
    feedback = await FeedbackService.create_feedback(
        system_storage.feedback,
        token_generator.verify_token,
        request.feedback_token,
        request.outcome,
        request.comment,
        request.user_id,
        event_router=event_router,
    )
    return CreateFeedbackResponse(
        id=feedback.id,
        outcome=feedback.outcome,
        comment=feedback.comment,
        user_id=feedback.user_id,
    )


class GetFeedbackResponse(BaseModel):
    outcome: Literal["positive", "negative"] | None


@feedback_router.get("", description="Get the outcome for a feedback given a token and a user ID")
async def get_feedback_outcome(
    system_storage: SystemStorageDep,
    token_generator: FeedbackTokenGeneratorDep,
    feedback_token: Annotated[str, Query(description="The feedback, as received in the run payload")],
    user_id: Annotated[str | None, Query(description="The user ID of the feedback")],
) -> GetFeedbackResponse:
    feedback = await FeedbackService.get_feedback(
        system_storage.feedback,
        token_generator.verify_token,
        feedback_token,
        user_id,
    )
    return GetFeedbackResponse(outcome=feedback.outcome if feedback else None)


router = APIRouter(prefix="/v1", tags=[RouteTags.FEEDBACK])


class FeedbackItem(BaseModel):
    id: str
    outcome: Literal["positive", "negative"]
    user_id: str | None
    created_at: datetime
    comment: str | None
    run_id: str

    annotation: Literal["resolved", "incorrect", "correct"] | None

    @classmethod
    def from_domain(cls, feedback: Feedback) -> "FeedbackItem":
        return cls(
            id=feedback.id,
            outcome=feedback.outcome,
            user_id=feedback.user_id,
            comment=feedback.comment,
            created_at=feedback.created_at or datetime_zero(),
            annotation=feedback.annotation.status if feedback.annotation else None,
            run_id=feedback.run_id,
        )


@router.get("/{tenant}/agents/{agent_id}/runs/{run_id}/feedback", response_model_exclude_none=True)
async def list_run_feedback(
    task_tuple: TaskTupleDep,
    run_id: str,
    feedback_service: FeedbackServiceDep,
    limit: Annotated[int, Query(description="The number of feedback items to return")] = 30,
    offset: Annotated[int, Query(description="The offset of the feedback items to return")] = 0,
) -> Page[FeedbackItem]:
    return await feedback_service.list_feedback(
        task_tuple[1],
        run_id=run_id,
        limit=limit,
        offset=offset,
        map_fn=FeedbackItem.from_domain,
    )


@router.get("/{tenant}/agents/{agent_id}/feedback")
async def list_task_feedback(
    task_tuple: TaskTupleDep,
    feedback_service: FeedbackServiceDep,
    limit: Annotated[int, Query(description="The number of feedback items to return")] = 30,
    offset: Annotated[int, Query(description="The offset of the feedback items to return")] = 0,
) -> Page[FeedbackItem]:
    return await feedback_service.list_feedback(
        task_tuple[1],
        run_id=None,
        limit=limit,
        offset=offset,
        map_fn=FeedbackItem.from_domain,
    )


class AnnotateFeedbackRequest(BaseModel):
    annotation: Literal["resolved", "incorrect", "correct"]
    comment: str | None = None


@router.post("/{tenant}/agents/{agent_id}/feedback/{feedback_id}/annotate")
async def annotate_feedback(
    feedback_id: Annotated[
        str,
        Path(description="The id of the feedback object, as returned by the feedback endpoint"),
    ],
    annotate_feedback_request: AnnotateFeedbackRequest,
    required_user: RequiredUserDep,
    feedback_service: FeedbackServiceDep,
) -> None:
    await feedback_service.annotate_feedback(
        feedback_id,
        FeedbackAnnotation(
            status=annotate_feedback_request.annotation,
            comment=annotate_feedback_request.comment,
            annotated_by=required_user.identifier(),
        ),
    )
