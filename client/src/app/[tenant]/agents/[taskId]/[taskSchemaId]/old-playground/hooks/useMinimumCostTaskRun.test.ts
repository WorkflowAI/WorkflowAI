import { renderHook } from '@testing-library/react';
import { TaskRun } from '@/types';
import { useMinimumCostTaskRun } from './useMinimumCostTaskRun';

describe('useMinimumCostTaskRun', () => {
  const MINIMUM_TASK_RUN = {
    cost_usd: 0.00023,
  } as TaskRun;
  const MAXIMUM_TASK_RUN = {
    cost_usd: 0.022,
  } as TaskRun;

  it('is undefined when there are no task runs', () => {
    const { result } = renderHook(() => useMinimumCostTaskRun([undefined, undefined, undefined]));
    expect(result.current).toBeUndefined();
  });

  test('should return the minimum cost task run', () => {
    const { result } = renderHook(() => useMinimumCostTaskRun([MINIMUM_TASK_RUN, MAXIMUM_TASK_RUN, undefined]));
    expect(result.current).toBe(MINIMUM_TASK_RUN);
  });
});
