import logging
from typing import Any, Literal, NamedTuple, Protocol, TypedDict, cast

from core.domain.agent_run import TaskRunIO
from core.domain.errors import BadRequestError, DuplicateValueError, InternalError
from core.domain.events import (
    AIReviewCompletedEvent,
    AIReviewerBuildStartedEvent,
    AIReviewerUpdatedEvent,
    AIReviewStartedEvent,
    EventRouter,
    RecomputeReviewBenchmarkEvent,
    TriggerRunEvaluationEvent,
    TriggerTaskRunEvent,
    UserReviewAddedEvent,
)
from core.domain.input_evaluation import InputEvaluation
from core.domain.review import Review, ReviewerType, ReviewOutcome
from core.domain.run_identifier import RunIdentifier
from core.domain.task_evaluation import TaskEvaluationScore
from core.domain.task_evaluator import EvalV2Evaluator, TaskEvaluator
from core.domain.task_group import TaskGroupQuery
from core.domain.task_run_query import SerializableTaskRunField, SerializableTaskRunQuery
from core.domain.task_variant import SerializableTaskVariant
from core.domain.types import AgentOutput
from core.domain.users import UserIdentifier
from core.evaluators.input_task_evaluator import (
    InputTaskEvaluator,
    InputTaskEvaluatorOptions,
    InternalTasksForEvaluations,
)
from core.storage import ObjectNotFoundException, TaskTuple
from core.storage.backend_storage import BackendStorage
from core.storage.review_benchmark_storage import RunReviewAggregateWithIteration
from core.storage.reviews_storage import AIReviewerFilter
from core.storage.task_run_storage import RunAggregate
from core.utils.fields import datetime_factory
from core.utils.models.dumps import safe_dump_pydantic_model


class _InternalTasks(InternalTasksForEvaluations, Protocol):
    async def update_correct_outputs_and_instructions(
        self,
        evaluation_instructions: str,
        input_evaluation: InputEvaluation,
        evaluated_output: dict[str, Any],
        previous_evaluation_result: TaskEvaluationScore,
        user_rating_is_correct: bool,
        user_feedback: str | None,
    ) -> tuple[EvalV2Evaluator, InputEvaluation]: ...


class _RunReviewAggregate(TypedDict):
    version_id: str

    in_progress_review_count: int | None
    positive_review_count: int | None
    positive_user_review_count: int | None
    negative_review_count: int | None
    negative_user_review_count: int | None
    unsure_review_count: int | None
    average_cost_usd: float | None
    average_duration_seconds: float | None
    total_run_count: int
    failed_run_count: int | None


class ReviewsService:
    def __init__(
        self,
        backend_storage: BackendStorage,
        internal_tasks: _InternalTasks,
        event_router: EventRouter,
    ):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._storage = backend_storage
        self._internal_tasks = internal_tasks
        self._reviews_storage = self._storage.reviews
        self._event_router = event_router

    # TODO: trigger AI evaluation updates

    # TODO: test
    async def add_user_review(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        outcome: Literal["positive", "negative", "unsure"],
        comment: str | None,
        user: UserIdentifier,
        run_id: str,
    ):
        current_review = await self._reviews_storage.get_review_by_hash(
            task_id,
            task_schema_id,
            task_input_hash,
            task_output_hash,
        )

        # Mark all ai reviews for this task as stale
        # This should not needed if there are no current reviews but we never know
        await self._reviews_storage.mark_as_stale(task_id, task_schema_id, task_input_hash, task_output_hash, "ai")

        user_review = Review(
            task_id=task_id,
            task_schema_id=task_schema_id,
            task_input_hash=task_input_hash,
            task_output_hash=task_output_hash,
            outcome=outcome,
            comment=comment,
            reviewer=Review.UserReviewer(user_id=user.user_id, user_email=user.user_email),
            status="completed",
        )

        review = await self._reviews_storage.insert_review(user_review)
        # TODO: the way we compute is_first_review is subject to race conditions
        # We could have a race where two users add a review more or less at the same time
        # Which would mean that we would send 2 events with current_review being None
        # That's ok for now, it will trigger runs twice for the same input but because of the cache it should
        # be fast and idempotent
        # The proper way would be storing all reviewed input separately see
        # https://linear.app/workflowai/issue/WOR-2612/store-reviewed-inputs-separately-for-benchmarks
        self._event_router(
            UserReviewAddedEvent.from_review(review, run_id=run_id, is_first_review=current_review is None),
        )
        return review

    async def add_manual_ai_review(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        outcome: ReviewOutcome,
        comment: str | None,
        evaluator_id: str,  # Should correspond to an existing AI evaluator configuration
        input_evaluation_id: str,  # Should correspond to an existing input evaluation (human review baseline), or be an empty string if not applicable.
        confidence_score: float | None,
        run_identifier_details: dict[str, Any] | None,  # For RunIdentifier domain object
        positive_aspects: list[str] | None,
        negative_aspects: list[str] | None,
        # user_who_added: UserIdentifier, # Optional: to track who manually added this AI review
    ):
        # Mark existing AI reviews for this specific input/output as stale,
        # as this manual entry is considered more definitive or a correction.
        await self._reviews_storage.mark_as_stale(
            task_id,
            task_schema_id,
            task_input_hash,
            task_output_hash,
            "ai",
        )

        ai_reviewer_details = Review.AIReviewer(
            evaluator_id=evaluator_id,
            input_evaluation_id=input_evaluation_id,
            confidence_score=confidence_score,
            run_identifier=RunIdentifier.model_validate(run_identifier_details) if run_identifier_details else None,
        )

        manual_ai_review = Review(
            task_id=task_id,
            task_schema_id=task_schema_id,
            task_input_hash=task_input_hash,
            task_output_hash=task_output_hash,
            outcome=outcome,
            comment=comment,
            reviewer=ai_reviewer_details,
            status="completed",  # Manual AI reviews are directly completed
            positive_aspects=positive_aspects,
            negative_aspects=negative_aspects,
            # Potentially add created_by_user=user_who_added if tracking is needed
        )

        # We are not emitting an AIReviewCompletedEvent here to distinguish
        # this manual addition from an automated AI evaluation.
        # If downstream processing is needed, a new specific event could be created.
        return await self._reviews_storage.insert_review(manual_ai_review)

    async def list_reviews(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
    ):
        reviews: list[Review] = []
        found_user_or_loading = False
        async for r in self._reviews_storage.list_reviews(
            task_id=task_id,
            task_schema_id=task_schema_id,
            task_input_hash=task_input_hash,
            task_output_hash=task_output_hash,
        ):
            if r.reviewer.reviewer_type == "user" or r.status == "in_progress":
                found_user_or_loading = True
            reviews.append(r)

        if not found_user_or_loading:
            last_eval = await self.get_latest_ai_evaluator(task_id, task_schema_id)
            if last_eval and last_eval.is_loading:
                reviews.insert(
                    0,
                    Review(
                        task_id=task_id,
                        task_schema_id=task_schema_id,
                        task_input_hash=task_input_hash,
                        task_output_hash=task_output_hash,
                        outcome=None,
                        reviewer=Review.AIReviewer(evaluator_id=last_eval.id, input_evaluation_id=""),
                        status="in_progress",
                    ),
                )
        return reviews

    async def _get_latest_review(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        reviewer_type: ReviewerType,
    ):
        try:
            return await anext(
                self._reviews_storage.list_reviews(
                    task_id,
                    task_schema_id,
                    task_input_hash,
                    task_output_hash,
                    reviewer_type,
                    limit=1,
                ),
            )
        except StopAsyncIteration:
            return None

    # TODO: test
    async def respond_to_review(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        review_id: str,
        comment: str,
    ):
        user_review = await self._get_latest_review(
            task_id,
            task_schema_id,
            task_input_hash,
            task_output_hash,
            "user",
        )
        if not user_review:
            raise BadRequestError("Can only respond when there is a user review")

        ai_review = await self._reviews_storage.get_review_by_id(task_id, task_schema_id, review_id)
        if ai_review.outcome == "unsure":
            raise BadRequestError("Cannot respond to an unsure review")
        if ai_review.reviewer.reviewer_type != "ai":
            raise BadRequestError("Can only respond to an AI review")

        try:
            await self._reviews_storage.add_comment_to_review(
                user_review.id,
                comment,
                responding_to=review_id,
            )
        except ObjectNotFoundException:
            raise InternalError("User review not found", extras={"review_id": user_review.id})
        user_review.comment = comment  # not needed, adding just for clarity
        user_review.responding_to_review_id = review_id

        self._event_router(UserReviewAddedEvent.from_review(user_review))

    async def get_latest_ai_evaluator(self, task_id: str, task_schema_id: int, active: bool | None = None):
        try:
            return await anext(
                self._storage.evaluators.list_task_evaluators(
                    task_id,
                    task_schema_id,
                    types={"evalv2"},
                    active=active,
                    limit=1,
                ),
            )
        except StopAsyncIteration:
            return None

    def _empty_ai_evaluator(self) -> TaskEvaluator:
        return TaskEvaluator(
            id="",
            name="",
            evaluator_type=EvalV2Evaluator(instructions=""),
        )

    async def _gather_evaluation_data_for_run(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        evaluator_id: str | None = None,
        input_evaluation_id: str | None = None,
    ):
        ai_evaluator = await self.get_latest_ai_evaluator(task_id, task_schema_id)
        if not ai_evaluator:
            # If we don't have one that's ok, we return an empty one
            # We will not have an evaluator until we have task evaluation instructions
            ai_evaluator = self._empty_ai_evaluator()
        if ai_evaluator.is_loading:
            self._logger.info("Skipping review since evaluator is loading")
            return None
        if not isinstance(ai_evaluator.evaluator_type, EvalV2Evaluator):
            self._logger.error(
                "Found non-evalv2 evaluator for task",
                extra={
                    "task_id": task_id,
                    "task_schema_id": task_schema_id,
                },
            )
            return None

        if evaluator_id and evaluator_id != ai_evaluator.id:
            self._logger.info("Skipping review since evaluator does not match")
            return None

        latest_input_evaluation = await self._storage.input_evaluations.get_latest_input_evaluation(
            task_id=task_id,
            task_schema_id=task_schema_id,
            input_hash=task_input_hash,
        )
        if not latest_input_evaluation:
            self._logger.info("Skipping review since no input evaluation found")
            return None
        if input_evaluation_id and input_evaluation_id != latest_input_evaluation.id:
            self._logger.info("Skipping review since input evaluation does not match")
            return None

        return (ai_evaluator, latest_input_evaluation)

    async def _task_run_for_review(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str | None,
        include_fields: set[SerializableTaskRunField] | None = None,
    ) -> TaskRunIO | None:
        query = SerializableTaskRunQuery(
            task_id=task_id[0],
            task_schema_id=task_schema_id,
            task_input_hashes={task_input_hash},
            task_output_hash=task_output_hash,
            limit=1,
            include_fields=include_fields or {"task_input", "task_output"},
            status={"success"},
        )
        try:
            return await anext(self._storage.task_runs.fetch_task_run_resources(task_id[1], query))
        except StopAsyncIteration:
            return None

    async def _build_input_evaluator(
        self,
        task: SerializableTaskVariant,
        data: TaskEvaluator,
        input_evaluation: InputEvaluation,
    ):
        evaluator = InputTaskEvaluator(
            task=task,
            options=InputTaskEvaluatorOptions(
                evaluator_id=data.id,
                task_data=cast(EvalV2Evaluator, data.evaluator_type),
                input_evaluation=input_evaluation,
            ),
            internal_tasks=self._internal_tasks,
        )

        await evaluator.prepare()
        return evaluator

    # Returns None if there is already a review with the same properties
    async def _insert_in_progress_review(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        evaluator_id: str | None,
        input_evaluation_id: str,
        run_id: str,
        version_id: str,
    ):
        try:
            review = await self._reviews_storage.insert_in_progress_review(
                task_id=task_id,
                task_schema_id=task_schema_id,
                task_input_hash=task_input_hash,
                task_output_hash=task_output_hash,
                evaluator_id=evaluator_id,
                input_evaluation_id=input_evaluation_id,
            )
            self._event_router(
                AIReviewStartedEvent(
                    task_id=review.task_id,
                    task_schema_id=review.task_schema_id,
                    review_id=review.id,
                    task_input_hash=review.task_input_hash,
                    task_output_hash=review.task_output_hash,
                    run_id=run_id,
                    version_id=version_id,
                ),
            )
            return review
        except DuplicateValueError:
            # Someone else already created the review
            return None

    async def _evaluate_run(
        self,
        evaluator: InputTaskEvaluator,
        run: TaskRunIO,
        review: Review,
    ):
        completed_event = AIReviewCompletedEvent(
            task_id=review.task_id,
            task_schema_id=review.task_schema_id,
            review_id=review.id,
            task_input_hash=review.task_input_hash,
            task_output_hash=review.task_output_hash,
            reviewer_type="ai",
        )
        try:
            score = await evaluator.evaluate(run, example=None)
            outcome, confidence_score, run_identifier = InputTaskEvaluator.parse_evaluation(score)
        except Exception as e:
            # Capturing all exceptions, otherwise we would create a state that cannot be resolved
            # since a review would be in progress forever
            self._logger.exception("Failed to complete review", exc_info=e, extra={"review": review.model_dump()})
            await self._reviews_storage.fail_review(review.id)
            # No need to pass the review id since it will no longer exist
            completed_event.review_id = None
            self._event_router(completed_event)
            return

        await self._reviews_storage.complete_review(
            review_id=review.id,
            outcome=outcome,
            comment=score.comment,
            confidence_score=confidence_score,
            run_identifier=run_identifier,
            positive_aspects=score.positive_aspects,
            negative_aspects=score.negative_aspects,
        )
        await self._reviews_storage.mark_as_stale(
            task_id=review.task_id,
            task_schema_id=review.task_schema_id,
            task_input_hash=review.task_input_hash,
            task_output_hash=review.task_output_hash,
            reviewer_type="ai",
            before_id=review.id,
        )

        self._event_router(completed_event)

    async def _insert_review_for_failed_run(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        run_id: str,
        version_id: str,
    ):
        await self._reviews_storage.insert_review(
            Review(
                task_id=task_id[0],
                task_uid=task_id[1],
                task_schema_id=task_schema_id,
                task_input_hash=task_input_hash,
                task_output_hash=task_output_hash,
                outcome="negative",
                status="completed",
                reviewer=Review.UserReviewer(user_id=None, user_email=None),
                comment="The model failed to return a valid output",
            ),
        )

    async def _prepare_evaluation_data(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        run_id: str,
        evaluator_id: str | None,
        input_evaluation_id: str | None,
        run_failed: bool,
        version_id: str,
    ):
        """
        Retrieves the latest evaluation data and checks whether it would make sense
        to trigger a new evaluation or recompute benchmarks.

        Returns a tuple latest evaluation data or None | should recompute benchmarks"""
        review_filter: dict[str, Any] = {
            "task_id": task_id[0],
            "task_schema_id": task_schema_id,
            "task_input_hash": task_input_hash,
            "task_output_hash": task_output_hash,
            "include": {"outcome", "status"},
        }

        # First we check if there is a user review
        user_review = await self._reviews_storage.get_review_by_hash(**review_filter, reviewer="user")

        if user_review and user_review.outcome:
            # No need to evaluate but we should recompute benchmarks since there is a new affected run
            return None, True

        # Now we check if we can evaluate the run
        evaluation_data = await self._gather_evaluation_data_for_run(
            task_id[0],
            task_schema_id,
            task_input_hash,
            evaluator_id=evaluator_id,
            input_evaluation_id=input_evaluation_id,
        )
        if not evaluation_data:
            # No need to evaluate or recompute benchmarks
            # Since there is no evaluation data available
            return None, False

        evaluator_data, latest_input_evaluation = evaluation_data
        ai_review = await self._reviews_storage.get_review_by_hash(
            **review_filter,
            reviewer=AIReviewerFilter(
                evaluator_id=evaluator_data.id,
                input_evaluation_id=latest_input_evaluation.id,
            ),
        )

        # Then check if there is already an AI review with the same evaluator and input evaluation
        if ai_review:
            return None, True

        # Here we know that:
        # - the run should be evaluated since it has evaluation data
        # - the run does not yet have an evaluation
        if run_failed:
            # The run has failed, so we automatically create a negative user review
            await self._insert_review_for_failed_run(
                task_id,
                task_schema_id,
                task_input_hash,
                task_output_hash,
                run_id,
                version_id,
            )
            return None, True

        # There is an evaluation data available
        # But there is no need to immediately recompute benchmarks since
        # the benchmark will be recomputed when the ai review is completed
        return evaluation_data, False

    async def evaluate_runs_by_hash_if_needed(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        run_id: str,
        version_id: str,
        iteration: int,
        run_failed: bool,
        # If provided, we also check that the evaluator and input evaluation match
        evaluator_id: str | None = None,
        input_evaluation_id: str | None = None,
    ):
        task = await self._storage.task_variants.get_latest_task_variant(task_id, task_schema_id)
        if not task:
            self._logger.error(
                "No task variant found",
                extra={"task_id": task_id, "task_schema_id": task_schema_id},
            )
            return

        evaluation_data, should_recompute_benchmark = await self._prepare_evaluation_data(
            task_id=task.id_tuple,
            task_schema_id=task_schema_id,
            task_input_hash=task_input_hash,
            task_output_hash=task_output_hash,
            run_id=run_id,
            version_id=version_id,
            evaluator_id=evaluator_id,
            input_evaluation_id=input_evaluation_id,
            run_failed=run_failed,
        )

        if should_recompute_benchmark:
            self._event_router(
                RecomputeReviewBenchmarkEvent(
                    task_id=task_id,
                    task_schema_id=task_schema_id,
                    run_id=run_id,
                    iterations={iteration},
                ),
            )

        if not evaluation_data:
            return

        evaluator_data, latest_input_evaluation = evaluation_data

        run = await self._task_run_for_review(task.id_tuple, task_schema_id, task_input_hash, task_output_hash)
        if not run:
            self._logger.error(
                "No task run found for review",
                extra={
                    "task_id": task_id,
                    "task_schema_id": task_schema_id,
                    "task_input_hash": task_input_hash,
                    "task_output_hash": task_output_hash,
                },
            )
            return

        if review := await self._insert_in_progress_review(
            task_id,
            task_schema_id,
            task_input_hash,
            task_output_hash,
            evaluator_id=evaluator_data.id,
            input_evaluation_id=latest_input_evaluation.id,
            run_id=run_id,
            version_id=version_id,
        ):
            evaluator = await self._build_input_evaluator(task, evaluator_data, latest_input_evaluation)
            await self._evaluate_run(evaluator, run, review)

    async def _handle_no_comment_review(self, review: Review, run: TaskRunIO):
        latest_input_evaluation = await self._storage.input_evaluations.get_latest_input_evaluation(
            task_id=review.task_id,
            task_schema_id=review.task_schema_id,
            input_hash=review.task_input_hash,
        )
        if latest_input_evaluation:
            new_input_evaluation = latest_input_evaluation.model_copy(update={"id": ""})
        else:
            new_input_evaluation = InputEvaluation(
                task_input_hash=review.task_input_hash,
                correct_outputs=[],
                incorrect_outputs=[],
            )

        task = await self._storage.task_variants.get_latest_task_variant(review.task_id, review.task_schema_id)
        if not task:
            self._logger.error(
                "No task variant found",
                extra={"task_id": review.task_id, "task_schema_id": review.task_schema_id},
            )
            return

        edited = new_input_evaluation.add_output(
            task.output_schema.sanitize(run.task_output),
            review.outcome == "positive",
        )
        if not edited:
            return

        created_input_evaluation = await self._storage.input_evaluations.create_input_evaluation(
            task_id=review.task_id,
            task_schema_id=review.task_schema_id,
            input_evaluation=new_input_evaluation,
        )
        self._event_router(
            AIReviewerUpdatedEvent(
                task_id=review.task_id,
                task_schema_id=review.task_schema_id,
                task_input_hash=review.task_input_hash,
                input_evaluation_id=created_input_evaluation.id,
                evaluator_did_change=False,
                evaluator_id=None,
            ),
        )

    @staticmethod
    def _is_same_evaluator_data(reviewer: Review.AIReviewer, evaluator: TaskEvaluator | None):
        if not reviewer.evaluator_id and not evaluator:
            return True

        if evaluator and reviewer.evaluator_id == evaluator.id:
            return True

        return False

    @staticmethod
    def _get_eval_v2_evaluator(evaluator: TaskEvaluator | None):
        if not evaluator:
            return EvalV2Evaluator(instructions="")
        return cast(EvalV2Evaluator, evaluator.evaluator_type)

    async def _replace_evaluator_data(
        self,
        task_id: str,
        task_schema_id: int,
        existing_id: str | None,
        inserted_id: str,
        new_evaluator: EvalV2Evaluator,
    ):
        # This is not great and could lead to race conditions where multiple active evaluators exist for the
        # the same type.
        # Only one evaluator will be returned at a time in _get_active_ai_evaluator so we should be ok
        _evaluators_storage = self._storage.evaluators
        if existing_id:
            await _evaluators_storage.set_task_evaluator_active(
                task_id=task_id,
                task_schema_id=task_schema_id,
                evaluator_id=existing_id,
                active=False,
            )

        await _evaluators_storage.patch_evaluator(
            id=inserted_id,
            active=True,
            is_loading=False,
            evaluator_type=new_evaluator,
        )

    async def _should_update_ai_reviewer(self, review: Review, run: TaskRunIO):
        if not review.responding_to_review_id:
            raise InternalError("No responding to review id found", extras={"review": review.model_dump()})

        ai_review = await self._reviews_storage.get_review_by_id(
            review.task_id,
            review.task_schema_id,
            review.responding_to_review_id,
        )
        if not ai_review.reviewer.reviewer_type == "ai":
            raise InternalError("Review is not an ai review", extras={"review": ai_review.model_dump()})
        if not ai_review.outcome:
            raise InternalError("No outcome found", extras={"review": ai_review.model_dump()})

        active_evaluator = await self.get_latest_ai_evaluator(ai_review.task_id, ai_review.task_schema_id, active=True)
        if not self._is_same_evaluator_data(ai_review.reviewer, active_evaluator):
            self._logger.info("Skipping update ai reviewer update since evaluator id does not match")
            return None

        latest_input_data = await self._storage.input_evaluations.get_latest_input_evaluation(
            task_id=ai_review.task_id,
            task_schema_id=ai_review.task_schema_id,
            input_hash=ai_review.task_input_hash,
        )
        if not latest_input_data:
            raise InternalError("No input evaluation found", extras={"review": ai_review.model_dump()})

        # That will actually never happen, since the last user review updates the input evaluation
        # if latest_input_data.id != ai_review.reviewer.input_evaluation_id:
        #     self._logger.info("Skipping update ai reviewer update since input evaluation id does not match")
        #     return None

        return active_evaluator, ai_review.outcome, latest_input_data

    async def _handle_commented_review(self, review: Review, run: TaskRunIO):
        data = await self._should_update_ai_reviewer(review, run)
        if not data:
            return

        active_evaluator, previous_outcome, latest_input_data = data

        inserted_evaluator = await self._storage.evaluators.add_task_evaluator(
            task_id=review.task_id,
            task_schema_id=review.task_schema_id,
            task_evaluator=TaskEvaluator(
                id="",
                name=InputTaskEvaluator.name(),
                active=False,
                is_loading=True,
                triggers=set(),
                evaluator_type=EvalV2Evaluator(instructions=""),
            ),
        )
        task = await self._storage.task_variants.get_latest_task_variant(review.task_id, review.task_schema_id)
        if not task:
            self._logger.error(
                "No task variant found",
                extra={"task_id": review.task_id, "task_schema_id": review.task_schema_id},
            )
            return

        self._event_router(
            AIReviewerBuildStartedEvent(
                task_id=review.task_id,
                task_schema_id=review.task_schema_id,
                evaluator_id=inserted_evaluator.id,
            ),
        )

        existing_v2_evaluator = self._get_eval_v2_evaluator(active_evaluator)

        (
            new_eval_data,
            new_input_data,
        ) = await self._internal_tasks.update_correct_outputs_and_instructions(
            evaluation_instructions=existing_v2_evaluator.instructions,
            input_evaluation=latest_input_data,
            evaluated_output=task.output_schema.sanitize(run.task_output),
            previous_evaluation_result=TaskEvaluationScore.from_outcome(previous_outcome),
            user_rating_is_correct=review.outcome == "positive",
            user_feedback=review.comment,
        )

        update_event: AIReviewerUpdatedEvent | None = None
        if not new_input_data.is_similar_to(latest_input_data):
            await self._storage.input_evaluations.create_input_evaluation(
                task_id=review.task_id,
                task_schema_id=review.task_schema_id,
                input_evaluation=new_input_data,
            )

            # we trigger one just for the input evaluation
            update_event = AIReviewerUpdatedEvent(
                task_id=review.task_id,
                task_schema_id=review.task_schema_id,
                evaluator_id=inserted_evaluator.id,
                task_input_hash=review.task_input_hash,
                input_evaluation_id=new_input_data.id,
                evaluator_did_change=False,
            )

        if not new_eval_data.is_similar_to(existing_v2_evaluator):
            await self._replace_evaluator_data(
                review.task_id,
                review.task_schema_id,
                inserted_id=inserted_evaluator.id,
                existing_id=active_evaluator.id if active_evaluator else None,
                new_evaluator=new_eval_data,
            )
            # We need to refresh all reviews since the base evaluator has changed
            update_event = AIReviewerUpdatedEvent(
                task_id=review.task_id,
                task_schema_id=review.task_schema_id,
                evaluator_id=inserted_evaluator.id,
                evaluator_did_change=True,
            )

        if update_event:
            self._event_router(update_event)

    async def update_ai_reviewer_from_user_review(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        review_id: str,
        comment: str | None,
        responding_to_review_id: str | None,
    ):
        review = await self._get_latest_review(task_id, task_schema_id, task_input_hash, task_output_hash, "user")
        if not review:
            raise InternalError(
                "Could not find a user review",
                extras={
                    "task_id": task_id,
                    "task_schema_id": task_schema_id,
                    "task_input_hash": task_input_hash,
                    "task_output_hash": task_output_hash,
                },
            )
        if (
            review.id != review_id
            or review.comment != comment
            or review.responding_to_review_id != responding_to_review_id
        ):
            self._logger.warning(
                "Skipping update ai reviewer update since review id does not match",
                extra={"review": review.model_dump(), "review_id": review_id},
            )
            return

        if review.task_uid:
            task_tuple = (review.task_id, review.task_uid)
        else:
            task_tuple = await self._storage.get_task_tuple(review.task_id)

        run = await self._task_run_for_review(
            task_tuple,
            review.task_schema_id,
            review.task_input_hash,
            review.task_output_hash,
        )
        if not run:
            raise InternalError("No task run found for review", extras={"review": review.model_dump()})

        # We need to update or setup the evaluations
        if not review.comment:
            await self._handle_no_comment_review(review, run)
        else:
            await self._handle_commented_review(review, run)

    async def _trigger_ai_reviews(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hashes: set[str],
        input_evaluation_id: str | None,
        evaluator_id: str | None,
    ):
        # We want to skip runs that already have a user review
        # Since there is no point in computing an AI review for them
        omit_eval_hashes = await self._storage.reviews.eval_hashes_with_user_reviews(
            task_id[0],
            task_schema_id,
            task_input_hashes,
        )

        run_query = SerializableTaskRunQuery(
            task_id=task_id[0],
            task_schema_id=task_schema_id,
            task_input_hashes=task_input_hashes,
            unique_by={"task_input_hash", "task_output_hash"},
            include_fields={
                "_id",
                "task_input_hash",
                "task_output_hash",
                "status",
                "group.iteration",
                "version_id",
                "eval_hash",
            },
        )

        async for run in self._storage.task_runs.fetch_task_run_resources(task_id[1], run_query):
            if run.eval_hash in omit_eval_hashes:
                continue
            self._event_router(
                TriggerRunEvaluationEvent(
                    task_id=task_id[0],
                    task_schema_id=task_schema_id,
                    task_input_hash=run.task_input_hash,
                    task_output_hash=run.task_output_hash,
                    input_evaluation_id=input_evaluation_id,
                    evaluator_id=evaluator_id,
                    run_id=run.id,
                    iteration=run.group.iteration,
                    version_id=run.group.id,
                    run_failed=run.status == "failure",
                ),
            )

    async def _trigger_reviews_for_evaluator_updates(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        evaluator_data: TaskEvaluator,
    ):
        # Then we have to trigger a new evaluation for all existing input data
        input_evaluations_by_hash: dict[str, InputEvaluation] = {}
        async for input_evaluation in self._storage.input_evaluations.list_input_evaluations_unique_by_hash(
            task_id[0],
            task_schema_id,
        ):
            input_evaluations_by_hash[input_evaluation.task_input_hash] = input_evaluation

        await self._trigger_ai_reviews(
            task_id,
            task_schema_id,
            set(input_evaluations_by_hash.keys()),
            input_evaluation_id=None,
            evaluator_id=evaluator_data.id,
        )

    async def trigger_reviews_for_ai_reviewer_updates(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str | None,
        evaluator_id: str | None,
        input_evaluation_id: str | None,
        evaluator_did_change: bool,
    ):
        latest_evaluator_data = await self.get_latest_ai_evaluator(task_id, task_schema_id)
        # We only check the fact that the evaluator id is the latest if it indeed changed
        # Otherwise the evaluator id might be the ID of a record that was deleted
        if evaluator_did_change and (not latest_evaluator_data or latest_evaluator_data.id != evaluator_id):
            self._logger.info(
                "Skipping review since evaluator id does not match",
                extra={
                    "latest_evaluator_data": latest_evaluator_data.model_dump() if latest_evaluator_data else None,
                    "evaluator_id": evaluator_id,
                },
            )
            return

        if not latest_evaluator_data:
            latest_evaluator_data = self._empty_ai_evaluator()
        elif latest_evaluator_data.is_loading:
            self._logger.info("Skipping review since evaluator is loading")
            return

        task_tuple = await self._storage.get_task_tuple(task_id)

        if input_evaluation_id and task_input_hash:
            await self._trigger_ai_reviews(
                task_tuple,
                task_schema_id,
                {task_input_hash},
                input_evaluation_id=input_evaluation_id,
                evaluator_id=latest_evaluator_data.id,
            )
            return

        if not evaluator_id:
            raise InternalError(
                "Either evaluator id or input evaluation id and task input hash must be provided",
                extras={
                    "task_id": task_id,
                    "task_schema_id": task_schema_id,
                },
            )

        await self._trigger_reviews_for_evaluator_updates(task_tuple, task_schema_id, latest_evaluator_data)

    async def mark_benchmark_as_building_evaluator(self, task_id: str, task_schema_id: int, is_building: bool):
        await self._storage.review_benchmarks.mark_as_loading_new_ai_reviewer(task_id, task_schema_id, is_building)

    async def add_versions_to_review_benchmark(self, task_id: str, task_schema_id: int, versions: list[int]):
        version_query = TaskGroupQuery(task_id=task_id, task_schema_id=task_schema_id, iterations=set(versions))
        fetched_versions = [
            (v.iteration, v.properties)
            async for v in self._storage.task_groups.list_task_groups(
                version_query,
                include={"properties.model", "properties.provider", "properties.temperature", "iteration"},
            )
        ]

        benchmark = await self._storage.review_benchmarks.add_versions(task_id, task_schema_id, fetched_versions)

        # Schedule 1 run per version per input hash
        evaluated_hashes = await self._storage.input_evaluations.unique_input_hashes(
            task_id=task_id,
            task_schema_id=task_schema_id,
        )
        for task_input_hash in evaluated_hashes:
            for version in fetched_versions:
                self._event_router(
                    TriggerTaskRunEvent(
                        task_id=task_id,
                        task_schema_id=task_schema_id,
                        group_iteration=version[0],
                        task_input_hash=task_input_hash,
                        task_input=None,  # input will be fetched in the run job
                        trigger="review_benchmark",
                    ),
                )
        return benchmark

    async def remove_versions_from_review_benchmark(self, task_id: str, task_schema_id: int, versions: list[int]):
        return await self._storage.review_benchmarks.remove_versions(task_id, task_schema_id, versions)

    async def _find_versions_to_aggregate(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        iterations: set[int] | None,
        input_hashes: tuple[str, str] | None,
    ) -> dict[str, int] | None:
        """Returns a dict version id -> iteration for versions to aggregate when benchmarking"""
        # Fetch the benchmarked iterations
        benchmark_iterations = await self._storage.review_benchmarks.get_benchmark_versions(task_id[0], task_schema_id)
        if not benchmark_iterations:
            return None

        # Only need to recompute for the intersection of the requested iterations and the benchmark iterations
        iterations = benchmark_iterations.intersection(iterations) if iterations else benchmark_iterations

        iter_id_map = await self._storage.task_groups.map_iterations(task_id[0], task_schema_id, iterations)

        if input_hashes:
            # If input hashes are provided, we limit the runs to the ones with the provided input hashes
            q = SerializableTaskRunQuery(
                task_id=task_id[0],
                task_schema_id=task_schema_id,
                task_input_hashes={input_hashes[0]},
                task_output_hash=input_hashes[1],
                unique_by={"version_id"},
                group_ids=set(iter_id_map.values()) if iter_id_map else None,
                include_fields={"version_id"},
            )
            filtered_ids = {
                run.group.id async for run in self._storage.task_runs.fetch_task_run_resources(task_id[1], q)
            }
            return {v: k for k, v in iter_id_map.items() if v in filtered_ids}

        return {v: k for k, v in iter_id_map.items()}

    # Returns True if a new review will be computed which means a benchmark event
    # will be triggered
    async def _review_cached_run(self, task_id: TaskTuple, task_schema_id: int, run_id: str):
        # Fix for backwards compatibility
        # Cached runs that did not have a review will never get one so we manually add it

        run = await self._storage.task_runs.fetch_task_run_resource(
            task_id,
            run_id,
            include={
                "task_input_hash",
                "task_output_hash",
                "status",
                "group.iteration",
                "version_id",
            },
        )
        review = await self._reviews_storage.get_review_by_hash(
            task_id[0],
            task_schema_id,
            run.task_input_hash,
            run.task_output_hash,
        )
        if review:
            # Not need to do anything, the run already has a review
            return False

        # Otherwise we trigger an evaluation, no need to send an event inline
        # since the benchmark will be recomputed right after
        await self.evaluate_runs_by_hash_if_needed(
            task_id=task_id[0],
            task_schema_id=task_schema_id,
            task_input_hash=run.task_input_hash,
            task_output_hash=run.task_output_hash,
            run_id=run_id,
            iteration=run.group.iteration,
            run_failed=run.status == "failure",
            version_id=run.group.id,
        )
        return True

    async def recompute_review_benchmark(
        self,
        task_id: str,
        task_schema_id: int,
        iterations: set[int] | None = None,
        run_id: str | None = None,
        cached_run_id: str | None = None,
        input_hashes: tuple[str, str] | None = None,
    ):
        """Recompute benchmark for a given task"""
        task_tuple = await self._storage.get_task_tuple(task_id)
        if run_id:
            if iterations and len(iterations) == 1:
                iteration = next(iter(iterations))
                await self._storage.review_benchmarks.complete_run(
                    task_id,
                    task_schema_id,
                    iteration,
                    run_id,
                )
            else:
                self._logger.error(
                    "Unexpected iteration count for recompute benchmark with run id",
                    extra={"iterations": iterations, "run_id": run_id},
                )
        if cached_run_id:
            # if we need to assign a new review, no need to continue
            # A benchmark will be computed later
            if await self._review_cached_run(
                task_tuple,
                task_schema_id,
                run_id=cached_run_id,
            ):
                return

        version_ids = await self._find_versions_to_aggregate(task_tuple, task_schema_id, iterations, input_hashes)
        if not version_ids:
            self._logger.info("Skipping recompute review benchmark since no iterations to aggregate")
            return

        hashes = await self._reviews_storage.find_unique_input_hashes(
            task_id=task_id,
            task_schema_id=task_schema_id,
        )  # We make sure we set an updated at to avoid race conditions
        now = datetime_factory()

        # For now, we aggregate using version ids but the benchmark still use iterations
        def _add_iteration(a: _RunReviewAggregate) -> RunReviewAggregateWithIteration:
            v = a["version_id"]
            return {
                # Not sure why pyright is not happy here
                **a,  # type: ignore
                "iteration": version_ids[v],
            }

        aggregates = [
            _add_iteration(a)
            async for a in self._aggregate_reviews(
                task_tuple,
                task_schema_id,
                set(hashes),
                set(version_ids.keys()) if version_ids else None,
            )
        ]
        await self._storage.review_benchmarks.update_benchmark(task_id, task_schema_id, aggregates, now)

    async def assign_review_to_runs(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        task_output_hash: str,
        reviewer_type: Literal["ai", "user"],
        # If review id is specified, we only assign the review if it is the latest review
        review_id: str | None,
    ):
        """React to a completed review, either from a user or the ai"""
        review = await self._get_latest_review(
            task_id,
            task_schema_id,
            task_input_hash,
            task_output_hash,
            reviewer_type,
        )
        if not review or (review_id and review.id != review_id):
            self._logger.warning(
                "Skipping assigning reviews since it is not the latest review",
                extra={"review": review.model_dump() if review else None, "review_id": review_id},
            )
            return
        outcome = review.outcome

        if not outcome:
            if reviewer_type == "ai" and review.status == "in_progress":
                outcome = "in_progress"
            else:
                self._logger.warning(
                    "Skipping assigning reviews since outcome is not set",
                    extra={"review": review.model_dump()},
                )
                return

        if not review.task_uid:
            task_tuple = await self._storage.get_task_tuple(task_id)
            review.task_uid = task_tuple[1]
        else:
            task_tuple = (review.task_id, review.task_uid)

        # If reviewer type is AI, we check if there is an existing user review
        if reviewer_type == "ai":
            if (
                await self._get_latest_review(
                    task_id,
                    task_schema_id,
                    task_input_hash,
                    task_output_hash,
                    "user",
                )
                is not None
            ):
                # No need to compute benchmark, the update is about an AI review
                # But there is a user review already
                self._logger.info(
                    "Skipping computing benchmark since there is a superseding user review",
                    extra={"review": review.model_dump()},
                )
                return

        self._event_router(
            RecomputeReviewBenchmarkEvent(
                task_id=task_id,
                task_schema_id=task_schema_id,
                input_hashes=(task_input_hash, task_output_hash),
            ),
        )

    async def trigger_runs_for_benchmark(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        is_first_review: bool,
        run_id: str | None,
    ):
        if not is_first_review:
            return

        # Schedule 1 run per version per input hash
        iterations = await self._storage.review_benchmarks.get_benchmark_versions(task_id, task_schema_id)
        if not iterations:
            return

        task_tuple = await self._storage.get_task_tuple(task_id)

        if run_id:
            run = await self._storage.task_runs.fetch_task_run_resource(
                task_tuple,
                run_id,
                include={"task_input", "task_input_hash"},
            )
            task_input = run.task_input
        else:
            task_input = None

        for iteration in iterations:
            self._event_router(
                TriggerTaskRunEvent(
                    task_id=task_id,
                    task_schema_id=task_schema_id,
                    group_iteration=iteration,
                    task_input_hash=task_input_hash,
                    task_input=task_input,
                    trigger="review_benchmark",
                ),
            )

    class ReviewedInput(NamedTuple):
        task_input_hash: str
        task_input: dict[str, Any]

        correct_outputs: list[AgentOutput]
        incorrect_outputs: list[AgentOutput]

        evaluation_instructions: str | None

        @classmethod
        def from_domain(cls, input_evaluation: InputEvaluation, task_input: dict[str, Any]):
            return cls(
                task_input_hash=input_evaluation.task_input_hash,
                # Taksk input will be set elsewhere
                task_input=task_input,
                correct_outputs=input_evaluation.correct_outputs,
                incorrect_outputs=input_evaluation.incorrect_outputs,
                evaluation_instructions=input_evaluation.evaluation_instruction,
            )

    async def list_reviewed_inputs(self, task_id: TaskTuple, task_schema_id: int) -> list[ReviewedInput]:
        input_evaluations = {
            e.task_input_hash: e
            async for e in self._storage.input_evaluations.list_input_evaluations_unique_by_hash(
                task_id[0],
                task_schema_id,
            )
        }
        if not input_evaluations:
            return []

        # Now we also need to fetch the runs to get the task input
        run_query = SerializableTaskRunQuery(
            task_id=task_id[0],
            task_schema_id=task_schema_id,
            task_input_hashes=set(input_evaluations.keys()),
            unique_by={"task_input_hash"},
            include_fields={"task_input", "task_input_hash"},
        )
        runs = [
            self.ReviewedInput.from_domain(input_evaluations[run.task_input_hash], run.task_input)
            async for run in self._storage.task_runs.fetch_task_run_resources(task_id[1], run_query)
        ]

        if len(runs) != len(input_evaluations):
            missing_hashes = set(input_evaluations.keys()) - set(run.task_input_hash for run in runs)
            self._logger.warning(
                "Runs and reviewed inputs do not match",
                extra={
                    "task_id": task_id,
                    "task_schema_id": task_schema_id,
                    "missing_hashes": missing_hashes,
                },
            )

        return runs

    async def update_task_evaluator(self, task_id: str, task_schema_id: int, instructions: str, user: UserIdentifier):
        async def _check_latest():
            # Check whether the latest ai evaluator has the same instructions to avoid unnecessary updates
            latest_evaluator = await self.get_latest_ai_evaluator(task_id, task_schema_id, active=True)
            if not latest_evaluator:
                return None
            if not isinstance(latest_evaluator.evaluator_type, EvalV2Evaluator):
                self._logger.error(
                    "Found non-evalv2 evaluator for task",
                    extra={"task_id": task_id, "task_schema_id": task_schema_id},
                )
                return None
            if latest_evaluator.evaluator_type.instructions == instructions:
                return latest_evaluator
            return None

        if evaluator := await _check_latest():
            return evaluator

        inserted_evaluator = await self._storage.evaluators.add_task_evaluator(
            task_id=task_id,
            task_schema_id=task_schema_id,
            task_evaluator=TaskEvaluator(
                id="",
                name=InputTaskEvaluator.name(),
                active=True,
                is_loading=False,
                triggers=set(),
                evaluator_type=EvalV2Evaluator(instructions=instructions, instructions_updated_by=user),
            ),
        )
        await self._storage.evaluators.deactivate_evaluators(
            task_id,
            task_schema_id,
            except_id=inserted_evaluator.id,
            types={"evalv2"},
        )
        self._event_router(
            AIReviewerUpdatedEvent(
                task_id=task_id,
                task_schema_id=task_schema_id,
                evaluator_id=inserted_evaluator.id,
                evaluator_did_change=True,
            ),
        )
        return inserted_evaluator

    async def _add_input_to_evaluation(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        input_evaluation: InputEvaluation,
    ):
        run = await self._task_run_for_review(
            task_id,
            task_schema_id,
            input_evaluation.task_input_hash,
            task_output_hash=None,
            include_fields={"task_input"},
        )
        if not run:
            self._logger.warning(
                "No run found for input evaluation update",
                extra={
                    "task_id": task_id,
                    "task_schema_id": task_schema_id,
                    "task_input_hash": input_evaluation.task_input_hash,
                },
            )
            return self.ReviewedInput.from_domain(input_evaluation, {})

        return self.ReviewedInput.from_domain(input_evaluation, run.task_input)

    class OutputListUpdate(NamedTuple):
        add: AgentOutput | None
        remove: AgentOutput | None

    async def update_input_evaluation(
        self,
        task_id: str,
        task_schema_id: int,
        task_input_hash: str,
        instructions: str | None,
        correct_outputs: OutputListUpdate,
        incorrect_outputs: OutputListUpdate,
        user: UserIdentifier,
    ) -> ReviewedInput:
        task_tuple = await self._storage.get_task_tuple(task_id)
        latest_input_evaluation = await self._storage.input_evaluations.get_latest_input_evaluation(
            task_id=task_id,
            task_schema_id=task_schema_id,
            input_hash=task_input_hash,
        )
        if not latest_input_evaluation:
            latest_input_evaluation = InputEvaluation(
                id="",
                task_input_hash=task_input_hash,
                correct_outputs=[],
                incorrect_outputs=[],
                evaluation_instruction=None,
            )

        cop = latest_input_evaluation.model_copy(deep=True)
        if instructions is not None:
            cop.evaluation_instruction = instructions

        def _update_outputs(
            update: "ReviewsService.OutputListUpdate",
            list: list[AgentOutput],
            other: list[AgentOutput],
        ):
            if update.add:
                if update.add not in list:
                    list.append(update.add)
                if update.add in other:
                    other.remove(update.add)
            if update.remove:
                if update.remove in list:
                    list.remove(update.remove)

        _update_outputs(correct_outputs, cop.correct_outputs, cop.incorrect_outputs)
        _update_outputs(incorrect_outputs, cop.incorrect_outputs, cop.correct_outputs)

        if cop == latest_input_evaluation:
            return await self._add_input_to_evaluation(task_tuple, task_schema_id, latest_input_evaluation)

        cop.created_by = user
        # no need to change the created at since it is generated from the ID
        cop.id = ""

        created_input_evaluation = await self._storage.input_evaluations.create_input_evaluation(
            task_id=task_id,
            task_schema_id=task_schema_id,
            input_evaluation=cop,
        )
        self._event_router(
            AIReviewerUpdatedEvent(
                task_id=task_id,
                task_schema_id=task_schema_id,
                input_evaluation_id=created_input_evaluation.id,
                evaluator_did_change=False,
                task_input_hash=task_input_hash,
                evaluator_id=None,
            ),
        )

        return await self._add_input_to_evaluation(task_tuple, task_schema_id, created_input_evaluation)

    # TODO: test, right now only tested throw
    def _merge_aggregate(  # noqa: C901
        self,
        version_id: str,
        agg: RunAggregate,
        reviews_by_eval_hash: dict[str, Review],
    ):
        in_progress_review_count = 0
        positive_review_count = 0
        positive_user_review_count = 0
        negative_review_count = 0
        negative_user_review_count = 0
        unsure_review_count = 0
        for eval_hash in agg["eval_hashes"]:
            review = reviews_by_eval_hash.get(eval_hash)
            if not review:
                continue
            match review.status:
                case "in_progress":
                    in_progress_review_count += 1
                    continue
                case "completed":
                    pass
            match review.outcome:
                case "negative":
                    negative_review_count += 1
                    if review.reviewer.reviewer_type == "user":
                        negative_user_review_count += 1
                case "positive":
                    positive_review_count += 1
                    if review.reviewer.reviewer_type == "user":
                        positive_user_review_count += 1
                case "unsure":
                    unsure_review_count += 1
                case None:
                    self._logger.warning("Review has no outcome", extra={"review": safe_dump_pydantic_model(review)})

        return _RunReviewAggregate(
            version_id=version_id,
            in_progress_review_count=in_progress_review_count,
            positive_review_count=positive_review_count,
            positive_user_review_count=positive_user_review_count,
            negative_review_count=negative_review_count,
            negative_user_review_count=negative_user_review_count,
            unsure_review_count=unsure_review_count,
            average_cost_usd=agg.get("average_cost_usd"),
            average_duration_seconds=agg.get("average_duration_seconds"),
            total_run_count=agg["total_run_count"],
            failed_run_count=agg.get("failed_run_count"),
        )

    async def _aggregate_reviews(
        self,
        task_id: TaskTuple,
        task_schema_id: int,
        task_input_hashes: set[str],
        group_ids: set[str] | None,
    ):
        run_aggs = await self._storage.task_runs.aggregate_runs(
            task_id,
            task_schema_id,
            task_input_hashes,
            group_ids,
        )
        eval_hashes: set[str] = set()
        for r in run_aggs.values():
            eval_hashes.update(r["eval_hashes"])

        reviews_by_eval_hash: dict[str, Review] = {}
        async for review in self._storage.reviews.reviews_for_eval_hashes(task_id[0], eval_hashes):
            # Supposedly the first review should be the good one
            # But just in case, we only override the review for a given hash if it is a user review
            if review.eval_hash not in reviews_by_eval_hash or review.reviewer.reviewer_type == "user":
                reviews_by_eval_hash[review.eval_hash] = review

        for version_id, run_agg in run_aggs.items():
            yield self._merge_aggregate(version_id, run_agg, reviews_by_eval_hash)
