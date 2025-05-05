import { useMemo } from 'react';
import { TaskRun } from '@/types';

export function useMinimumLatencyTaskRun(taskRuns: (TaskRun | undefined)[]) {
  return useMemo<TaskRun | undefined>(() => {
    let result: TaskRun | undefined = undefined;
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
