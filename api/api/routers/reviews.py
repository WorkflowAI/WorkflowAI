from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Path, Response
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from api.dependencies.path_params import AgentID, RunID, TaskSchemaID
from api.dependencies.security import RequiredUserDep
from api.dependencies.services import ReviewsServiceDep
from api.dependencies.storage import StorageDep
from api.dependencies.task_info import TaskTupleDep
from api.schemas.version_properties import ShortVersionProperties
from api.services.reviews import ReviewsService
from core.domain.errors import BadRequestError, DuplicateValueError
from core.domain.page import Page
from core.domain.review import Review as DomainReview
from core.domain.review_benchmark import ReviewBenchmark as DomainReviewBenchmark
from core.domain.task_evaluator import EvalV2Evaluator
from core.domain.types import AgentOutput
from core.domain.users import UserIdentifier
from core.storage import ObjectNotFoundException

router = APIRouter(prefix="/agents/{agent_id}")


class CreateReviewRequest(BaseModel):
    outcome: Literal["positive", "negative"]
    comment: str | None = None


class UserReviewer(UserIdentifier):
    reviewer_type: Literal["user"] = "user"

    @classmethod
    def from_domain(cls, reviewer: DomainReview.UserReviewer):
        return cls(
            user_id=reviewer.user_id,
            user_email=reviewer.user_email,
        )


class AIReviewer(BaseModel):
    reviewer_type: Literal["ai"] = "ai"

    @classmethod
    def from_domain(cls, reviewer: DomainReview.AIReviewer):
        return cls()


class Review(BaseModel):
    # A mongodb generated id, e-g 507f1f77bcf86cd799439011
    id: str
    created_at: datetime
    created_by: Annotated[UserReviewer | AIReviewer, Field(discriminator="reviewer_type")]
    outcome: Literal["positive", "negative", "unsure"] | None
    status: Literal["in_progress", "completed"]
    comment: str | None = Field(
        default=None,
        description="A comment left by the reviewer",
        deprecated="use summary instead",
    )

    summary: str | None = None
    positive_aspects: list[str] | None = None
    negative_aspects: list[str] | None = None

    @classmethod
    def _reviewer_from_domain(cls, reviewer: DomainReview.UserReviewer | DomainReview.AIReviewer):
        if isinstance(reviewer, DomainReview.UserReviewer):
            return UserReviewer.from_domain(reviewer)
        return AIReviewer.from_domain(reviewer)

    @classmethod
    def from_domain(cls, review: DomainReview):
        return cls(
            id=review.id,
            created_at=review.created_at,
            created_by=cls._reviewer_from_domain(review.reviewer),
            outcome=review.outcome,
            status=review.status,
            comment=review.comment,
            summary=review.comment,
            positive_aspects=review.positive_aspects,
            negative_aspects=review.negative_aspects,
        )


async def run_hash_info(
    task_tuple: TaskTupleDep,
    run_id: RunID,
    storage: StorageDep,
) -> tuple[str, str, int, Literal["success", "failure"]]:
    run = await storage.task_runs.fetch_task_run_resource(
        task_tuple,
        run_id,
        include={"task_input_hash", "task_output_hash", "task_schema_id", "status"},
    )
    return run.task_input_hash, run.task_output_hash, run.task_schema_id, run.status


_RunHashInfoDep = Annotated[tuple[str, str, int, Literal["success", "failure"]], Depends(run_hash_info)]


@router.post("/runs/{run_id}/reviews", description="Create a user review for a given run")
async def create_review(
    request: CreateReviewRequest,
    agent_id: AgentID,
    user: RequiredUserDep,  # user will be marked as the creator of the review
    reviews_service: ReviewsServiceDep,
    run_hash_info: _RunHashInfoDep,
    run_id: RunID,
) -> Review:
    if run_hash_info[3] == "failure":
        raise BadRequestError("Cannot review a failed run")
    review = await reviews_service.add_user_review(
        task_id=agent_id,
        task_schema_id=run_hash_info[2],
        task_input_hash=run_hash_info[0],
        task_output_hash=run_hash_info[1],
        outcome=request.outcome,
        comment=request.comment,
        user=UserIdentifier(user_id=user.user_id, user_email=user.sub),
        run_id=run_id,
    )
    return Review.from_domain(review)


@router.get(
    "/runs/{run_id}/reviews",
    description="Retrieve the most recent non-stale reviews for a given run."
    "A review becomes state if either a new review of the same type was created or if the review was responded to",
)
async def list_reviews(
    agent_id: AgentID,
    run_hash_info: _RunHashInfoDep,
    reviews_service: ReviewsServiceDep,
) -> Page[Review]:
    reviews = await reviews_service.list_reviews(
        task_id=agent_id,
        task_schema_id=run_hash_info[2],
        task_input_hash=run_hash_info[0],
        task_output_hash=run_hash_info[1],
    )
    return Page(items=[Review.from_domain(r) for r in reviews])


class RespondToReviewRequest(BaseModel):
    comment: str


@router.post(
    "/runs/{run_id}/reviews/{review_id}/respond",
    description="Respond to a review by adding a comment, triggering an improvement of the evaluation instructions."
    "A user review must exist.",
)
async def respond_to_review(
    agent_id: AgentID,
    review_id: Annotated[str, Path(description="The id of the AI review to respond to")],
    request: RespondToReviewRequest,
    reviews_service: ReviewsServiceDep,
    run_hash_info: _RunHashInfoDep,
) -> Response:
    await reviews_service.respond_to_review(
        task_id=agent_id,
        task_schema_id=run_hash_info[2],
        task_input_hash=run_hash_info[0],
        task_output_hash=run_hash_info[1],
        review_id=review_id,
        comment=request.comment,
    )
    return Response(status_code=204)


class ReviewBenchmark(BaseModel):
    class VersionResult(BaseModel):
        iteration: int
        properties: ShortVersionProperties

        # Aggregated data about reviews
        positive_review_count: int = Field(description="The number of positive reviews for the version")
        positive_user_review_count: int = Field(
            description="The number of positive reviews that were left by users",
        )
        negative_review_count: int = Field(
            description="The number of negative reviews for the version,"
            "including both runs that were rejected and runs that failed because the output was invalid",
        )
        negative_user_review_count: int = Field(
            description="The number of negative reviews that were left by users",
        )
        unsure_review_count: int = Field(
            description="The number of unsure reviews for the version",
        )
        in_progress_review_count: int = Field(
            description="The number of reviews that are still in progress for the version, either because"
            "the run has not yet completed or because the review has not yet been computed",
        )

        average_cost_usd: float | None
        average_duration_seconds: float | None

        @classmethod
        def from_domain(cls, aggregation: DomainReviewBenchmark.VersionAggregation):
            return cls(
                iteration=aggregation.iteration,
                properties=ShortVersionProperties.from_domain(aggregation.properties),
                positive_review_count=aggregation.positive_review_count,
                positive_user_review_count=aggregation.positive_user_review_count,
                negative_review_count=aggregation.negative_review_count,
                negative_user_review_count=aggregation.negative_user_review_count,
                unsure_review_count=aggregation.unsure_review_count,
                in_progress_review_count=aggregation.in_progress_review_count + aggregation.run_in_progress_count,
                average_cost_usd=aggregation.average_cost_usd,
                average_duration_seconds=aggregation.average_duration_seconds,
            )

    results: list[VersionResult]

    is_building_ai_reviewer: bool = Field(
        default=False,
        description="Whether a new AI reviewer is being built."
        "When done building, some reviews that need to be recomputed",
    )

    @classmethod
    def from_domain(cls, benchmark: DomainReviewBenchmark):
        return cls(
            results=[ReviewBenchmark.VersionResult.from_domain(r) for r in benchmark.results],
            is_building_ai_reviewer=benchmark.is_loading_new_ai_reviewer,
        )


@router.get(
    "/schemas/{task_schema_id}/reviews/benchmark",
    description="Retrieve the benchmark for a given task schema",
)
async def get_review_benchmark(agent_id: AgentID, task_schema_id: TaskSchemaID, storage: StorageDep) -> ReviewBenchmark:
    try:
        benchmark = await storage.review_benchmarks.get_review_benchmark(agent_id, task_schema_id)
        return ReviewBenchmark.from_domain(benchmark)
    except ObjectNotFoundException:
        return ReviewBenchmark(results=[])


class PatchReviewBenchmarkRequest(BaseModel):
    add_versions: list[int] | None = None
    remove_versions: list[int] | None = None


@router.patch(
    "/schemas/{task_schema_id}/reviews/benchmark",
    description="Patch a review benchmark",
    response_model_exclude_none=True,
)
async def patch_review_benchmark(
    agent_id: AgentID,
    task_schema_id: TaskSchemaID,
    request: PatchReviewBenchmarkRequest,
    reviews_service: ReviewsServiceDep,
) -> ReviewBenchmark:
    benchmark = None
    try:
        if request.add_versions:
            benchmark = await reviews_service.add_versions_to_review_benchmark(
                agent_id,
                task_schema_id,
                request.add_versions,
            )
    except DuplicateValueError:
        raise BadRequestError("Duplicate iteration")

    if request.remove_versions:
        benchmark = await reviews_service.remove_versions_from_review_benchmark(
            agent_id,
            task_schema_id,
            request.remove_versions,
        )

    if not benchmark:
        raise BadRequestError("No versions to add or remove")
    return ReviewBenchmark.from_domain(benchmark)


class TaskEvaluationResponse(BaseModel):
    evaluation_instructions: str = Field(
        description="The task level instructions for the AI reviewer. "
        "The instructions are passed with every evaluation.",
    )


@router.get("/schemas/{task_schema_id}/evaluation")
async def get_task_evaluation(
    agent_id: AgentID,
    task_schema_id: TaskSchemaID,
    user: RequiredUserDep,
    reviews_service: ReviewsServiceDep,
) -> TaskEvaluationResponse:
    evaluator = await reviews_service.get_latest_ai_evaluator(agent_id, task_schema_id, active=True)
    if not evaluator:
        return TaskEvaluationResponse(evaluation_instructions="")
    assert isinstance(evaluator.evaluator_type, EvalV2Evaluator)
    return TaskEvaluationResponse(evaluation_instructions=evaluator.evaluator_type.instructions)


class TaskEvaluationPatchRequest(BaseModel):
    evaluation_instructions: str


@router.patch("/schemas/{task_schema_id}/evaluation")
async def update_task_evaluation(
    agent_id: AgentID,
    task_schema_id: TaskSchemaID,
    request: TaskEvaluationPatchRequest,
    user: RequiredUserDep,
    reviews_service: ReviewsServiceDep,
) -> TaskEvaluationResponse:
    inserted = await reviews_service.update_task_evaluator(
        task_id=agent_id,
        task_schema_id=task_schema_id,
        instructions=request.evaluation_instructions,
        user=UserIdentifier(user_id=user.user_id, user_email=user.sub),
    )
    assert isinstance(inserted.evaluator_type, EvalV2Evaluator)
    return TaskEvaluationResponse(evaluation_instructions=inserted.evaluator_type.instructions)


class InputEvaluationData(BaseModel):
    task_input_hash: str
    task_input: dict[str, Any]

    correct_outputs: list[AgentOutput]
    incorrect_outputs: list[AgentOutput]

    evaluation_instructions: str

    @classmethod
    def from_domain(cls, input: ReviewsService.ReviewedInput):
        return cls(
            task_input_hash=input.task_input_hash,
            task_input=input.task_input,
            correct_outputs=input.correct_outputs,
            incorrect_outputs=input.incorrect_outputs,
            evaluation_instructions=input.evaluation_instructions or "",
        )


@router.get("/schemas/{task_schema_id}/evaluation/inputs")
async def get_ai_reviewer_evaluation_instructions(
    task_id: TaskTupleDep,
    task_schema_id: TaskSchemaID,
    reviews_service: ReviewsServiceDep,
) -> Page[InputEvaluationData]:
    reviewed_inputs = await reviews_service.list_reviewed_inputs(task_id, task_schema_id)
    return Page(
        items=[InputEvaluationData.from_domain(i) for i in reviewed_inputs],
        count=len(reviewed_inputs),
    )


class InputEvaluationPatchRequest(BaseModel):
    update_input_evaluation_instructions: str | None = Field(
        default=None,
        description="The evaluation instructions to use for the input",
    )
    add_correct_output: dict[str, Any] | None = Field(
        default=None,
        description="A correct output to use in evaluations. If the output already existed as an incorrect output, "
        "the matching incorrect output is removed. If the output already existed in the correct outputs, the output is "
        "ignored",
    )
    remove_correct_output: dict[str, Any] | None = Field(
        default=None,
        description="A correct output to remove from evaluations",
    )
    add_incorrect_output: dict[str, Any] | None = Field(
        default=None,
        description="An incorrect output to use in evaluations. If the output already existed as a correct output, "
        "the matching correct output is removed. If the output already existed in the incorrect outputs, the output is "
        "ignored",
    )
    remove_incorrect_output: dict[str, Any] | None = Field(
        default=None,
        description="An incorrect output to remove from evaluations",
    )


@router.patch("/schemas/{task_schema_id}/evaluation/inputs/{task_input_hash}")
async def update_input_evaluation(
    agent_id: AgentID,
    task_schema_id: TaskSchemaID,
    task_input_hash: Annotated[str, Path(description="The hash of the task input evaluation to update")],
    request: InputEvaluationPatchRequest,
    reviews_service: ReviewsServiceDep,
    user: RequiredUserDep,
) -> InputEvaluationData:
    res = await reviews_service.update_input_evaluation(
        task_id=agent_id,
        task_schema_id=task_schema_id,
        task_input_hash=task_input_hash,
        instructions=request.update_input_evaluation_instructions,
        correct_outputs=ReviewsService.OutputListUpdate(
            add=request.add_correct_output,
            remove=request.remove_correct_output,
        ),
        incorrect_outputs=ReviewsService.OutputListUpdate(
            add=request.add_incorrect_output,
            remove=request.remove_incorrect_output,
        ),
        user=user.identifier(),
    )
    return InputEvaluationData.from_domain(res)
