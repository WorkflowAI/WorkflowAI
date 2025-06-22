import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocalStorage, useSessionStorage } from 'usehooks-ts';
import { useRedirectWithParams } from '@/lib/queryString';
import { buildScopeKey } from '@/store/utils';
import { GeneralizedTaskInput } from '@/types';
import { ModelOptional, TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { ProxyMessage, VersionV1 } from '@/types/workflowAI';
import { PlaygroundModels, formatRunIdParam } from './utils';

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
    hiddenModelColumns: number[] | undefined;
    runId1: string | undefined;
    runId2: string | undefined;
    runId3: string | undefined;
    versionId: string | undefined;
    proxyMessages: ProxyMessage[] | undefined;
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
  hiddenModelColumnsParam: string | undefined;
};

export function usePlaygroundPersistedState(props: Props) {
  const { taskId, taskSchemaId, tenant, showDiffModeParam, hiddenModelColumnsParam } = props;

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
  const persistedHiddenModelColumns: number[] | undefined = persistedState[taskScopeKey]?.hiddenModelColumns;
  const persistedRunId1 = persistedState[schemaScopeKey]?.runId1;
  const persistedRunId2 = persistedState[schemaScopeKey]?.runId2;
  const persistedRunId3 = persistedState[schemaScopeKey]?.runId3;
  const persistedVersionId = persistedState[schemaScopeKey]?.versionId;
  const persistedProxyMessages = persistedState[schemaScopeKey]?.proxyMessages;

  const [schemaModels, setSchemaModels] = useState<PlaygroundModels>(persistedSchemaModels);
  const [taskModels, setTaskModels] = useState<PlaygroundModels>(persistedTaskModels);
  const [generatedInput, setGeneratedInput] = useState<GeneralizedTaskInput | undefined>(persistedGeneratedInput);
  const [proxyMessages, setProxyMessages] = useState<ProxyMessage[] | undefined>(persistedProxyMessages);
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

  const handleSetHiddenModelColumns = useCallback(
    (hiddenModelColumns: number[] | undefined) => {
      redirectWithParams({
        params: { hiddenModelColumns: hiddenModelColumns?.join(',') },
        scroll: false,
      });
      setPersistedState((prev) => ({
        ...prev,
        [taskScopeKey]: { ...prev[taskScopeKey], hiddenModelColumns },
      }));
    },
    [taskScopeKey, setPersistedState, redirectWithParams]
  );

  // We need to set the showDiffMode and hiddenModelColumns from the query params if they are not defined
  useEffect(() => {
    if (showDiffModeParam === undefined && hiddenModelColumnsParam === undefined) {
      redirectWithParams({
        params: {
          showDiffMode: persistedShowDiffMode ? 'true' : 'false',
          hiddenModelColumns: persistedHiddenModelColumns?.join(','),
        },
        scroll: false,
      });
    }
  }, [
    showDiffModeParam,
    hiddenModelColumnsParam,
    redirectWithParams,
    persistedShowDiffMode,
    persistedHiddenModelColumns,
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

  const handleSetProxyMessages = useCallback(
    (proxyMessages: ProxyMessage[] | undefined) => {
      setProxyMessages(proxyMessages);
      setSessionPersistedState((prev) => ({
        ...prev,
        [schemaScopeKey]: {
          ...prev[schemaScopeKey],
          proxyMessages,
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

  const handleSetRunId = useCallback(
    (index: number, runId: string | undefined) => {
      setPersistedState((prev) => ({
        ...prev,
        [schemaScopeKey]: {
          ...prev[schemaScopeKey],
          [formatRunIdParam(index)]: runId,
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
    () => [persistedRunId1, persistedRunId2, persistedRunId3],
    [persistedRunId1, persistedRunId2, persistedRunId3]
  );

  const hiddenModelColumns = useMemo(() => {
    if (hiddenModelColumnsParam) {
      return hiddenModelColumnsParam.split(',').map(Number);
    }
    return persistedHiddenModelColumns;
  }, [hiddenModelColumnsParam, persistedHiddenModelColumns]);

  return {
    schemaModels,
    taskModels,
    setSchemaModels: handleSetModels,
    showDiffMode: showDiffModeParam === 'true',
    setShowDiffMode: handleSetShowDiffMode,
    hiddenModelColumns: hiddenModelColumns,
    setHiddenModelColumns: handleSetHiddenModelColumns,
    generatedInput,
    preGeneratedInput,
    setGeneratedInput: handleGenerateInputChange,
    setPreGeneratedInput: handlePreGeneratedInputChange,
    persistedTaskRunIds,
    setRunId: handleSetRunId,
    persistedVersionId,
    setPersistedVersionId: handleSetPersistedVersionId,
    proxyMessages,
    setProxyMessages: handleSetProxyMessages,
  };
}
