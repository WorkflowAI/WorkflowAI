import { renderHook } from '@testing-library/react';
import { TaskRun } from '@/types';
import { useMinimumLatencyTaskRun } from './useMinimumLatencyTaskRun';

describe('useMinimumLatencyTaskRun', () => {
  const MINIMUM_TASK_RUN = {
    duration_seconds: 2.01,
  } as TaskRun;
  const MAXIMUM_TASK_RUN = {
    duration_seconds: 10.009,
  } as TaskRun;

  it('is undefined when there are no task runs', () => {
    const { result } = renderHook(() => useMinimumLatencyTaskRun([undefined, undefined, undefined]));
    expect(result.current).toBeUndefined();
  });

  test('should return the minimum cost task run', () => {
    const { result } = renderHook(() => useMinimumLatencyTaskRun([MINIMUM_TASK_RUN, MAXIMUM_TASK_RUN, undefined]));
    expect(result.current).toBe(MINIMUM_TASK_RUN);
  });
});
