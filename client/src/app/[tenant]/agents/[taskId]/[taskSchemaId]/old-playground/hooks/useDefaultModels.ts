import { useMemo } from 'react';
import { ModelResponse } from '@/types/workflowAI';
import { PlaygroundModels } from './utils';

export function useDefaultModels(models: ModelResponse[]) {
  return useMemo(() => {
    const defaultModels: string[] = [];
    for (const model of models) {
      if (model.is_default && !model.is_not_supported_reason) {
        defaultModels.push(model.id);
        if (defaultModels.length === 3) {
          break;
        }
      }
    }
    return defaultModels as PlaygroundModels;
  }, [models]);
}
