import { useRouter } from 'next/navigation';
import { usePathname } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { QueryParam, stringifyQueryParams, useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import { replaceTaskSchemaId } from '@/lib/routeFormatter';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { saveSearchParamsToHistory } from './useProxyHistory';

export function getCacheValue(cache: string | undefined): 'auto' | 'always' | 'never' | undefined {
  if (cache === undefined) {
    return undefined;
  }
  switch (cache) {
    case 'auto':
      return 'auto';
    case 'always':
      return 'always';
    case 'never':
      return 'never';
    default:
      return undefined;
  }
}

export type AdvancedSettings = {
  temperature: string | undefined;
  setTemperature: (temperature: string | undefined) => void;
  cache: string | undefined;
  setCache: (cache: string | undefined) => void;
  top_p: string | undefined;
  setTopP: (topP: string | undefined) => void;
  max_tokens: string | undefined;
  setMaxTokens: (maxTokens: string | undefined) => void;
  stream: string | undefined;
  setStream: (stream: string | undefined) => void;
  stream_options_include_usage: string | undefined;
  setStreamOptionsIncludeUsage: (streamOptionsIncludeUsage: string | undefined) => void;
  stop: string | undefined;
  setStop: (stop: string | undefined) => void;
  presence_penalty: string | undefined;
  setPresencePenalty: (presencePenalty: string | undefined) => void;
  frequency_penalty: string | undefined;
  setFrequencyPenalty: (frequencyPenalty: string | undefined) => void;
  tool_choice: string | undefined;
  setToolChoice: (toolChoice: string | undefined) => void;
};

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
    model1: model1FromParams,
    model2: model2FromParams,
    model3: model3FromParams,
    modelReasoning1: modelReasoning1FromParams,
    modelReasoning2: modelReasoning2FromParams,
    modelReasoning3: modelReasoning3FromParams,
    scrollToBottom: scrollToBottomFromParams,
    temperature: temperatureFromParams,
    cache: cacheFromParams,
    top_p: topPFromParams,
    max_tokens: maxTokensFromParams,
    stream: streamFromParams,
    stream_options_include_usage: streamOptionsIncludeUsageFromParams,
    stop: stopFromParams,
    presence_penalty: presencePenaltyFromParams,
    frequency_penalty: frequencyPenaltyFromParams,
    tool_choice: toolChoiceFromParams,
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
    'modelReasoning1',
    'modelReasoning2',
    'modelReasoning3',
    'scrollToBottom',
    'cache',
    'top_p',
    'max_tokens',
    'stream',
    'stream_options_include_usage',
    'stop',
    'presence_penalty',
    'frequency_penalty',
    'tool_choice'
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
  const [temperature, setTemperature] = useState<string | undefined>(temperatureFromParams);
  const [model1, setModel1] = useState<string | undefined>(model1FromParams);
  const [model2, setModel2] = useState<string | undefined>(model2FromParams);
  const [model3, setModel3] = useState<string | undefined>(model3FromParams);
  const [modelReasoning1, setModelReasoning1] = useState<string | undefined>(modelReasoning1FromParams);
  const [modelReasoning2, setModelReasoning2] = useState<string | undefined>(modelReasoning2FromParams);
  const [modelReasoning3, setModelReasoning3] = useState<string | undefined>(modelReasoning3FromParams);

  const [scrollToBottom, setScrollToBottom] = useState(scrollToBottomFromParams);
  const [cache, setCache] = useState<string | undefined>(cacheFromParams);
  const [top_p, setTopP] = useState<string | undefined>(topPFromParams);
  const [max_tokens, setMaxTokens] = useState<string | undefined>(maxTokensFromParams);
  const [stream, setStream] = useState<string | undefined>(streamFromParams);
  const [stream_options_include_usage, setStreamOptionsIncludeUsage] = useState<string | undefined>(
    streamOptionsIncludeUsageFromParams
  );
  const [stop, setStop] = useState<string | undefined>(stopFromParams);
  const [presence_penalty, setPresencePenalty] = useState<string | undefined>(presencePenaltyFromParams);
  const [frequency_penalty, setFrequencyPenalty] = useState<string | undefined>(frequencyPenaltyFromParams);
  const [tool_choice, setToolChoice] = useState<string | undefined>(toolChoiceFromParams);

  const [schemaId, setSchemaId] = useState(urlSchemaId);

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
      temperature: temperature,
      model1: model1,
      model2: model2,
      model3: model3,
      modelReasoning1: modelReasoning1,
      modelReasoning2: modelReasoning2,
      modelReasoning3: modelReasoning3,
      cache: cache,
      top_p,
      max_tokens,
      stream: stream,
      stream_options_include_usage,
      stop: stop,
      presence_penalty,
      frequency_penalty,
      tool_choice,
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
    modelReasoning1,
    modelReasoning2,
    modelReasoning3,
    cache,
    top_p,
    max_tokens,
    stream,
    stream_options_include_usage,
    stop,
    presence_penalty,
    frequency_penalty,
    tool_choice,
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
      const newUrlWithParams = `${newUrl}${newParamsString}`;

      router.replace(newUrlWithParams, { scroll: false });
    },
    [pathname, router]
  );

  const advancedSettings: AdvancedSettings = {
    temperature,
    setTemperature,
    cache,
    setCache,
    top_p,
    setTopP,
    max_tokens,
    setMaxTokens,
    stream,
    setStream,
    stream_options_include_usage,
    setStreamOptionsIncludeUsage,
    stop,
    setStop,
    presence_penalty,
    setPresencePenalty,
    frequency_penalty,
    setFrequencyPenalty,
    tool_choice,
    setToolChoice,
  };

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
  };
}
