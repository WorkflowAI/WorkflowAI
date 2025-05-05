import { useCallback } from 'react';
import { useTaskRuns } from '@/store';
import { TaskID, TenantID } from '@/types/aliases';

/**
 * Attempds several time to fetch the task run after a 404
 * Task runs are created asynchronously so we need to retry until we get a 200
 */
export function useFetchTaskRunUntilCreated(max_retries: number = 10, delay_ms: number = 500) {
  const fetchTaskRun = useTaskRuns((state) => state.fetchTaskRun);

  return useCallback(
    async (tenant: TenantID | undefined, taskId: TaskID, taskRunId: string) => {
      for (let i = 0; i < max_retries; i++) {
        const taskRun = await fetchTaskRun(tenant, taskId, taskRunId);
        if (taskRun !== undefined) {
          return taskRun;
        }
        // Exponential backoff, first one is 500ms, second one is 750ms, etc.
        const delay = 1 + (i / 2) * delay_ms;
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    },
    [fetchTaskRun, max_retries, delay_ms]
  );
}
