import { enableMapSet, produce } from 'immer';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { TaskID, TenantID } from '@/types/aliases';
import { CreateReviewRequest, Page_Review_, Review } from '@/types/workflowAI';
import { taskSubPath } from './utils';

enableMapSet();

interface TaskRunReviewsState {
  reviewsById: Map<string, Array<Review>>;
  isInitializedById: Map<string, boolean>;
  isLoadingById: Map<string, boolean>;
  pollingIntervalsById: Map<string, NodeJS.Timeout>;

  respondToReview(
    tenant: TenantID | undefined,
    taskId: TaskID,
    runId: string,
    reviewId: string,
    comment: string
  ): Promise<void>;

  createReview(
    tenant: TenantID | undefined,
    taskId: TaskID,
    runId: string,
    outcome: 'positive' | 'negative'
  ): Promise<void>;

  fetchTaskRunReviews(tenant: TenantID | undefined, taskId: TaskID, runId: string): Promise<void>;
}

export const useTaskRunReviews = create<TaskRunReviewsState>((set, get) => ({
  reviewsById: new Map<string, Array<Review>>(),
  isInitializedById: new Map<string, boolean>(),
  isLoadingById: new Map<string, boolean>(),
  pollingIntervalsById: new Map<string, NodeJS.Timeout>(),

  respondToReview: async (tenant, taskId, runId, reviewId, comment) => {
    await client.post(taskSubPath(tenant, taskId, `/runs/${runId}/reviews/${reviewId}/respond`), {
      body: JSON.stringify({ comment }),
    });
  },

  createReview: async (tenant, taskId, runId, outcome) => {
    const review = await client.post<CreateReviewRequest, Review>(
      taskSubPath(tenant, taskId, `/runs/${runId}/reviews`),
      {
        outcome,
      }
    );

    set(
      produce((state) => {
        const existingReviews = state.reviewsById.get(runId) || [];
        state.reviewsById.set(runId, [review, ...existingReviews]);
      })
    );
  },

  fetchTaskRunReviews: async (tenant: TenantID | undefined, taskId: TaskID, runId: string) => {
    if (get().isLoadingById.get(runId)) {
      return;
    }

    set(
      produce((state: TaskRunReviewsState) => {
        state.isLoadingById.set(runId, true);
      })
    );

    const response = await client.get<Page_Review_>(taskSubPath(tenant, taskId, `/runs/${runId}/reviews`));

    const reviews = response.items;

    set(
      produce((state: TaskRunReviewsState) => {
        state.reviewsById.set(runId, reviews);
      })
    );

    set(
      produce((state: TaskRunReviewsState) => {
        state.isLoadingById.set(runId, false);
        state.isInitializedById.set(runId, true);
      })
    );
  },
}));
