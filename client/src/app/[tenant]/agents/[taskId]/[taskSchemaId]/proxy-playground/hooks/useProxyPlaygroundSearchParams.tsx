import { useRouter } from 'next/navigation';
import { usePathname } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { QueryParam, stringifyQueryParams, useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import { replaceTaskSchemaId } from '@/lib/routeFormatter';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { saveSearchParamsToHistory } from './useProxyHistory';

export function useProxyPlaygroundSearchParams(
  tenant: TenantID | undefined,
  taskId: TaskID,
  urlSchemaId: TaskSchemaID
) {
  const {
    versionId: versionIdFromParams,
    taskRunId: runIdForModal,
    taskRunId1: taskRunId1FromParams,
    taskRunId2: taskRunId2FromParams,
    taskRunId3: taskRunId3FromParams,
    baseRunId: baseRunIdFromParams,
    showDiffMode: showDiffModeFromParams,
    hiddenModelColumns: hiddenModelColumnsFromParams,
    historyId: historyIdFromParams,
    temperature: temperatureFromParams,
    model1: model1FromParams,
    model2: model2FromParams,
    model3: model3FromParams,
    scrollToBottom: scrollToBottomFromParams,
    performRun: performRunFromParams,
  } = useParsedSearchParams(
    'versionId',
    'taskRunId',
    'taskRunId1',
    'taskRunId2',
    'taskRunId3',
    'baseRunId',
    'showDiffMode',
    'hiddenModelColumns',
    'historyId',
    'temperature',
    'model1',
    'model2',
    'model3',
    'scrollToBottom',
    'performRun'
  );

  const redirectWithParams = useRedirectWithParams();

  const [versionId, setVersionId] = useState(versionIdFromParams);
  const [taskRunId1, setTaskRunId1] = useState(taskRunId1FromParams);
  const [taskRunId2, setTaskRunId2] = useState(taskRunId2FromParams);
  const [taskRunId3, setTaskRunId3] = useState(taskRunId3FromParams);
  const [baseRunId, setBaseRunId] = useState(baseRunIdFromParams);
  const [showDiffMode, setShowDiffMode] = useState(showDiffModeFromParams);
  const [hiddenModelColumns, setHiddenModelColumns] = useState(hiddenModelColumnsFromParams);
  const [historyId, setHistoryId] = useState(historyIdFromParams);
  const [temperature, setTemperature] = useState<number | undefined>(
    temperatureFromParams ? Number(temperatureFromParams) : undefined
  );
  const [model1, setModel1] = useState<string | undefined>(model1FromParams);
  const [model2, setModel2] = useState<string | undefined>(model2FromParams);
  const [model3, setModel3] = useState<string | undefined>(model3FromParams);

  const [scrollToBottom, setScrollToBottom] = useState(scrollToBottomFromParams);

  const [schemaId, setSchemaId] = useState(urlSchemaId);
  const [performRun, setPerformRun] = useState(performRunFromParams);

  const params = useMemo(() => {
    const result: Record<string, QueryParam> = {
      versionId: versionId,
      taskRunId1: taskRunId1,
      taskRunId2: taskRunId2,
      taskRunId3: taskRunId3,
      baseRunId: baseRunId,
      showDiffMode: showDiffMode,
      hiddenModelColumns: hiddenModelColumns,
      historyId: historyId,
      temperature: temperature ? temperature.toString() : undefined,
      model1: model1,
      model2: model2,
      model3: model3,
      performRun: performRun,
    };

    return result;
  }, [
    versionId,
    taskRunId1,
    taskRunId2,
    taskRunId3,
    baseRunId,
    showDiffMode,
    hiddenModelColumns,
    historyId,
    temperature,
    model1,
    model2,
    model3,
    performRun,
  ]);

  const paramsRef = useRef(params);
  paramsRef.current = params;
  useEffect(() => {
    paramsRef.current = params;
  }, [params]);

  useEffect(() => {
    saveSearchParamsToHistory(tenant, taskId, schemaId, params);
    redirectWithParams({
      params,
      scroll: false,
    });
  }, [params, tenant, taskId, schemaId, redirectWithParams]);

  const setRunIdForModal = useCallback(
    (taskRunId: string | undefined) => {
      redirectWithParams({
        params: {
          taskRunId: taskRunId,
        },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const router = useRouter();
  const pathname = usePathname();

  const changeURLSchemaId = useCallback(
    (taskSchemaId: TaskSchemaID, scrollToBottom?: boolean) => {
      const params = paramsRef.current;
      if (scrollToBottom) {
        params.scrollToBottom = 'true';
      }
      const newUrl = replaceTaskSchemaId(pathname, taskSchemaId);
      const newParamsString = stringifyQueryParams(params);
      router.replace(`${newUrl}${newParamsString}`, { scroll: false });
    },
    [pathname, router]
  );

  return {
    versionId,
    setVersionId,

    taskRunId1,
    taskRunId2,
    taskRunId3,
    setTaskRunId1,
    setTaskRunId2,
    setTaskRunId3,

    baseRunId,
    setBaseRunId,

    showDiffMode,
    setShowDiffMode,

    hiddenModelColumns,
    setHiddenModelColumns,

    runIdForModal,
    setRunIdForModal,

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
  };
}
