import { nanoid } from 'nanoid';
import { useCallback, useEffect, useMemo } from 'react';
import { useOrFetchLatestRun, useOrFetchRunV1, useOrFetchVersion } from '@/store/fetchers';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { useProxyOutputModels } from './useProxyOutputModels';
import { useProxyPlaygroundSearchParams } from './useProxyPlaygroundSearchParams';

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
    temperature,
    setTemperature,
    model1,
    model2,
    model3,
    setModel1,
    setModel2,
    setModel3,

    schemaId,
    setSchemaId,
    changeURLSchemaId,

    scrollToBottom,
    setScrollToBottom,

    performRun,
    setPerformRun,
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

  useEffect(() => {
    if (temperature !== undefined || !version) {
      return;
    }

    setTemperature(version.properties.temperature ?? undefined);
  }, [version, temperature, setTemperature]);

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

  const { outputModels, setOutputModels, compatibleModels, allModels } = useProxyOutputModels(
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
    setModel3
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
    temperature,
    setTemperature,
    outputModels,
    setOutputModels,
    compatibleModels,
    allModels,
    schemaId,
    setSchemaId,
    changeURLSchemaId,
    scrollToBottom,
    setScrollToBottom,
    performRun,
    setPerformRun,
  };
}
