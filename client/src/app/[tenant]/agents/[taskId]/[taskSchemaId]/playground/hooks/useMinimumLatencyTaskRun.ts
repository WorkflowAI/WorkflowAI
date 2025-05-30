import { useMemo } from 'react';
import { RunV1 } from '@/types/workflowAI';

export function useMinimumLatencyTaskRun(taskRuns: (RunV1 | undefined)[]) {
  return useMemo<RunV1 | undefined>(() => {
    let result: RunV1 | undefined = undefined;
    for (const taskRun of taskRuns) {
      const value = taskRun?.duration_seconds;
      const resultValue = result?.duration_seconds;
      if (typeof value !== 'number') {
        continue;
      }
      if (typeof resultValue !== 'number') {
        result = taskRun;
        continue;
      }
      if (value < resultValue) {
        result = taskRun;
      }
    }
    return result;
  }, [taskRuns]);
}
