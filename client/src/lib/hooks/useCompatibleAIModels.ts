import { useMemo } from 'react';
import { useOrFetchAllAiModels } from '@/store';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { ModelResponse } from '@/types/workflowAI';

type TModeAiModelsProps = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID | undefined;
};

export function filterSupportedModels(models: ModelResponse[]) {
  return models.filter((model) => !model.is_not_supported_reason);
}

export function useCompatibleAIModels(props: TModeAiModelsProps) {
  const { tenant, taskId, taskSchemaId } = props;
  const { models, isInitialized, isLoading } = useOrFetchAllAiModels({
    tenant,
    taskId,
    taskSchemaId,
  });

  const compatibleModels = useMemo(() => filterSupportedModels(models), [models]);

  return {
    compatibleModels,
    isLoading,
    isInitialized,
    allModels: models,
  };
}
