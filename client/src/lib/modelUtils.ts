import { ModelResponse } from '@/types/workflowAI';

export function isModelSupportingResoning(model: ModelResponse) {
  return model?.reasoning !== undefined;
}
