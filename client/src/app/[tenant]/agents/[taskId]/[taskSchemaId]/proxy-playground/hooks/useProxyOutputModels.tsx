import { useCallback, useEffect, useMemo } from 'react';
import { useCompatibleAIModels } from '@/lib/hooks/useCompatibleAIModels';
import { ModelOptional, TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { RunV1 } from '@/types/workflowAI';
import { PlaygroundModels } from '../../playground/hooks/utils';

export function useProxyOutputModels(
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  run1: RunV1 | undefined,
  run2: RunV1 | undefined,
  run3: RunV1 | undefined,
  model1: string | undefined,
  model2: string | undefined,
  model3: string | undefined,
  setModel1: (model: string | undefined) => void,
  setModel2: (model: string | undefined) => void,
  setModel3: (model: string | undefined) => void
) {
  const { compatibleModels, allModels, defaultModels } = useCompatibleAIModels({
    tenant,
    taskId,
    taskSchemaId,
  });

  const maxTokens = useMemo(() => {
    if (allModels.length === 0) {
      return undefined;
    }
    return allModels.reduce((max, model) => {
      return Math.max(max, model.metadata.context_window_tokens ?? 0);
    }, 0);
  }, [allModels]);

  const outputModels = useMemo(() => {
    return [
      model1 ?? defaultModels[0]?.id ?? undefined,
      model2 ?? defaultModels[1]?.id ?? undefined,
      model3 ?? defaultModels[2]?.id ?? undefined,
    ] as PlaygroundModels;
  }, [model1, model2, model3, defaultModels]);

  const setOutputModels = useCallback(
    (index: number, model: ModelOptional) => {
      switch (index) {
        case 0:
          setModel1(model ?? undefined);
          break;
        case 1:
          setModel2(model ?? undefined);
          break;
        case 2:
          setModel3(model ?? undefined);
          break;
      }
    },
    [setModel1, setModel2, setModel3]
  );

  useEffect(() => {
    if (!!run1?.version.properties.model) {
      setModel1(run1.version.properties.model);
    }
  }, [run1?.version.properties.model, setModel1]);

  useEffect(() => {
    if (!!run2?.version.properties.model) {
      setModel2(run2.version.properties.model);
    }
  }, [run2?.version.properties.model, setModel2]);

  useEffect(() => {
    if (!!run3?.version.properties.model) {
      setModel3(run3.version.properties.model);
    }
  }, [run3?.version.properties.model, setModel3]);

  return {
    outputModels,
    setOutputModels,
    compatibleModels: compatibleModels,
    allModels: allModels,
    maxTokens,
  };
}
