'use client';

import { isEqual } from 'lodash';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useRedirectWithParams } from '@/lib/queryString';
import { SchemaNodeType } from '@/lib/schemaUtils';
import { useOrFetchTaskRun } from '@/store';
import { GeneralizedTaskInput, TaskRun } from '@/types';
import { Model, ModelOptional, TaskID, TenantID } from '@/types/aliases';
import { ModelResponse, VersionV1 } from '@/types/workflowAI';
import { useDefaultModels } from './useDefaultModels';
import { GeneratePlaygroundInputParams } from './usePlaygroundPersistedState';
import { PlaygroundModels } from './utils';

type PersistedTaskRunsWithSameModel = [TaskRun | null, TaskRun | null, TaskRun | null];

function isTaskRunOnSameModel(taskRun: TaskRun | undefined, taskModel: ModelOptional) {
  if (!taskRun || !taskModel) return false;
  const modelID = taskModel;
  const taskRunGroupProperties = taskRun.group?.properties;
  return modelID === taskRunGroupProperties?.model;
}

type Props = {
  aiModels: ModelResponse[];
  currentVersion: VersionV1 | undefined;
  generatedInput: GeneralizedTaskInput | undefined;
  versionId: string | undefined;
  handleGeneratePlaygroundInput: (params?: GeneratePlaygroundInputParams) => void;
  handleGenerateInstructions: () => void;
  resetStreamedChunk: (index: number) => void;
  onTaskRunIdUpdate: (index: number, runId: string | undefined) => void;
  latestTaskRun: TaskRun | undefined;
  schemaModels: PlaygroundModels;
  taskModels: PlaygroundModels;
  persistedTaskRunIds: (string | undefined)[];
  setGeneratedInput: (input: GeneralizedTaskInput) => void;
  setInstructions: (instructions: string) => void;
  setTemperature: (temperature: number) => void;
  setSchemaModels: (index: number, newModel: ModelOptional) => void;
  taskId: TaskID;
  versions: VersionV1[];
  taskRunId1: string | undefined;
  taskRunId2: string | undefined;
  taskRunId3: string | undefined;
  tenant: TenantID | undefined;
  voidInput: Record<string, unknown> | SchemaNodeType[] | undefined;
  persistedVersionId: string | undefined;
};

export function usePlaygroundEffects(props: Props) {
  const {
    aiModels,
    currentVersion,
    generatedInput,
    versionId,
    handleGeneratePlaygroundInput,
    handleGenerateInstructions,
    resetStreamedChunk,
    latestTaskRun,
    onTaskRunIdUpdate,
    schemaModels,
    taskModels,
    persistedTaskRunIds,
    setGeneratedInput,
    setInstructions,
    setSchemaModels,
    setTemperature,

    versions,
    taskId,
    taskRunId1,
    taskRunId2,
    taskRunId3,
    tenant,
    voidInput,
    persistedVersionId,
  } = props;

  const {
    taskRun: taskRun1,
    isInitialized: taskRun1Initialized,
    isLoading: taskRun1Loading,
  } = useOrFetchTaskRun(tenant, taskId, taskRunId1);

  const {
    taskRun: taskRun2,
    isInitialized: taskRun2Initialized,
    isLoading: taskRun2Loading,
  } = useOrFetchTaskRun(tenant, taskId, taskRunId2);
  const {
    taskRun: taskRun3,
    isInitialized: taskRun3Initialized,
    isLoading: taskRun3Loading,
  } = useOrFetchTaskRun(tenant, taskId, taskRunId3);
  const { taskRun: persistedTaskRun1, isInitialized: persistedTaskRun1Initialized } = useOrFetchTaskRun(
    tenant,
    taskId,
    persistedTaskRunIds[0]
  );
  const { taskRun: persistedTaskRun2, isInitialized: persistedTaskRun2Initialized } = useOrFetchTaskRun(
    tenant,
    taskId,
    persistedTaskRunIds[1]
  );
  const { taskRun: persistedTaskRun3, isInitialized: persistedTaskRun3Initialized } = useOrFetchTaskRun(
    tenant,
    taskId,
    persistedTaskRunIds[2]
  );
  const persistedTaskRunsInitialized = useMemo(() => {
    if (!!persistedTaskRunIds[0] && !persistedTaskRun1Initialized) return false;
    if (!!persistedTaskRunIds[1] && !persistedTaskRun2Initialized) return false;
    if (!!persistedTaskRunIds[2] && !persistedTaskRun3Initialized) return false;
    return true;
  }, [persistedTaskRun1Initialized, persistedTaskRun2Initialized, persistedTaskRun3Initialized, persistedTaskRunIds]);
  const persistedTaskRuns = useMemo(() => {
    return [persistedTaskRun1, persistedTaskRun2, persistedTaskRun3];
  }, [persistedTaskRun1, persistedTaskRun2, persistedTaskRun3]);

  const redirectWithParams = useRedirectWithParams();
  const hasVersions = versions.length > 0;

  const hasModelsBeenSet = useMemo(() => schemaModels.some((model) => !!model), [schemaModels]);

  const persistedTaskRunsWithSameModel = useMemo(() => {
    const result: PersistedTaskRunsWithSameModel = [null, null, null];
    taskModels.forEach((model, modelIndex) => {
      const taskRun = persistedTaskRuns[modelIndex];
      const isSameModel = isTaskRunOnSameModel(taskRun, model);
      if (!!taskRun && isSameModel) {
        result[modelIndex] = taskRun;
      }
    });
    return result;
  }, [persistedTaskRuns, taskModels]);

  const latestTaskRunOnSameModel = useMemo(
    () => persistedTaskRunsWithSameModel.find((tr) => !!tr),
    [persistedTaskRunsWithSameModel]
  );

  const hasGeneratedInputBeenInitialized = useRef<boolean>(false);
  const hasLaunchedSuggestedInstructions = useRef<boolean>(false);
  // If the playground was loaded with a version id, we don't want to update the version
  const isForcedVersion = useRef(!!versionId);

  useEffect(() => {
    // First of all, let's wait for all the data to be loaded
    if (!!taskRunId1 && !taskRun1Initialized) {
      return;
    }

    if (!persistedTaskRunsInitialized) {
      return;
    }
    // Also, we make sure that models have been properly set
    if (!hasModelsBeenSet) {
      return;
    }
    // If there is no task group id, we need to set one if possible
    if (!versionId) {
      // If there is a task run, we redirect to its task group
      if (!!taskRun1) {
        redirectWithParams({
          params: { versionId: taskRun1.group?.id },
          scroll: false,
        });
        return;
        // If the latest task run has the same input as the generated input, we redirect to its task group
      } else if (!!generatedInput) {
        if (!!latestTaskRun) {
          redirectWithParams({
            params: { versionId: latestTaskRun.group?.id },
            scroll: false,
          });
        }
        for (let i = 0; i < persistedTaskRunsWithSameModel.length; i++) {
          const taskRun = persistedTaskRunsWithSameModel[i];
          if (!!taskRun && isEqual(taskRun.task_input, generatedInput)) {
            // We only want to update the task run id if the latest task run is on the same model
            // Otherwise, we lose the persistence of the model
            onTaskRunIdUpdate(i, taskRun.id);
          }
        }
        return;
        // If there is no task run, but there are task groups, we redirect to the first task group
      } else if (!!persistedVersionId) {
        redirectWithParams({
          params: { versionId: persistedVersionId },
          scroll: false,
        });
        return;
      } else if (hasVersions) {
        redirectWithParams({
          params: { versionId: versions[0].id },
          scroll: false,
        });
        return;
      } else {
        if (hasLaunchedSuggestedInstructions.current) {
          return;
        }
        // At this point, we know that there is no task group
        // so let's create the instructions, generate the input and launch runs
        handleGenerateInstructions();
        hasLaunchedSuggestedInstructions.current = true;
        return;
      }
    }
    if (
      // If playground was loaded with a version id, we don't want to set other params
      isForcedVersion.current ||
      // If the generated input has been initialized, we are done here
      hasGeneratedInputBeenInitialized.current ||
      // If there is at least one version, we need to wait until it is initialized
      (hasVersions && !currentVersion) ||
      // If playground was loaded with a task run id, we don't want to set other params
      !!taskRunId1
    ) {
      return;
    }
    hasGeneratedInputBeenInitialized.current = true;
    if (!generatedInput) {
      if (!!latestTaskRunOnSameModel) {
        // We only want to update the task run id if the latest task run is on the same model
        // Otherwise, we lose the persistence of the model
        onTaskRunIdUpdate(0, latestTaskRunOnSameModel.id);
      } else if (!!latestTaskRun) {
        setGeneratedInput(latestTaskRun.task_input);
      } else if (!!voidInput) {
        setGeneratedInput(voidInput);
      }
    }
  }, [
    currentVersion,
    generatedInput,
    versionId,
    handleGenerateInstructions,
    handleGeneratePlaygroundInput,
    hasModelsBeenSet,
    hasVersions,
    latestTaskRun,
    latestTaskRunOnSameModel,
    onTaskRunIdUpdate,
    persistedTaskRunsInitialized,
    persistedTaskRunsWithSameModel,
    redirectWithParams,
    setGeneratedInput,
    versions,
    persistedVersionId,
    taskRun1,
    taskRun1Initialized,
    taskRunId1,
    taskRunId2,
    taskRunId3,
    voidInput,
  ]);

  const hasUpdatedVersion = useRef(false);

  // When loading initial version, update the instructions, temperature, few-shot count and model
  useEffect(() => {
    if (!currentVersion || hasUpdatedVersion.current) {
      return;
    }
    hasUpdatedVersion.current = true;
    const currentVersionProperties = currentVersion?.properties;
    const currentVersionInstructions = currentVersionProperties?.instructions;
    const currentVersionTemperature = currentVersionProperties?.temperature;
    // @ts-expect-error we should fix the type of version properties
    const currentVersionModel: Model = currentVersion?.model ?? '';
    if (currentVersionInstructions) {
      setInstructions(currentVersionInstructions);
    }
    if (currentVersionTemperature) {
      setTemperature(currentVersionTemperature);
    }
    // We only want to set the model if the task group is forced
    // Otherwise, we rely on models cached
    if (isForcedVersion.current) {
      setSchemaModels(0, currentVersionModel);
    }
  }, [currentVersion, setInstructions, setTemperature, setSchemaModels, taskRunId1]);

  const handleSetRunModel = useCallback(
    (index: number, taskRun: TaskRun | undefined) => {
      if (!taskRun) return;
      setSchemaModels(index, (taskRun.group?.properties?.model ?? '') as Model);
    },
    [setSchemaModels]
  );

  // If we have task runs, set the models to the models of the task runs
  useEffect(() => {
    handleSetRunModel(0, taskRun1);
  }, [taskRun1, handleSetRunModel]);
  useEffect(() => {
    handleSetRunModel(1, taskRun2);
  }, [taskRun2, handleSetRunModel]);
  useEffect(() => {
    handleSetRunModel(2, taskRun3);
  }, [taskRun3, handleSetRunModel]);

  useEffect(() => {
    // If we have task runs, but they are not initialized, wait
    if (!!taskRunId1 && !taskRun1Initialized) return;
    if (!!taskRunId2 && !taskRun2Initialized) return;
    if (!!taskRunId3 && !taskRun3Initialized) return;
    const notNilTaskRun = taskRun1 || taskRun2 || taskRun3;
    // Check if we have a task run with input, if so, set the input
    if (notNilTaskRun) {
      const newInput = notNilTaskRun.task_input;
      setGeneratedInput(newInput);
      return;
    }
  }, [
    taskRun1,
    taskRun2,
    taskRun3,
    taskRun1Initialized,
    taskRun2Initialized,
    taskRun3Initialized,
    taskRunId1,
    taskRunId2,
    taskRunId3,
    setGeneratedInput,
  ]);

  // We only want to set the model in 2 cases if there is no task run
  // 1. If the model is not set
  // 2. If the model is not found in the list of AI models (can happen if the model was deleted)
  const shouldSetDefaultModel = useCallback(
    (index: number) => {
      if (aiModels.length === 0) return false;
      const currentModel = schemaModels[index];
      if (!currentModel) return true;
      return !aiModels.find((model) => model.id === currentModel);
    },
    [aiModels, schemaModels]
  );

  const defaultModels = useDefaultModels(aiModels);

  const computeAndSetModel = useCallback(
    (taskRunId: string | undefined, index: number) => {
      if (!!taskRunId) {
        return;
      }
      const schemaModel = schemaModels[index];
      const taskModel = taskModels[index];
      if (!!taskModel) {
        if (!!schemaModel) {
          return;
        }
        setSchemaModels(index, taskModel);
        return;
      }
      if (shouldSetDefaultModel(index)) {
        setSchemaModels(index, defaultModels[index]);
      }
    },
    [setSchemaModels, shouldSetDefaultModel, defaultModels, taskModels, schemaModels]
  );

  // If we have no task runs, set the models to the first and last AI models
  // This should only happen once
  const defaultModelsInitialized = useRef(false);

  useEffect(() => {
    if (aiModels.length === 0 || defaultModelsInitialized.current) return;
    defaultModelsInitialized.current = true;

    computeAndSetModel(taskRunId1, 0);
    computeAndSetModel(taskRunId2, 1);
    computeAndSetModel(taskRunId3, 2);
  }, [aiModels, taskRunId1, taskRunId2, taskRunId3, defaultModelsInitialized, computeAndSetModel]);

  useEffect(() => {
    if (!!taskRunId1 && !!taskRun1) {
      resetStreamedChunk(0);
    }
    if (!!taskRunId2 && !!taskRun2) {
      resetStreamedChunk(1);
    }
    if (!!taskRunId3 && !!taskRun3) {
      resetStreamedChunk(2);
    }
  }, [taskRunId1, taskRunId2, taskRunId3, taskRun1, taskRun2, taskRun3, resetStreamedChunk]);

  return {
    taskRun1,
    taskRun2,
    taskRun3,
    taskRun1Initialized,
    taskRun2Initialized,
    taskRun3Initialized,
    taskRun1Loading,
    taskRun2Loading,
    taskRun3Loading,
  };
}
