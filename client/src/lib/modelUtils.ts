import { ModelResponse } from '@/types/workflowAI';

export function isModelSupportingResoning(model: ModelResponse) {
  return model?.reasoning !== undefined;
}

export function embedReasoningInModelID(modelId: string, reasoning: string | null | undefined) {
  if (!reasoning) {
    return modelId;
  }

  return modelId + '-' + reasoning + '-reasoning';
}

export function extractReasoningFromModelID(modelId: string) {
  if (!modelId.endsWith('-reasoning')) {
    return [modelId, undefined];
  }

  const splits = modelId.split('-');
  return [splits.slice(0, splits.length - 2).join('-'), splits[splits.length - 2]];
}
