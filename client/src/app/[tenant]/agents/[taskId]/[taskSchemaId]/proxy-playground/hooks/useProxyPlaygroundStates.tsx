import { nanoid } from 'nanoid';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useOrFetchLatestRun, useOrFetchRunV1, useOrFetchVersion } from '@/store/fetchers';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';
import { useProxyOutputModels } from './useProxyOutputModels';
import { useProxyPlaygroundSearchParams } from './useProxyPlaygroundSearchParams';

function useSetPropertyFromVersionIfNotSetYet(
  version: VersionV1 | undefined,
  key: string,
  property: string | undefined,
  setProperty: (property: string | undefined) => void
) {
  const propertyRef = useRef<string | undefined>(property);
  useEffect(() => {
    propertyRef.current = property;
  }, [property]);

  const keyRef = useRef<string>(key);
  useEffect(() => {
    keyRef.current = key;
  }, [key]);

  const setPropertyRef = useRef<((property: string | undefined) => void) | undefined>(setProperty);
  useEffect(() => {
    setPropertyRef.current = setProperty;
  }, [setProperty]);

  useEffect(() => {
    const property = propertyRef.current;
    const key = keyRef.current;

    // If the property is already set or the version is undefined or the property in version is not set yet, do nothing
    if (property !== undefined || version === undefined || version.properties[key] === undefined) {
      return;
    }

    const value = String(version.properties[key]);
    setPropertyRef.current?.(value);
  }, [version]);
}

export function useProxyPlaygroundStates(tenant: TenantID | undefined, taskId: TaskID, urlSchemaId: TaskSchemaID) {
  const {
    versionId,
    taskRunId1,
    taskRunId2,
    taskRunId3,
    baseRunId,
    showDiffMode,
    hiddenModelColumns,
    setVersionId,
    setTaskRunId1,
    setTaskRunId2,
    setTaskRunId3,
    setBaseRunId,
    setShowDiffMode,
    setHiddenModelColumns,
    setRunIdForModal,
    runIdForModal,
    historyId,
    setHistoryId,
    model1,
    model2,
    model3,
    setModel1,
    setModel2,
    setModel3,

    modelReasoning1,
    modelReasoning2,
    modelReasoning3,
    setModelReasoning1,
    setModelReasoning2,
    setModelReasoning3,

    schemaId,
    setSchemaId,
    changeURLSchemaId,

    scrollToBottom,
    setScrollToBottom,

    advancedSettings,
  } = useProxyPlaygroundSearchParams(tenant, taskId, urlSchemaId);

  const { version } = useOrFetchVersion(tenant, taskId, versionId);

  const { run: run1 } = useOrFetchRunV1(tenant, taskId, taskRunId1);
  const { run: run2 } = useOrFetchRunV1(tenant, taskId, taskRunId2);
  const { run: run3 } = useOrFetchRunV1(tenant, taskId, taskRunId3);

  const { run: baseRun } = useOrFetchRunV1(tenant, taskId, baseRunId);

  const { latestRun } = useOrFetchLatestRun(tenant, taskId, schemaId);

  // We only need to set two parameters: baseRunId and versionId
  useEffect(() => {
    if (!historyId) {
      setHistoryId(nanoid(10));
    }
  }, [historyId, setHistoryId]);

  useEffect(() => {
    if (!!baseRunId) {
      return;
    }

    if (taskRunId1 || taskRunId2 || taskRunId3) {
      setBaseRunId(taskRunId1 ?? taskRunId2 ?? taskRunId3);
      return;
    }

    if (latestRun) {
      setBaseRunId(latestRun.id);
      return;
    }
  }, [versionId, baseRunId, taskRunId1, taskRunId2, taskRunId3, latestRun, setBaseRunId]);

  useEffect(() => {
    if (!!versionId) {
      return;
    }

    if (!!baseRun) {
      setVersionId(baseRun.version.id);

      // Also if the Runs are empty and the version ids match let's set the first task run id to the base run id
      if (!run1 && !run2 && !run3) {
        setTaskRunId1(baseRunId);
      }
      return;
    }
  }, [versionId, baseRun, setVersionId, run1, run2, run3, baseRunId, setTaskRunId1]);

  useSetPropertyFromVersionIfNotSetYet(
    version,
    'temperature',
    advancedSettings.temperature,
    advancedSettings.setTemperature
  );
  useSetPropertyFromVersionIfNotSetYet(version, 'top_p', advancedSettings.top_p, advancedSettings.setTopP);
  useSetPropertyFromVersionIfNotSetYet(
    version,
    'max_tokens',
    advancedSettings.max_tokens,
    advancedSettings.setMaxTokens
  );
  useSetPropertyFromVersionIfNotSetYet(
    version,
    'presence_penalty',
    advancedSettings.presence_penalty,
    advancedSettings.setPresencePenalty
  );
  useSetPropertyFromVersionIfNotSetYet(
    version,
    'frequency_penalty',
    advancedSettings.frequency_penalty,
    advancedSettings.setFrequencyPenalty
  );
  useSetPropertyFromVersionIfNotSetYet(
    version,
    'tool_choice',
    advancedSettings.tool_choice,
    advancedSettings.setToolChoice
  );
  useSetPropertyFromVersionIfNotSetYet(version, 'use_cache', advancedSettings.cache, advancedSettings.setCache);

  // Setters and Getters with Sync

  const showDiffModeParsed = useMemo(() => showDiffMode === 'true', [showDiffMode]);

  const hiddenModelColumnsParsed = useMemo(() => {
    if (hiddenModelColumns) {
      return hiddenModelColumns.split(',').map(Number);
    }
    return [];
  }, [hiddenModelColumns]);

  const setShowDiffModeWithSearchParamsSync = useCallback(
    (showDiffMode: boolean) => {
      setShowDiffMode(showDiffMode.toString());
    },
    [setShowDiffMode]
  );

  const setHiddenModelColumnsWithSearchParamsSync = useCallback(
    (hiddenModelColumns: number[]) => {
      setHiddenModelColumns(hiddenModelColumns.join(','));
    },
    [setHiddenModelColumns]
  );

  const setTaskRunId = useCallback(
    (index: number, runId: string | undefined) => {
      switch (index) {
        case 0:
          setTaskRunId1(runId);
          break;
        case 1:
          setTaskRunId2(runId);
          break;
        case 2:
          setTaskRunId3(runId);
          break;
      }
    },
    [setTaskRunId1, setTaskRunId2, setTaskRunId3]
  );

  const resetTaskRunIds = useCallback(() => {
    setTaskRunId1(undefined);
    setTaskRunId2(undefined);
    setTaskRunId3(undefined);
  }, [setTaskRunId1, setTaskRunId2, setTaskRunId3]);

  const { outputModels, setOutputModels, compatibleModels, allModels, maxTokens } = useProxyOutputModels(
    tenant,
    taskId,
    schemaId,
    run1,
    run2,
    run3,
    model1,
    model2,
    model3,
    setModel1,
    setModel2,
    setModel3,
    modelReasoning1,
    modelReasoning2,
    modelReasoning3,
    setModelReasoning1,
    setModelReasoning2,
    setModelReasoning3
  );

  return {
    version,
    run1,
    run2,
    run3,
    baseRun,
    versionId,
    taskRunId1,
    taskRunId2,
    taskRunId3,
    baseRunId,
    showDiffMode: showDiffModeParsed,
    hiddenModelColumns: hiddenModelColumnsParsed,
    setShowDiffMode: setShowDiffModeWithSearchParamsSync,
    setHiddenModelColumns: setHiddenModelColumnsWithSearchParamsSync,
    setTaskRunId,
    resetTaskRunIds,
    setRunIdForModal,
    runIdForModal,
    historyId,
    outputModels,
    setOutputModels,
    compatibleModels,
    allModels,
    schemaId,
    setSchemaId,
    changeURLSchemaId,
    scrollToBottom,
    setScrollToBottom,

    advancedSettings,
    maxTokens,
  };
}
