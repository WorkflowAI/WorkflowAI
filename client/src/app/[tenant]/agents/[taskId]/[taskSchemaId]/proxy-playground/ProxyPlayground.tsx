'use client';

/* eslint-disable max-lines */
import { Link16Regular } from '@fluentui/react-icons';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useHotkeys } from 'react-hotkeys-hook';
import useMeasure from 'react-use-measure';
import TaskRunModal from '@/components/TaskRunModal/TaskRunModal';
import { Button } from '@/components/ui/Button';
import { PageContainer } from '@/components/v2/PageContainer';
import { useCopyCurrentUrl } from '@/lib/hooks/useCopy';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useIsMobile } from '@/lib/hooks/useIsMobile';
import {
  useOrFetchOrganizationSettings,
  useOrFetchSchema,
  useOrFetchTask,
  useOrFetchVersions,
  useScheduledMetaAgentMessages,
} from '@/store';
import { useOrExtractTemplete } from '@/store/extract_templete';
import { ToolCallName, usePlaygroundChatStore } from '@/store/playgroundChatStore';
import { GeneralizedTaskInput } from '@/types';
import { ModelOptional, TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import {
  MajorVersion,
  PlaygroundState,
  RunV1,
  SelectedModels,
  TaskInputDict,
  ToolKind,
  Tool_Output,
} from '@/types/workflowAI';
import { ProxyMessage } from '@/types/workflowAI';
import { CodeModal } from '../code/CodeModal';
import { PlaygroundChat } from '../playground/components/Chat/PlaygroundChat';
import { RunAgentsButton } from '../playground/components/RunAgentsButton';
import { RunTaskOptions } from '../playground/hooks/usePlaygroundPersistedState';
import { useVersionsForTaskRunners } from '../playground/hooks/useVersionsForRuns';
import { ProxySection } from './ProxySection';
import { ProxyCodeButton } from './code/ProxyCodeButton';
import { performScroll } from './components/performScroll';
import { getFromProxyHistory, useSaveToProxyHistory } from './hooks/useProxyHistory';
import { ProxyImproveMessagesControls, useProxyImproveMessages } from './hooks/useProxyImproveMessages';
import { useProxyMatchVersion } from './hooks/useProxyMatchVersion';
import { useProxyPerformRuns } from './hooks/useProxyPerformRuns';
import { useProxyPlaygroundStates } from './hooks/useProxyPlaygroundStates';
import { useProxyRunners } from './hooks/useProxyRunners';
import { ProxyOutput } from './output/ProxyOutput';
import {
  findMessagesInVersion,
  moveInputMessagesToVersionIfRequired,
  repairMessageKeyInInput,
  valueFromToolChoice,
} from './utils';

export type Props = {
  taskId: TaskID;
  tenant: TenantID | undefined;
  schemaId: TaskSchemaID;
};

export function ProxyPlayground(props: Props) {
  const { tenant, taskId, schemaId: urlSchemaId } = props;

  const { task, isInitialized: isTaskInitialized } = useOrFetchTask(tenant, taskId);

  const {
    historyId,
    version,
    setShowDiffMode,
    setHiddenModelColumns,
    showDiffMode,
    hiddenModelColumns,
    run1,
    run2,
    run3,
    taskRunId1,
    taskRunId2,
    taskRunId3,
    baseRun,
    setTaskRunId,
    resetTaskRunIds,
    setRunIdForModal,
    runIdForModal,
    outputModels,
    setOutputModels,
    allModels,
    schemaId,
    setSchemaId,
    changeURLSchemaId,
    scrollToBottom,
    setScrollToBottom,
    advancedSettings,
    maxTokens,
  } = useProxyPlaygroundStates(tenant, taskId, urlSchemaId);

  const { taskSchema: schema } = useOrFetchSchema(tenant, taskId, urlSchemaId);

  useEffect(() => {
    if (scrollToBottom) {
      performScroll('playground-scroll', 'bottom', 'instant');
      setScrollToBottom(undefined);
    }
  }, [scrollToBottom, setScrollToBottom]);

  const inputSchema = useMemo(() => schema?.input_schema.json_schema, [schema]);
  const outputSchema = useMemo(() => schema?.output_schema.json_schema, [schema]);

  const [input, setInput] = useState<GeneralizedTaskInput | undefined>(getFromProxyHistory(historyId, 'input'));

  const [proxyMessages, setProxyMessages] = useState<ProxyMessage[] | undefined>(
    getFromProxyHistory(historyId, 'proxy-messages')
  );

  const [proxyToolCalls, setProxyToolCalls] = useState<(ToolKind | Tool_Output)[] | undefined>(
    getFromProxyHistory(historyId, 'proxy-tool-calls')
  );

  useSaveToProxyHistory(historyId, 'input', input);
  useSaveToProxyHistory(historyId, 'proxy-messages', proxyMessages);
  useSaveToProxyHistory(historyId, 'proxy-tool-calls', proxyToolCalls);

  useEffect(() => {
    if (!version || !baseRun) {
      return;
    }

    const input: GeneralizedTaskInput | undefined =
      getFromProxyHistory(historyId, 'input') ?? repairMessageKeyInInput(baseRun.task_input);

    const messages: ProxyMessage[] | undefined =
      getFromProxyHistory(historyId, 'proxy-messages') ?? findMessagesInVersion(version);

    const toolCalls: (ToolKind | Tool_Output)[] | undefined =
      getFromProxyHistory(historyId, 'proxy-tool-calls') ?? version?.properties.enabled_tools ?? undefined;

    const { input: modifiedInput, messages: modifiedMessages } = moveInputMessagesToVersionIfRequired(input, messages);

    setInput(modifiedInput);
    setProxyMessages(modifiedMessages);
    setProxyToolCalls(toolCalls);
  }, [version, baseRun, historyId]);

  const {
    schema: extractedInputSchema,
    setSchema: setExtractedInputSchema,
    inputVariblesKeys,
    error: extractedInputSchemaError,
    areThereChangesInInputSchema,
  } = useOrExtractTemplete(tenant, taskId, schema?.schema_id, proxyMessages, inputSchema, historyId);

  const playgroundOutputRef = useRef<HTMLDivElement>(null);
  const [scheduledPlaygroundStateMessage, setScheduledPlaygroundStateMessage] = useState<string | undefined>(undefined);

  const { majorVersions } = useOrFetchVersions(tenant, taskId, schemaId);
  const [userSelectedMajor, setUserSelectedMajor] = useState<number | undefined>(undefined);

  const { matchedVersion: matchedMajorVersion } = useProxyMatchVersion({
    majorVersions,
    userSelectedMajor,
    advancedSettings,
    proxyMessages,
  });

  const { noCreditsLeft } = useOrFetchOrganizationSettings();

  const { areTasksRunning, errorsForModels, performRuns, stopAllRuns, stopRun, streamedChunks, inProgressIndexes } =
    useProxyPerformRuns({
      setTaskRunId,
      input,
      tenant,
      taskId,
      schemaId,
      variantId: schema?.latest_variant_id ?? undefined,
      taskRunId1,
      taskRunId2,
      taskRunId3,
      hiddenModelColumns,
      proxyMessages,
      proxyToolCalls,
      outputModels,
      changeURLSchemaId,
      areThereChangesInInputSchema,
      extractedInputSchema,
      outputSchema,
      setSchemaId,
      setScheduledPlaygroundStateMessage,
      advancedSettings,
      models: allModels,
    });

  const onPerformRuns = useCallback(
    async (indexes?: number[]) => {
      performScroll('playground-scroll', 'bottom', 'smooth');
      await performRuns(indexes);
      performScroll('playground-scroll', 'bottom', 'instant');
    },
    [performRuns]
  );

  useHotkeys('meta+enter', () => onPerformRuns());

  const runs = useMemo(() => [run1, run2, run3], [run1, run2, run3]);
  const [versionIdForCode, setVersionIdForCode] = useState<string | undefined>(undefined);

  const filteredRunIds = useMemo(() => {
    const result = runs.filter((run) => !!run) as RunV1[];
    return result.map((run) => run?.id ?? '');
  }, [runs]);

  const taskRunners = useProxyRunners({
    inProgressIndexes,
    streamedChunks,
    runs,
    performRuns: onPerformRuns,
    stopRun,
    input,
  });

  const { versionsForRuns, showSaveAllVersions, onSaveAllVersions } = useVersionsForTaskRunners({
    tenant,
    taskId,
    taskRunners,
    hiddenModelColumns,
  });

  const setModelAndRun = useCallback(
    async (index: number, model: string | undefined, reasoning: string | undefined) => {
      setOutputModels(index, model, reasoning);
      setTimeout(() => {
        onPerformRuns([index]);
      }, 300);
    },
    [onPerformRuns, setOutputModels]
  );

  const copyUrl = useCopyCurrentUrl();

  const [containerRef, { height: containerHeight }] = useMeasure();

  const useParametersFromMajorVersion = useCallback(
    (version: MajorVersion) => {
      resetTaskRunIds();

      advancedSettings.setTemperature(String(version.properties.temperature));
      advancedSettings.setTopP(String(version.properties.top_p));
      advancedSettings.setFrequencyPenalty(String(version.properties.frequency_penalty));
      advancedSettings.setPresencePenalty(String(version.properties.presence_penalty));
      advancedSettings.setToolChoice(valueFromToolChoice(version.properties.tool_choice));

      const messages = (version.properties.messages as ProxyMessage[]) ?? undefined;
      setProxyMessages(messages);

      setUserSelectedMajor(version.major);
    },
    [advancedSettings, setUserSelectedMajor, resetTaskRunIds, setProxyMessages]
  );

  const { isInDemoMode, onDifferentTenant } = useDemoMode();

  const playgroundState: PlaygroundState = useMemo(() => {
    const models: SelectedModels = {
      column_1: outputModels.model1 ?? null,
      column_2: outputModels.model2 ?? null,
      column_3: outputModels.model3 ?? null,
    };

    const result = {
      is_proxy: true,
      version_id: version?.id,
      version_messages: proxyMessages,
      agent_input: input as Record<string, unknown>,
      agent_instructions: '',
      agent_temperature: advancedSettings.temperature ? Number(advancedSettings.temperature) : undefined,
      agent_run_ids: filteredRunIds,
      selected_models: models,
    };
    return result;
  }, [input, advancedSettings, filteredRunIds, outputModels, version, proxyMessages]);

  const markToolCallAsDone = usePlaygroundChatStore((state) => state.markToolCallAsDone);

  const { cancelScheduledPlaygroundMessage } = useScheduledMetaAgentMessages(
    tenant,
    taskId,
    schemaId,
    playgroundState,
    scheduledPlaygroundStateMessage,
    setScheduledPlaygroundStateMessage,
    1000
  );

  const onChatRequestToChangeModels = useCallback(
    (
      columnsAndModels: {
        column: number;
        model: ModelOptional | undefined;
      }[]
    ) => {
      const individualOptions: Record<number, RunTaskOptions> = {};
      columnsAndModels.forEach((columnAndModel) => {
        setOutputModels(columnAndModel.column, columnAndModel.model ?? undefined, undefined);
        if (columnAndModel.model) {
          individualOptions[columnAndModel.column] = {
            externalModel: columnAndModel.model,
          };
        }
      });

      markToolCallAsDone(taskId, ToolCallName.RUN_CURRENT_AGENT_ON_MODELS);
      onPerformRuns();
    },
    [setOutputModels, markToolCallAsDone, taskId, onPerformRuns]
  );

  const isMobile = useIsMobile();

  const shouldShowChat = useMemo(() => {
    if (isMobile) {
      return false;
    }
    if (onDifferentTenant) {
      return false;
    }
    return true;
  }, [isMobile, onDifferentTenant]);

  const addModelColumn = useCallback(() => {
    const newHiddenModelColumns = hiddenModelColumns ?? [];
    newHiddenModelColumns.pop();
    setHiddenModelColumns(newHiddenModelColumns);
  }, [hiddenModelColumns, setHiddenModelColumns]);

  const hideModelColumn = useCallback(
    (column: number) => {
      const newHiddenModelColumns = hiddenModelColumns ?? [];
      if (newHiddenModelColumns.includes(column)) {
        return;
      }
      newHiddenModelColumns.push(column);
      setHiddenModelColumns(newHiddenModelColumns);
    },
    [hiddenModelColumns, setHiddenModelColumns]
  );

  const onSetProxyMessages = useCallback(
    (messages: ProxyMessage[] | undefined) => {
      resetTaskRunIds();
      stopAllRuns();
      setProxyMessages(messages);
    },
    [setProxyMessages, resetTaskRunIds, stopAllRuns]
  );

  const onSetInputAndResetRuns = useCallback(
    (input: GeneralizedTaskInput | undefined) => {
      resetTaskRunIds();
      stopAllRuns();
      setInput(input);
    },
    [setInput, resetTaskRunIds, stopAllRuns]
  );

  const updateInputAndRun = useCallback(
    async (input: TaskInputDict) => {
      setInput(input);
      await new Promise((resolve) => setTimeout(resolve, 200));
      performScroll('proxy-messages-view', 'bottom', 'smooth');
      await onPerformRuns();
    },
    [setInput, onPerformRuns]
  );

  const improveMessagesControls: ProxyImproveMessagesControls = useProxyImproveMessages({
    taskId,
    tenant,
    versionId: version?.id,
    proxyMessages,
    setProxyMessages,
  });

  const onImproveVersionMessagesFromChat = useCallback(
    async (improvementInstructions: string) => {
      performScroll('playground-scroll', 'top', 'smooth');
      await improveMessagesControls.improveVersionMessages(improvementInstructions);
    },
    [improveMessagesControls]
  );

  const onCancelChatRequest = useCallback(() => {
    improveMessagesControls.cancelImprovement();
    cancelScheduledPlaygroundMessage();
    stopAllRuns();
    setTimeout(() => {
      stopAllRuns();
    }, 1000);
  }, [cancelScheduledPlaygroundMessage, improveMessagesControls, stopAllRuns]);

  return (
    <div className='flex flex-row h-full w-full'>
      <div className='flex h-full flex-1 overflow-hidden'>
        <PageContainer
          task={task}
          schemaId={schemaId}
          isInitialized={isTaskInitialized}
          name='Playground'
          showCopyLink={false}
          showBottomBorder={true}
          documentationLink='https://docs.workflowai.com/features/playground'
          documentationText='Docs'
          rightBarText='Your data is not used for LLM training.'
          rightBarChildren={
            <div className='flex flex-row items-center gap-2 font-lato'>
              <Button variant='newDesign' icon={<Link16Regular />} onClick={copyUrl} className='w-9 h-9 px-0 py-0' />
              <ProxyCodeButton
                runs={runs}
                versionsForRuns={versionsForRuns}
                outputModels={outputModels}
                models={allModels}
                tenant={tenant}
                taskId={taskId}
                schemaId={schemaId}
                proxyMessages={proxyMessages}
                proxyToolCalls={proxyToolCalls}
                advancedSettings={advancedSettings}
                setVersionIdForCode={setVersionIdForCode}
              />
              {!isMobile && (
                <RunAgentsButton
                  showSaveAllVersions={false}
                  areTasksRunning={areTasksRunning}
                  inputLoading={false}
                  areInstructionsLoading={false}
                  onSaveAllVersions={onSaveAllVersions}
                  onTryPromptClick={() => onPerformRuns()}
                  onStopAllRuns={stopAllRuns}
                />
              )}
            </div>
          }
          showBorders={!isMobile}
        >
          <div
            id='playground-scroll'
            className='flex flex-col w-full h-full overflow-y-auto relative'
            ref={(element) => {
              containerRef(element);
            }}
          >
            <div className='flex flex-col w-full sm:pb-0 pb-20'>
              <ProxySection
                extractedInputSchema={extractedInputSchema}
                setExtractedInputSchema={setExtractedInputSchema}
                inputVariblesKeys={inputVariblesKeys}
                error={extractedInputSchemaError}
                input={input}
                setInput={onSetInputAndResetRuns}
                advancedSettings={advancedSettings}
                toolCalls={proxyToolCalls}
                setToolCalls={setProxyToolCalls}
                maxHeight={isMobile ? undefined : containerHeight - 50}
                proxyMessages={proxyMessages}
                setProxyMessages={onSetProxyMessages}
                tenant={tenant}
                taskId={taskId}
                matchedMajorVersion={matchedMajorVersion}
                majorVersions={majorVersions}
                useParametersFromMajorVersion={useParametersFromMajorVersion}
                showSaveAllVersions={showSaveAllVersions && !noCreditsLeft && !isInDemoMode}
                onSaveAllVersions={onSaveAllVersions}
                versionsForRuns={versionsForRuns}
                improveMessagesControls={improveMessagesControls}
                maxTokens={maxTokens}
              />
              <div ref={playgroundOutputRef} className='flex w-full'>
                <ProxyOutput
                  aiModels={allModels}
                  areInstructionsLoading={false}
                  errorForModels={errorsForModels}
                  models={outputModels}
                  onModelsChange={setModelAndRun}
                  outputSchema={outputSchema}
                  showDiffMode={showDiffMode}
                  setShowDiffMode={setShowDiffMode}
                  taskId={taskId}
                  taskSchemaId={schemaId}
                  taskRunners={taskRunners}
                  tenant={tenant}
                  versionsForRuns={versionsForRuns}
                  maxHeight={isMobile ? undefined : containerHeight}
                  addModelColumn={addModelColumn}
                  hideModelColumn={hideModelColumn}
                  hiddenModelColumns={hiddenModelColumns}
                  updateInputAndRun={updateInputAndRun}
                  setVersionIdForCode={setVersionIdForCode}
                  setRunIdForModal={setRunIdForModal}
                />
              </div>
            </div>
            <div className='fixed bottom-0 left-0 right-0 z-10 bg-white border-t border-gray-200 p-4 sm:hidden flex w-full'>
              <RunAgentsButton
                showSaveAllVersions={false}
                areTasksRunning={areTasksRunning}
                inputLoading={false}
                areInstructionsLoading={false}
                onSaveAllVersions={onSaveAllVersions}
                onTryPromptClick={onPerformRuns}
                onStopAllRuns={stopAllRuns}
                className='flex w-full'
              />
            </div>
            {runIdForModal && (
              <TaskRunModal
                tenant={tenant}
                onClose={() => setRunIdForModal(undefined)}
                open={!!runIdForModal}
                taskId={taskId}
                taskRunId={runIdForModal}
                taskRunIds={filteredRunIds}
                taskSchemaIdFromParams={schemaId}
              />
            )}
          </div>
        </PageContainer>
      </div>
      {shouldShowChat && (
        <PlaygroundChat
          tenant={tenant}
          taskId={taskId}
          schemaId={schemaId}
          playgroundState={playgroundState}
          onShowEditSchemaModal={() => {}}
          improveInstructions={() => Promise.resolve()}
          improveVersionMessages={onImproveVersionMessagesFromChat}
          changeModels={onChatRequestToChangeModels}
          generateNewInput={() => Promise.resolve()}
          onCancelChatToolCallOnPlayground={onCancelChatRequest}
          scrollToInput={() => performScroll('proxy-scroll-view', 'top')}
          scrollToOutput={() => performScroll('proxy-scroll-view', 'bottom')}
          isProxy={true}
        />
      )}
      <CodeModal tenant={tenant} taskId={taskId} versionId={versionIdForCode} setVersionId={setVersionIdForCode} />
    </div>
  );
}
