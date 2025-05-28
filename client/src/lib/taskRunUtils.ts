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

  const usage = runCompletions.find(
    (completion) =>
      !!completion.usage.prompt_token_count &&
      !!completion.usage.completion_token_count &&
      !!completion.usage.model_context_window_size
  )?.usage;

  if (!usage || !usage.prompt_token_count || !usage.completion_token_count || !usage.model_context_window_size) {
    return undefined;
  }

  const percentage = (usage.prompt_token_count + usage.completion_token_count) / usage.model_context_window_size;

  return {
    inputTokens: formatTokenCount(usage.prompt_token_count),
    outputTokens: formatTokenCount(usage.completion_token_count),
    percentage: `${Math.round(percentage * 100)}%`,
  };
}
