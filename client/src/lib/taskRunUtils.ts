import { LLMCompletionTypedMessages } from '@/types/workflowAI';

export type ContextWindowInformation = {
  inputTokens: string;
  outputTokens: string;
  percentage: string;
};

function formatTokenCount(count: number): string {
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}k`;
  }
  return count.toFixed(0).toString();
}

export function getContextWindowInformation(
  runCompletions: LLMCompletionTypedMessages[] | undefined
): ContextWindowInformation | undefined {
  if (!runCompletions) {
    return undefined;
  }

  // Find the completion with the highest context usage ratio
  let maxUsageCompletion: LLMCompletionTypedMessages | undefined;
  let maxUsageRatio = 0;

  for (const completion of runCompletions) {
    const { prompt_token_count, completion_token_count, model_context_window_size } = completion.usage;

    if (!!prompt_token_count && !!completion_token_count && !!model_context_window_size) {
      const totalTokens = prompt_token_count + completion_token_count;
      const usageRatio = totalTokens / model_context_window_size;

      if (usageRatio > maxUsageRatio) {
        maxUsageRatio = usageRatio;
        maxUsageCompletion = completion;
      }
    }
  }

  if (!maxUsageCompletion) {
    return undefined;
  }

  const usage = maxUsageCompletion.usage;

  if (!usage.prompt_token_count || !usage.completion_token_count || !usage.model_context_window_size) {
    return undefined;
  }

  const percentage = (usage.prompt_token_count + usage.completion_token_count) / usage.model_context_window_size;

  return {
    inputTokens: formatTokenCount(usage.prompt_token_count),
    outputTokens: formatTokenCount(usage.completion_token_count),
    percentage: `${Math.round(percentage * 100)}%`,
  };
}
