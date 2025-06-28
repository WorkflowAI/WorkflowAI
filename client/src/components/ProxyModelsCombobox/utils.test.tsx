import { ModelResponse } from '@/types/workflowAI';
import { pricingBetweenModelsComparator } from './utils';

describe('comparePricingBetweenModels', () => {
  it('should sort models with pricing first', () => {
    const models = [
      {
        id: '3',
        average_cost_per_run_usd: null,
        metadata: {
          price_per_input_token_usd: 1,
          price_per_output_token_usd: 1,
        },
      },
      { id: '1', average_cost_per_run_usd: 1 },
      {
        id: '4',
        average_cost_per_run_usd: undefined,
        metadata: {
          price_per_input_token_usd: 1,
          price_per_output_token_usd: 2,
        },
      },
      // Will be first since it has pricing and is more expensive
      { id: '2', average_cost_per_run_usd: 2 },
    ] as ModelResponse[];

    const sorted = models
      .map((model) => ({ model }))
      .sort(pricingBetweenModelsComparator(true))
      .map((m) => m.model.id);

    expect(sorted).toEqual(['2', '1', '4', '3']);

    const sorted2 = models
      .map((model) => ({ model }))
      .sort(pricingBetweenModelsComparator(false))
      .map((m) => m.model.id);

    expect(sorted2).toEqual(['1', '2', '3', '4']);
  });
});
