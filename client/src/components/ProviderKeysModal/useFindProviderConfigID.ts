import { useMemo } from 'react';
import { useCompatibleAIModels } from '@/lib/hooks/useCompatibleAIModels';
import { TaskSchemaID, TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { Model, ProviderSettings } from '@/types/workflowAI';

type UseFindProviderConfigIDProps = {
  providerSettings: ProviderSettings[] | undefined;
  model: Model | string | undefined;
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
};

// TODO: remove, likely unused
export function useFindProviderConfigID(props: UseFindProviderConfigIDProps) {
  const { providerSettings, model, tenant, taskId, taskSchemaId } = props;

  const { allModels } = useCompatibleAIModels({
    tenant,
    taskId,
    taskSchemaId,
  });

  const providerConfigID = useMemo(() => {
    const identifiedModel = allModels.find((candidate) => candidate.id === model);
    const provider = identifiedModel?.providers[0];
    return providerSettings?.find((v) => v.provider === provider)?.id;
  }, [allModels, model, providerSettings]);

  return { providerConfigID };
}
