import { useCallback } from 'react';
import { useTaskRuns } from '@/store';
import { TaskID, TenantID } from '@/types/aliases';

/**
 * Attempds several time to fetch the task run after a 404
 * Task runs are created asynchronously so we need to retry until we get a 200
 */
export function useFetchTaskRunUntilCreated(max_retries: number = 10, delay_ms: number = 500) {
  const fetchRunV1 = useTaskRuns((state) => state.fetchRunV1);

  return useCallback(
    async (tenant: TenantID | undefined, taskId: TaskID, runId: string) => {
      for (let i = 0; i < max_retries; i++) {
        const runV1 = await fetchRunV1(tenant, taskId, runId);
        if (runV1 !== undefined) {
          return runV1;
        }
        // Exponential backoff, first one is 500ms, second one is 750ms, etc.
        const delay = 1 + (i / 2) * delay_ms;
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    },
    [fetchRunV1, max_retries, delay_ms]
  );
}
