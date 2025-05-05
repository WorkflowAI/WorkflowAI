import { render } from '@testing-library/react';
import { TaskRun } from '@/types';
import { ModelResponse } from '@/types/workflowAI';
import { PriceOutputValueRow } from './PriceOutputValueRow';

describe('PriceOutputValueRow', () => {
  const MINIMUM_TASK_RUN = {
    cost_usd: 0.00001,
  } as TaskRun;
  const MAXIMUM_TASK_RUN = {
    cost_usd: 0.0023,
  } as TaskRun;
  const CURRENT_AI_MODEL = {
    name: 'gpt-4-turbo-2024-04-09',
  } as ModelResponse;
  const MINIMUM_COST_AI_MODEL = {
    name: 'llama3-70b-8192',
  } as ModelResponse;

  test('empty state', () => {
    const { getByTestId, queryAllByTestId } = render(
      <PriceOutputValueRow
        taskRun={undefined}
        minimumCostTaskRun={undefined}
        currentAIModel={CURRENT_AI_MODEL}
        minimumCostAIModel={MINIMUM_COST_AI_MODEL}
      />
    );

    expect(getByTestId('label').textContent).toEqual('Price');
    expect(getByTestId('value').textContent).toEqual('-');
    expect(queryAllByTestId('tooltip-trigger').length).toEqual(0);
  });

  test('no AI agent runs to compare itself to', () => {
    const { getByTestId, queryAllByTestId } = render(
      <PriceOutputValueRow
        taskRun={MINIMUM_TASK_RUN}
        minimumCostTaskRun={undefined}
        currentAIModel={CURRENT_AI_MODEL}
        minimumCostAIModel={MINIMUM_COST_AI_MODEL}
      />
    );

    expect(getByTestId('label').textContent).toEqual('Price');
    expect(getByTestId('value').textContent).toEqual('$0.00001');
    expect(queryAllByTestId('tooltip-trigger').length).toEqual(0);
  });

  test('best value AI agent run', () => {
    const { getByTestId, queryAllByTestId } = render(
      <PriceOutputValueRow
        taskRun={MINIMUM_TASK_RUN}
        minimumCostTaskRun={MINIMUM_TASK_RUN}
        currentAIModel={CURRENT_AI_MODEL}
        minimumCostAIModel={MINIMUM_COST_AI_MODEL}
      />
    );

    expect(getByTestId('label').textContent).toEqual('Price');
    expect(getByTestId('value').textContent).toEqual('$0.00001');
    expect(queryAllByTestId('tooltip-trigger').length).toEqual(0);
  });

  test('not the best value', () => {
    const { getByTestId } = render(
      <PriceOutputValueRow
        taskRun={MAXIMUM_TASK_RUN}
        minimumCostTaskRun={MINIMUM_TASK_RUN}
        currentAIModel={CURRENT_AI_MODEL}
        minimumCostAIModel={MINIMUM_COST_AI_MODEL}
      />
    );

    expect(getByTestId('label').textContent).toEqual('Price');
    expect(getByTestId('value').textContent).toEqual('$0.0023');
    expect(getByTestId('tooltip-trigger').textContent).toEqual('230x');
  });
});
