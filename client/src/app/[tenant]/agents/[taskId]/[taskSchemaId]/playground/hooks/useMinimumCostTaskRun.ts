import { useMemo } from 'react';
import { RunV1 } from '@/types/workflowAI';

export function useMinimumCostTaskRun(taskRuns: (RunV1 | undefined)[]) {
  return useMemo<RunV1 | undefined>(() => {
    let result: RunV1 | undefined = undefined;
    for (const taskRun of taskRuns) {
      const value = taskRun?.cost_usd;
      const resultValue = result?.cost_usd;
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
