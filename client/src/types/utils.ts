import { TaskRun, ToolCallPreview } from './task_run';
import {
  InternalReasoningStep,
  ReasoningStep,
  RunV1,
  ToolCall,
  ToolKind,
  api__routers__run__RunResponseStreamChunk__ToolCall,
  api__routers__run__RunResponse__ToolCall,
} from './workflowAI/models';

export type WithRequired<T, K extends keyof T> = T & Required<Pick<T, K>>;
export type WithPartial<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

// Branded aliases require an explicit type casting to be used. this is to avoid passing the wrong field by mistake

declare const __brand: unique symbol;
type Brand<B> = { [__brand]: B };
export type Branded<T, B> = T & Brand<B>;

export function isNullish(value: unknown): value is null | undefined {
  return value === null || value === undefined;
}

export function toolCallsFromStreamOrRun(
  toolCalls: Array<
    api__routers__run__RunResponseStreamChunk__ToolCall | api__routers__run__RunResponse__ToolCall
  > | null
): ToolCall[] | undefined {
  if (!toolCalls) return undefined;

  return toolCalls.map((toolCall) => {
    const result: ToolCall = {
      id: toolCall.id,
      name: toolCall.name,
      input_preview: toolCall.input_preview,
      output_preview: toolCall.output_preview,
      error: null,
    };

    if ('error' in toolCall) {
      result.error = toolCall.error;
    }

    return result;
  });
}

export function toolCallsFromRun(run: TaskRun | undefined): ToolCallPreview[] | undefined {
  if (!run) return undefined;

  const result: ToolCallPreview[] = [];
  run.llm_completions?.forEach((llmCompletion) => {
    llmCompletion.tool_calls?.forEach((toolCall) => {
      result.push({
        id: toolCall.id ?? '',
        name: toolCall.tool_name,
        input_preview: JSON.stringify(toolCall.tool_input_dict),
        output_preview: undefined,
      });
    });
  });

  return result.length > 0 ? result : undefined;
}

export function toolCallsFromRunV1(run: RunV1 | undefined): ToolCallPreview[] | undefined {
  if (!run) return undefined;

  const result: ToolCallPreview[] = [];

  run.tool_call_requests?.forEach((toolCall) => {
    result.push({
      id: toolCall.id ?? '',
      name: toolCall.name,
      input_preview: JSON.stringify(toolCall.input),
      output_preview: undefined,
    });
  });

  return result.length > 0 ? result : undefined;
}

// TODO: temporarily map the reasoning steps to the new format
// Will no longer be needed when we use the v1 endpoint to fetch runs by id
export function mapReasoningSteps(
  reasoningSteps: InternalReasoningStep[] | undefined | null
): ReasoningStep[] | undefined {
  return reasoningSteps?.map((step) => ({
    title: step.title ?? null,
    step: step.explaination ?? null,
    output: step.output ?? null,
  }));
}

export function displayToolName(toolName: ToolKind): string {
  switch (toolName) {
    case '@search-google':
      return 'Search';
    case '@perplexity-sonar':
      return 'Perplexity';
    case '@perplexity-sonar-reasoning':
      return 'Perplexity Reasoning';
    case '@perplexity-sonar-pro':
      return 'Perplexity Pro';
    case '@browser-text':
      return 'Browser';
    default:
      return toolName;
  }
}
