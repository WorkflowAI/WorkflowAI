import { renderHook } from '@testing-library/react';
import { RunV1 } from '@/types/workflowAI';
import { useMinimumLatencyTaskRun } from './useMinimumLatencyTaskRun';

describe('useMinimumLatencyTaskRun', () => {
  const MINIMUM_TASK_RUN = {
    duration_seconds: 2.01,
  } as RunV1;
  const MAXIMUM_TASK_RUN = {
    duration_seconds: 10.009,
  } as RunV1;

  it('is undefined when there are no task runs', () => {
    const { result } = renderHook(() => useMinimumLatencyTaskRun([undefined, undefined, undefined]));
    expect(result.current).toBeUndefined();
  });

  test('should return the minimum cost task run', () => {
    const { result } = renderHook(() => useMinimumLatencyTaskRun([MINIMUM_TASK_RUN, MAXIMUM_TASK_RUN, undefined]));
    expect(result.current).toBe(MINIMUM_TASK_RUN);
  });
});
