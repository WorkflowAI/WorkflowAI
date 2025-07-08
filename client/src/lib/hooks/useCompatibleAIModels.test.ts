import { ModelResponse } from '@/types/workflowAI';
import { filterSupportedModels } from './useCompatibleAIModels';

const MODEL = { name: 'Model 1', modes: [], icon_url: 'icon_url' };

describe('filterSupportedModels', () => {
  it('filters out models that are not supported', () => {
    const models: ModelResponse[] = [
      {
        ...MODEL,
        id: '1',
        is_not_supported_reason: 'reason',
        average_cost_per_run_usd: 0.1,
        providers: ['fireworks'],
        is_latest: true,
        metadata: {
          quality_index: 100,
          price_per_input_token_usd: 100,
          price_per_output_token_usd: 100,
          release_date: '2024-04-09',
          context_window_tokens: 1000000,
          provider_name: 'some-new-unknown-provider',
        },
      },
      {
        ...MODEL,
        id: '2',
        is_not_supported_reason: null,
        average_cost_per_run_usd: 0.2,
        providers: ['fireworks'],
        is_latest: false,
        metadata: {
          quality_index: 100,
          price_per_input_token_usd: 100,
          price_per_output_token_usd: 100,
          release_date: '2024-04-09',
          context_window_tokens: 1000000,
          provider_name: 'some-new-unknown-provider',
        },
      },
      {
        ...MODEL,
        id: '3',
        is_not_supported_reason: null,
        average_cost_per_run_usd: 0.3,
        is_latest: true,
        providers: ['fireworks'],
        metadata: {
          quality_index: 100,
          price_per_input_token_usd: 100,
          price_per_output_token_usd: 100,
          release_date: '2024-04-09',
          context_window_tokens: 1000000,
          provider_name: 'some-new-unknown-provider',
        },
      },
    ];
    const result = filterSupportedModels(models);
    expect(result).toEqual([models[1], models[2]]);
  });
});
