import { TaskRun, ToolCallPreview } from './task_run';
import {
  RunV1,
  ToolCall,
  ToolCallRequestWithID,
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

export function toolCallPreviewFromToolCallRequests(
  requests: ToolCallRequestWithID[] | undefined
): ToolCallPreview[] | undefined {
  if (!requests) return undefined;

  return requests.map((request) => {
    return {
      id: request.id ?? '',
      name: request.tool_name,
      input_preview: JSON.stringify(request.tool_input_dict),
      output_preview: undefined,
    };
  });
}

export function toolCallsFromRunV1(run: RunV1 | undefined): ToolCallPreview[] | undefined {
  if (!run || !run.tool_call_requests) return undefined;

  const result: ToolCallPreview[] = run.tool_call_requests.map((request) => {
    return {
      id: request.id,
      name: request.name,
      input_preview: JSON.stringify(request.input),
      output_preview: undefined,
    };
  });

  return result.length > 0 ? result : undefined;
}

export function toolCallsFromRun(run: TaskRun | undefined): ToolCallPreview[] | undefined {
  if (!run) return undefined;

  const result: ToolCallPreview[] = [];
  run.llm_completions?.forEach((llmCompletion) => {
    const toolCalls = llmCompletion.tool_calls;
    const toolCallPreviews = toolCallPreviewFromToolCallRequests(toolCalls ?? undefined);
    if (toolCallPreviews) {
      result.push(...toolCallPreviews);
    }
  });

  return result.length > 0 ? result : undefined;
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
