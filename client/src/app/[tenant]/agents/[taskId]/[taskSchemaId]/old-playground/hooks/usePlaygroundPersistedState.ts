import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocalStorage, useSessionStorage } from 'usehooks-ts';
import { useRedirectWithParams } from '@/lib/queryString';
import { buildScopeKey } from '@/store/utils';
import { GeneralizedTaskInput } from '@/types';
import { ModelOptional, TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';
import { PlaygroundModels, formatTaskRunIdParam } from './utils';

export type GeneratePlaygroundInputParams = {
  externalVersion?: VersionV1 | undefined;
  // These are the instructions to be used when launching runs
  externalInstructions?: string;
  launchRuns?: boolean;
  // These are the instructions to be used when generating the input
  instructions?: string;
  temperature?: number;
  successMessage?: string;
  inputText?: string;
  baseInput?: Record<string, unknown>;
};

export type RunTaskOptions = {
  externalGeneratedInput?: GeneralizedTaskInput;
  externalVersion?: VersionV1;
  externalModel?: string;
  externalTemperature?: number;
  externalInstructions?: string;
};

type PlaygroundPersistedState = Record<
  string,
  {
    models: PlaygroundModels;
    showDiffMode: boolean;
    show2ColumnLayout: boolean;
    taskRunId1: string | undefined;
    taskRunId2: string | undefined;
    taskRunId3: string | undefined;
    versionId: string | undefined;
  }
>;

type PlaygroundSessionPersistedState = Record<
  string,
  {
    generatedInput: GeneralizedTaskInput | undefined;
    preGeneratedInput: GeneralizedTaskInput | undefined;
  }
>;

type Props = {
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  tenant: TenantID | undefined;
  showDiffModeParam: string | undefined;
  show2ColumnLayoutParam: string | undefined;
};

export function usePlaygroundPersistedState(props: Props) {
  const { taskId, taskSchemaId, tenant, showDiffModeParam, show2ColumnLayoutParam } = props;

  const [persistedState, setPersistedState] = useLocalStorage<PlaygroundPersistedState>('playgroundPersistedState', {});
  const [sessionPersistedState, setSessionPersistedState] = useSessionStorage<PlaygroundSessionPersistedState>(
    'playgroundSessionPersistedState',
    {}
  );

  const schemaScopeKey = buildScopeKey({ tenant, taskId, taskSchemaId });
  const taskScopeKey = buildScopeKey({
    tenant,
    taskId,
    taskSchemaId: 'allTaskSchemas',
  });
  // We persist the generated input in session storage to keep it until the user closes the tab
  const persistedGeneratedInput = sessionPersistedState[schemaScopeKey]?.generatedInput;
  const persistedPreGeneratedInput = sessionPersistedState[schemaScopeKey]?.preGeneratedInput;
  const persistedSchemaModels = persistedState[schemaScopeKey]?.models ?? [null, null, null];
  const persistedTaskModels = persistedState[taskScopeKey]?.models ?? [null, null, null];
  const persistedShowDiffMode = persistedState[taskScopeKey]?.showDiffMode ?? false;
  const persistedShow2ColumnLayout = persistedState[taskScopeKey]?.show2ColumnLayout ?? false;
  const persistedTaskRunId1 = persistedState[schemaScopeKey]?.taskRunId1;
  const persistedTaskRunId2 = persistedState[schemaScopeKey]?.taskRunId2;
  const persistedTaskRunId3 = persistedState[schemaScopeKey]?.taskRunId3;
  const persistedVersionId = persistedState[schemaScopeKey]?.versionId;

  const [schemaModels, setSchemaModels] = useState<PlaygroundModels>(persistedSchemaModels);
  const [taskModels, setTaskModels] = useState<PlaygroundModels>(persistedTaskModels);
  const [generatedInput, setGeneratedInput] = useState<GeneralizedTaskInput | undefined>(persistedGeneratedInput);
  const [preGeneratedInput, setPreGeneratedInput] = useState<GeneralizedTaskInput | undefined>(
    persistedPreGeneratedInput
  );

  const handleSetModels = useCallback(
    (index: number, newModel: ModelOptional) => {
      setSchemaModels((prev) => {
        const newModels: PlaygroundModels = [...prev];
        newModels[index] = newModel;
        setPersistedState((prev) => ({
          ...prev,
          [schemaScopeKey]: {
            ...prev[schemaScopeKey],
            models: newModels,
          },
        }));
        return newModels;
      });
      setTaskModels((prev) => {
        const newModelIds: PlaygroundModels = [...prev];
        newModelIds[index] = newModel;
        setPersistedState((prev) => ({
          ...prev,
          [taskScopeKey]: {
            ...prev[taskScopeKey],
            models: newModelIds,
          },
        }));
        return newModelIds;
      });
    },
    [schemaScopeKey, taskScopeKey, setPersistedState]
  );

  const redirectWithParams = useRedirectWithParams();

  const handleSetShowDiffMode = useCallback(
    (showDiffMode: boolean) => {
      redirectWithParams({
        params: { showDiffMode: showDiffMode.toString() },
        scroll: false,
      });
      setPersistedState((prev) => ({
        ...prev,
        [taskScopeKey]: { ...prev[taskScopeKey], showDiffMode },
      }));
    },
    [taskScopeKey, setPersistedState, redirectWithParams]
  );

  const handleSetShow2ColumnLayout = useCallback(
    (show2ColumnLayout: boolean) => {
      redirectWithParams({
        params: { show2ColumnLayout: show2ColumnLayout.toString() },
        scroll: false,
      });
      setPersistedState((prev) => ({
        ...prev,
        [taskScopeKey]: { ...prev[taskScopeKey], show2ColumnLayout },
      }));
    },
    [taskScopeKey, setPersistedState, redirectWithParams]
  );

  // We need to set the showDiffMode and show2ColumnLayout from the query params if they are not defined
  useEffect(() => {
    if (showDiffModeParam === undefined && show2ColumnLayoutParam === undefined) {
      redirectWithParams({
        params: {
          showDiffMode: persistedShowDiffMode ? 'true' : 'false',
          show2ColumnLayout: persistedShow2ColumnLayout ? 'true' : 'false',
        },
        scroll: false,
      });
    }
  }, [
    showDiffModeParam,
    show2ColumnLayoutParam,
    redirectWithParams,
    persistedShowDiffMode,
    persistedShow2ColumnLayout,
  ]);

  const handleGenerateInputChange = useCallback(
    (taskInput: GeneralizedTaskInput | undefined) => {
      setGeneratedInput(taskInput);
      setSessionPersistedState((prev) => ({
        ...prev,
        [schemaScopeKey]: {
          ...prev[schemaScopeKey],
          generatedInput: taskInput,
        },
      }));
    },
    [schemaScopeKey, setSessionPersistedState]
  );

  const handlePreGeneratedInputChange = useCallback(
    (taskInput: GeneralizedTaskInput | undefined) => {
      setPreGeneratedInput(taskInput);
      setSessionPersistedState((prev) => ({
        ...prev,
        [schemaScopeKey]: {
          ...prev[schemaScopeKey],
          preGeneratedInput: taskInput,
        },
      }));
    },
    [schemaScopeKey, setSessionPersistedState]
  );

  const handleSetTaskRunId = useCallback(
    (index: number, taskRunId: string | undefined) => {
      setPersistedState((prev) => ({
        ...prev,
        [schemaScopeKey]: {
          ...prev[schemaScopeKey],
          [formatTaskRunIdParam(index)]: taskRunId,
        },
      }));
    },
    [schemaScopeKey, setPersistedState]
  );

  const handleSetPersistedVersionId = useCallback(
    (versionId: string | undefined) => {
      setPersistedState((prev) => ({
        ...prev,
        [schemaScopeKey]: { ...prev[schemaScopeKey], versionId },
      }));
    },
    [schemaScopeKey, setPersistedState]
  );

  const persistedTaskRunIds = useMemo(
    () => [persistedTaskRunId1, persistedTaskRunId2, persistedTaskRunId3],
    [persistedTaskRunId1, persistedTaskRunId2, persistedTaskRunId3]
  );

  return {
    schemaModels,
    taskModels,
    setSchemaModels: handleSetModels,
    showDiffMode: showDiffModeParam === 'true',
    show2ColumnLayout: show2ColumnLayoutParam === 'true',
    setShowDiffMode: handleSetShowDiffMode,
    setShow2ColumnLayout: handleSetShow2ColumnLayout,
    generatedInput,
    preGeneratedInput,
    setGeneratedInput: handleGenerateInputChange,
    setPreGeneratedInput: handlePreGeneratedInputChange,
    persistedTaskRunIds,
    setTaskRunId: handleSetTaskRunId,
    persistedVersionId,
    setPersistedVersionId: handleSetPersistedVersionId,
  };
}
