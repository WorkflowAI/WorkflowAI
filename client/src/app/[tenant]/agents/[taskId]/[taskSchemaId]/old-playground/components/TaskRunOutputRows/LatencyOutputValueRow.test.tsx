import { render } from '@testing-library/react';
import { TaskRun } from '@/types';
import { ModelResponse } from '@/types/workflowAI';
import { LatencyOutputValueRow } from './LatencyOutputValueRow';

describe('LatencyOutputValueRow', () => {
  const MINIMUM_TASK_RUN = {
    duration_seconds: 5.001,
  } as TaskRun;
  const MAXIMUM_TASK_RUN = {
    duration_seconds: 10.009,
  } as TaskRun;
  const CURRENT_AI_MODEL = {
    name: 'gpt-4-turbo-2024-04-09',
  } as ModelResponse;
  const MINIMUM_COST_AI_MODEL = {
    name: 'llama3-70b-8192',
  } as ModelResponse;

  test('empty state', () => {
    const { getByTestId, queryAllByTestId } = render(
      <LatencyOutputValueRow
        taskRun={undefined}
        minimumLatencyTaskRun={undefined}
        currentAIModel={CURRENT_AI_MODEL}
        minimumCostAIModel={MINIMUM_COST_AI_MODEL}
      />
    );
    expect(getByTestId('label').textContent).toEqual('Latency');
    expect(getByTestId('value').textContent).toEqual('-');
    expect(queryAllByTestId('tooltip-trigger').length).toEqual(0);
  });

  test('no AI agent runs to compare itself to', () => {
    const { getByTestId, queryAllByTestId } = render(
      <LatencyOutputValueRow
        taskRun={MINIMUM_TASK_RUN}
        minimumLatencyTaskRun={undefined}
        currentAIModel={CURRENT_AI_MODEL}
        minimumCostAIModel={MINIMUM_COST_AI_MODEL}
      />
    );

    expect(getByTestId('label').textContent).toEqual('Latency');
    expect(getByTestId('value').textContent).toEqual('5.0s');
    expect(queryAllByTestId('tooltip-trigger').length).toEqual(0);
  });

  test('best value AI agent run', () => {
    const { getByTestId, queryAllByTestId } = render(
      <LatencyOutputValueRow
        taskRun={MINIMUM_TASK_RUN}
        minimumLatencyTaskRun={MINIMUM_TASK_RUN}
        currentAIModel={CURRENT_AI_MODEL}
        minimumCostAIModel={MINIMUM_COST_AI_MODEL}
      />
    );

    expect(getByTestId('label').textContent).toEqual('Latency');
    expect(getByTestId('value').textContent).toEqual('5.0s');
    expect(queryAllByTestId('tooltip-trigger').length).toEqual(0);
  });

  test('not the best value', () => {
    const { getByTestId } = render(
      <LatencyOutputValueRow
        taskRun={MAXIMUM_TASK_RUN}
        minimumLatencyTaskRun={MINIMUM_TASK_RUN}
        currentAIModel={CURRENT_AI_MODEL}
        minimumCostAIModel={MINIMUM_COST_AI_MODEL}
      />
    );

    expect(getByTestId('label').textContent).toEqual('Latency');
    expect(getByTestId('value').textContent).toEqual('10.0s');
    expect(getByTestId('tooltip-trigger').textContent).toEqual('2x');
  });
});
