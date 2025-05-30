import { useMemo } from 'react';
import { SideBySideEntry, useSideBySideStore } from '@/store/side_by_side';
import { useTaskRunReviews } from '@/store/task_run_reviews';
import { useTaskRuns } from '@/store/task_runs';
import { buildScopeKey } from '@/store/utils';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { Review, RunV1 } from '@/types/workflowAI';

function getReviewsForEntries(state: { reviewsById: Map<string, Review[]> }, entries: SideBySideEntry[] | undefined) {
  if (!entries) {
    return undefined;
  }

  const reviews: Review[][] = [];
  for (const entry of entries) {
    const runReviews = state.reviewsById.get(entry.runId);
    if (runReviews) {
      reviews.push(runReviews);
    }
  }
  return reviews;
}

function valueForReviews(reviews: Review[]): 'positive' | 'negative' | 'unsure' | undefined {
  if (reviews.length === 0) {
    return undefined;
  }

  const userReview = reviews.filter((review) => review.created_by.reviewer_type === 'user')[0];

  if (!!userReview && userReview.outcome !== null) {
    return userReview.outcome;
  }

  const aiReview = reviews.filter((review) => review.created_by.reviewer_type === 'ai')[0];

  if (!!aiReview && aiReview.outcome !== null) {
    return aiReview.outcome;
  }

  return undefined;
}

function findEntries(
  runs: Set<SideBySideEntry> | undefined,
  inputHashes: string[] | undefined,
  versionId: string | undefined,
  modelId: string | undefined
) {
  if (!runs || !inputHashes) {
    return undefined;
  }

  if (!versionId && !modelId) {
    return undefined;
  }

  return Array.from(runs).filter(
    (entry) =>
      inputHashes.includes(entry.inputHash) &&
      ((entry.versionId === versionId && !!versionId) || (entry.modelId === modelId && !!modelId))
  );
}

function accuracyForReviews(reviews: Review[][] | undefined): number | undefined {
  if (!reviews) {
    return undefined;
  }

  let positiveCount = 0;
  let negativeCount = 0;
  let unsureCount = 0;

  for (const subreviews of reviews) {
    const value = valueForReviews(subreviews);
    switch (value) {
      case 'positive':
        positiveCount++;
        break;
      case 'negative':
        negativeCount++;
        break;
      case 'unsure':
        unsureCount++;
    }
  }

  const totalCount = positiveCount + negativeCount + unsureCount;
  if (totalCount === 0) {
    return undefined;
  }

  return positiveCount / totalCount;
}

function getMinimalValue(leftValue: number | undefined, rightValue: number | undefined): number | undefined {
  if (leftValue === undefined && rightValue === undefined) {
    return undefined;
  }
  if (leftValue === undefined) {
    return rightValue;
  }
  if (rightValue === undefined) {
    return leftValue;
  }
  return Math.min(leftValue, rightValue);
}

function getMaximalValue(leftValue: number | undefined, rightValue: number | undefined): number | undefined {
  if (leftValue === undefined && rightValue === undefined) {
    return undefined;
  }
  if (leftValue === undefined) {
    return rightValue;
  }
  if (rightValue === undefined) {
    return leftValue;
  }
  return Math.max(leftValue, rightValue);
}

function calculateAverage<T extends 'cost_usd' | 'duration_seconds'>(
  runs: RunV1[] | undefined,
  property: T
): number | undefined {
  if (!runs) {
    return undefined;
  }

  const filteredRuns = runs.filter((run) => run[property] !== undefined && run[property] !== null);

  if (filteredRuns.length === 0) {
    return undefined;
  }

  const sum = filteredRuns.reduce((acc, run) => acc + (run[property] ?? 0), 0);
  return sum / filteredRuns.length;
}

function getRunsForEntries(
  state: { runV1ById: Map<string, RunV1> },
  entries: SideBySideEntry[] | undefined
): RunV1[] | undefined {
  if (!entries) {
    return undefined;
  }

  const runs: RunV1[] = [];
  for (const entry of entries) {
    const run = state.runV1ById.get(entry.runId);
    if (run) {
      runs.push(run);
    }
  }
  return runs;
}

export type SideBySideStats = {
  accuracy: number | undefined;
  bestAccuracy: number | undefined;
  worstAccuracy: number | undefined;

  averageCost: number | undefined;
  minimalCost: number | undefined;

  averageDuration: number | undefined;
  minimalDuration: number | undefined;
};

export function useSideBySideStatsEffect(
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  inputHashes: string[] | undefined,
  leftVersionId: string | undefined,
  rightVersionId: string | undefined,
  rightModelId: string | undefined
): { left: SideBySideStats; right: SideBySideStats } {
  const scopeKey = buildScopeKey({
    tenant,
    taskId,
    taskSchemaId,
  });

  const runs = useSideBySideStore((state) => state.runs.get(scopeKey));
  // const { models } = useOrFetchAllAiModels({ tenant, taskId, taskSchemaId });

  const leftEntries = useMemo(
    () => findEntries(runs, inputHashes, leftVersionId, undefined),
    [runs, inputHashes, leftVersionId]
  );

  const rightEntries = useMemo(
    () => findEntries(runs, inputHashes, rightVersionId, rightModelId),
    [runs, inputHashes, rightVersionId, rightModelId]
  );

  const leftRuns: RunV1[] | undefined = useTaskRuns((state) => getRunsForEntries(state, leftEntries));

  const rightRuns: RunV1[] | undefined = useTaskRuns((state) => getRunsForEntries(state, rightEntries));

  const leftAverageCost = useMemo(() => {
    return calculateAverage(leftRuns, 'cost_usd');
  }, [leftRuns]);

  const rightAverageCost = useMemo(() => {
    return calculateAverage(rightRuns, 'cost_usd');
  }, [rightRuns]);

  const leftAverageDuration = useMemo(() => {
    return calculateAverage(leftRuns, 'duration_seconds');
  }, [leftRuns]);

  const rightAverageDuration = useMemo(() => {
    return calculateAverage(rightRuns, 'duration_seconds');
  }, [rightRuns]);

  const leftReviews = useTaskRunReviews((state) => getReviewsForEntries(state, leftEntries));
  const rightReviews = useTaskRunReviews((state) => getReviewsForEntries(state, rightEntries));

  const leftAccuracy = useMemo(() => {
    return accuracyForReviews(leftReviews);
  }, [leftReviews]);

  const rightAccuracy = useMemo(() => {
    return accuracyForReviews(rightReviews);
  }, [rightReviews]);

  const minimalDuration = useMemo(() => {
    return getMinimalValue(leftAverageDuration, rightAverageDuration);
  }, [leftAverageDuration, rightAverageDuration]);

  const minimalCost = useMemo(() => {
    return getMinimalValue(leftAverageCost, rightAverageCost);
  }, [leftAverageCost, rightAverageCost]);

  const bestAccuracy = useMemo(() => {
    return getMaximalValue(leftAccuracy, rightAccuracy);
  }, [leftAccuracy, rightAccuracy]);

  const worstAccuracy = useMemo(() => {
    return getMinimalValue(leftAccuracy, rightAccuracy);
  }, [leftAccuracy, rightAccuracy]);

  return {
    left: {
      accuracy: leftAccuracy,
      bestAccuracy,
      worstAccuracy,
      averageCost: leftAverageCost,
      minimalCost,
      averageDuration: leftAverageDuration,
      minimalDuration,
    },
    right: {
      accuracy: rightAccuracy,
      bestAccuracy,
      worstAccuracy,
      averageCost: rightAverageCost,
      minimalCost,
      averageDuration: rightAverageDuration,
      minimalDuration,
    },
  };
}
