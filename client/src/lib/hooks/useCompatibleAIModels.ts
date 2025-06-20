import { useMemo } from 'react';
import { useOrFetchSchemaAIModels } from '@/store';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { ModelResponse } from '@/types/workflowAI';

type TModeAiModelsProps = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
};

export function filterSupportedModels(models: ModelResponse[]) {
  return models.filter((model) => !model.is_not_supported_reason);
}

export function filterDefaultModels(models: ModelResponse[]) {
  return models.filter((model) => model.is_default && !model.is_not_supported_reason);
}

export function useCompatibleAIModels(props: TModeAiModelsProps) {
  const { tenant, taskId, taskSchemaId } = props;

  const { models, isInitialized, isLoading } = useOrFetchSchemaAIModels({
    tenant,
    taskId,
    taskSchemaId,
  });

  const compatibleModels = useMemo(() => filterSupportedModels(models), [models]);
  const defaultModels = useMemo(() => filterDefaultModels(models), [models]);

  return {
    compatibleModels,
    defaultModels,
    isLoading,
    isInitialized,
    allModels: models,
  };
}
