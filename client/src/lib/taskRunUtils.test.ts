import { LLMCompletionTypedMessages } from '@/types/workflowAI';
import { getContextWindowInformation } from './taskRunUtils';

describe('getContextWindowInformation', () => {
  it('should return undefined when no completions are provided', () => {
    expect(getContextWindowInformation(undefined)).toBeUndefined();
    expect(getContextWindowInformation([])).toBeUndefined();
  });

  it('should return undefined when no completion has valid usage data', () => {
    const completions: LLMCompletionTypedMessages[] = [
      {
        messages: [],
        usage: {
          prompt_token_count: null,
          completion_token_count: 75,
          model_context_window_size: 4000,
        },
      },
      {
        messages: [],
        usage: {
          prompt_token_count: 1000,
          completion_token_count: null,
          model_context_window_size: 4000,
        },
      },
    ];

    expect(getContextWindowInformation(completions)).toBeUndefined();
  });

  it('should return context information from the completion with highest usage ratio', () => {
    const completions: LLMCompletionTypedMessages[] = [
      {
        messages: [],
        usage: {
          prompt_token_count: 1300,
          completion_token_count: 75,
          model_context_window_size: 4000,
        },
      },
      {
        messages: [],
        usage: {
          prompt_token_count: 7000,
          completion_token_count: 832,
          model_context_window_size: 8000,
        },
      },
      {
        messages: [],
        usage: {
          prompt_token_count: 500,
          completion_token_count: 100,
          model_context_window_size: 2000,
        },
      },
    ];

    const result = getContextWindowInformation(completions);

    // First completion: (1300 + 75) / 4000 = 0.34375
    // Second completion: (7000 + 832) / 8000 = 0.9790
    // Third completion: (500 + 100) / 2000 = 0.30
    // Second completion should be selected as it has the highest ratio (0.9790)

    expect(result).toEqual({
      inputTokens: '7.0k',
      outputTokens: '832',
      percentage: '98%',
    });
  });

  it('should format token counts correctly', () => {
    const completions: LLMCompletionTypedMessages[] = [
      {
        messages: [],
        usage: {
          prompt_token_count: 1234,
          completion_token_count: 567,
          model_context_window_size: 4000,
        },
      },
    ];

    const result = getContextWindowInformation(completions);

    expect(result).toEqual({
      inputTokens: '1.2k',
      outputTokens: '567',
      percentage: '45%',
    });
  });

  it('should handle single completion correctly', () => {
    const completions: LLMCompletionTypedMessages[] = [
      {
        messages: [],
        usage: {
          prompt_token_count: 1000,
          completion_token_count: 500,
          model_context_window_size: 4000,
        },
      },
    ];

    const result = getContextWindowInformation(completions);

    expect(result).toEqual({
      inputTokens: '1.0k',
      outputTokens: '500',
      percentage: '38%',
    });
  });

  it('should handle edge case where multiple completions have the same ratio', () => {
    const completions: LLMCompletionTypedMessages[] = [
      {
        messages: [],
        usage: {
          prompt_token_count: 1000,
          completion_token_count: 500,
          model_context_window_size: 3000,
        },
      },
      {
        messages: [],
        usage: {
          prompt_token_count: 2000,
          completion_token_count: 1000,
          model_context_window_size: 6000,
        },
      },
    ];

    const result = getContextWindowInformation(completions);

    // Both have ratio of 0.5, should return the first one found
    expect(result).toEqual({
      inputTokens: '1.0k',
      outputTokens: '500',
      percentage: '50%',
    });
  });

  it('should skip completions with missing required fields and find the one with highest ratio among valid ones', () => {
    const completions: LLMCompletionTypedMessages[] = [
      {
        messages: [],
        usage: {
          prompt_token_count: null, // invalid
          completion_token_count: 75,
          model_context_window_size: 4000,
        },
      },
      {
        messages: [],
        usage: {
          prompt_token_count: 1000,
          completion_token_count: 200,
          model_context_window_size: 4000,
        },
      },
      {
        messages: [],
        usage: {
          prompt_token_count: 2000,
          completion_token_count: 800,
          model_context_window_size: 4000,
        },
      },
    ];

    const result = getContextWindowInformation(completions);

    // First completion is invalid
    // Second completion: (1000 + 200) / 4000 = 0.30
    // Third completion: (2000 + 800) / 4000 = 0.70
    // Third completion should be selected

    expect(result).toEqual({
      inputTokens: '2.0k',
      outputTokens: '800',
      percentage: '70%',
    });
  });
});
