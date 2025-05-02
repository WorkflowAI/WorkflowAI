import { useMemo } from 'react';
import { TaskRun } from '@/types';

export function useMinimumCostTaskRun(taskRuns: (TaskRun | undefined)[]) {
  return useMemo<TaskRun | undefined>(() => {
    let result: TaskRun | undefined = undefined;
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
