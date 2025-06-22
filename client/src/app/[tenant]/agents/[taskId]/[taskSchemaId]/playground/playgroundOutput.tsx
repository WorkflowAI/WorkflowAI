'use client';

import { ColumnDoubleCompare20Filled, ColumnDoubleCompare20Regular } from '@fluentui/react-icons';
import { isEqual } from 'lodash';
import { Plus } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { AIModelCombobox } from '@/components/AIModelsCombobox/aiModelCombobox';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useRedirectWithParams } from '@/lib/queryString';
import { useOrFetchOrganizationSettings } from '@/store';
import { GeneralizedTaskInput, JsonSchema } from '@/types';
import { Model, TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { ModelResponse, RunV1, VersionV1 } from '@/types/workflowAI';
import { TaskInputDict } from '@/types/workflowAI';
import { FreeCreditsLimitReachedInfo } from './FreeCreditsLimitReachedInfo';
import { CreateTaskRunButton } from './components/CreateTaskRunButton';
import { ModelOutputErrorInformation } from './components/ModelOutputErrorInformation';
import { useMinimumCostTaskRun } from './hooks/useMinimumCostTaskRun';
import { useMinimumLatencyTaskRun } from './hooks/useMinimumLatencyTaskRun';
import { TaskRunner } from './hooks/useTaskRunners';
import { PlaygroundModels } from './hooks/utils';
import { PlaygroundModelOutputContent } from './playgroundModelOutputContent';

function computeHasInputChanged(taskRun: RunV1 | undefined, generatedInput: GeneralizedTaskInput | undefined) {
  if (taskRun === undefined || generatedInput === undefined) {
    return false;
  }

  // We need to remove undefined values from the generated input
  const processedGeneratedInput = JSON.parse(JSON.stringify(generatedInput));
  return !isEqual(taskRun.task_input, processedGeneratedInput);
}

type ModelOutputProps = {
  version: VersionV1 | undefined;
  aiModels: ModelResponse[];
  areInstructionsLoading: boolean;
  errorForModels: Omit<Map<string, Error>, 'set' | 'clear' | 'delete'>;
  generatedInput: GeneralizedTaskInput | undefined;
  improveInstructions: (text: string, runId: string | undefined) => Promise<void>;
  index: number;
  minimumCostTaskRun: RunV1 | undefined;
  minimumLatencyTaskRun: RunV1 | undefined;
  models: PlaygroundModels;
  onModelsChange: (index: number, newModel: Model | null | undefined) => void;
  outputSchema: JsonSchema | undefined;
  referenceValue: Record<string, unknown> | undefined;
  onShowEditDescriptionModal: () => void;
  onShowEditSchemaModal: () => void;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  taskRunner: TaskRunner;
  tenant: TenantID | undefined;
  isInDemoMode: boolean;
  isHideModelColumnAvaible: boolean;
  hideModelColumn: () => void;
  updateInputAndRun: (input: TaskInputDict) => Promise<void>;
  isProxy: boolean;
};

function ModelOutput(props: ModelOutputProps) {
  const {
    aiModels,
    areInstructionsLoading,
    errorForModels,
    generatedInput,
    improveInstructions,
    index,
    minimumCostTaskRun,
    minimumLatencyTaskRun,
    models,
    onModelsChange,
    outputSchema,
    referenceValue,
    onShowEditDescriptionModal,
    taskId,
    taskSchemaId,
    taskRunner,
    tenant,
    version,
    isInDemoMode,
    isHideModelColumnAvaible,
    hideModelColumn,
    updateInputAndRun,
    isProxy,
  } = props;

  const taskRun = taskRunner.data;
  const runId = taskRun?.id;
  const hasInputChanged = useMemo(() => {
    if (isProxy) {
      return false;
    }
    return computeHasInputChanged(taskRun, generatedInput);
  }, [taskRun, generatedInput, isProxy]);

  const redirectWithParams = useRedirectWithParams();
  const onOpenTaskRun = useCallback(() => {
    redirectWithParams({
      params: { runId },
      scroll: false,
    });
  }, [runId, redirectWithParams]);

  const currentModel = models[index];
  const currentAIModel = useMemo(
    () => aiModels.find((model) => model.id === taskRun?.version.properties?.model),
    [aiModels, taskRun?.version.properties?.model]
  );
  const minimumCostAIModel = useMemo(
    () => aiModels.find((model) => model.id === minimumCostTaskRun?.version.properties?.model),
    [aiModels, minimumCostTaskRun?.version.properties?.model]
  );

  const onImprovePrompt = useCallback(
    async (evaluation: string) => {
      if (!runId) return;
      await improveInstructions(evaluation, runId);
    },
    [runId, improveInstructions]
  );

  const handleModelChange = useCallback(
    (value: Model) => {
      onModelsChange(index, value);
    },
    [index, onModelsChange]
  );

  const taskOutput = useMemo(() => {
    const taskRunOutput = taskRun?.task_output;
    if (hasInputChanged) {
      return undefined;
    }
    return taskRunOutput || taskRunner.streamingOutput;
  }, [taskRun?.task_output, taskRunner.streamingOutput, hasInputChanged]);

  const errorForModel = useMemo(() => {
    if (!currentModel) {
      return undefined;
    }
    return errorForModels.get(currentModel) || undefined;
  }, [currentModel, errorForModels]);

  const [openModelCombobox, setOpenModelCombobox] = useState(false);

  return (
    <div className='flex flex-col sm:flex-1 sm:w-1/3 pt-3 pb-2 sm:pb-4 justify-between overflow-hidden'>
      <div className='flex flex-col w-full'>
        <div className='flex items-center gap-2 justify-between px-2'>
          <AIModelCombobox
            value={currentModel || ''}
            onModelChange={handleModelChange}
            models={aiModels}
            noOptionsMessage='Choose Model'
            fitToContent={false}
            open={openModelCombobox}
            setOpen={setOpenModelCombobox}
            isProxy={isProxy}
            taskId={taskId}
          />
          <CreateTaskRunButton
            taskRunner={taskRunner}
            disabled={areInstructionsLoading}
            containsError={!!errorForModel}
          />
        </div>
      </div>
      <div className='flex flex-col w-full sm:flex-1 overflow-hidden'>
        {!!errorForModel ? (
          <ModelOutputErrorInformation
            errorForModel={errorForModel}
            onOpenChangeModalPopover={() => setOpenModelCombobox(true)}
          />
        ) : (
          <div className='flex flex-col w-full sm:flex-1 px-2 overflow-hidden'>
            <PlaygroundModelOutputContent
              currentAIModel={currentAIModel}
              minimumCostAIModel={minimumCostAIModel}
              hasInputChanged={hasInputChanged}
              minimumCostTaskRun={minimumCostTaskRun}
              minimumLatencyTaskRun={minimumLatencyTaskRun}
              onOpenTaskRun={onOpenTaskRun}
              onImprovePrompt={onImprovePrompt}
              outputSchema={outputSchema}
              referenceValue={referenceValue}
              onShowEditDescriptionModal={onShowEditDescriptionModal}
              version={version}
              taskOutput={taskOutput}
              taskRun={taskRun}
              taskSchemaId={taskSchemaId}
              tenant={tenant}
              taskId={taskId}
              streamLoading={!!taskRunner.streamingOutput}
              toolCalls={taskRunner.toolCalls}
              reasoningSteps={taskRunner.reasoningSteps}
              isInDemoMode={isInDemoMode}
              isHideModelColumnAvaible={isHideModelColumnAvaible}
              hideModelColumn={hideModelColumn}
              updateInputAndRun={updateInputAndRun}
              isProxy={isProxy}
            />
          </div>
        )}
      </div>
    </div>
  );
}

type PlaygroundOutputProps = Pick<
  ModelOutputProps,
  | 'aiModels'
  | 'areInstructionsLoading'
  | 'errorForModels'
  | 'generatedInput'
  | 'improveInstructions'
  | 'models'
  | 'onModelsChange'
  | 'outputSchema'
  | 'onShowEditDescriptionModal'
  | 'onShowEditSchemaModal'
  | 'taskId'
  | 'tenant'
  | 'taskSchemaId'
> & {
  taskRunners: [TaskRunner, TaskRunner, TaskRunner];
  versionsForRuns: Record<string, VersionV1>;
  showDiffMode: boolean;
  setShowDiffMode: (showDiffMode: boolean) => void;
  maxHeight: number | undefined;
  isInDemoMode: boolean;
  addModelColumn: () => void;
  hideModelColumn: (index: number) => void;
  hiddenModelColumns: number[] | undefined;
  isProxy: boolean;
  updateInputAndRun: (input: TaskInputDict) => Promise<void>;
};

export function PlaygroundOutput(props: PlaygroundOutputProps) {
  const {
    taskRunners,
    versionsForRuns,
    showDiffMode,
    setShowDiffMode,
    addModelColumn,
    hideModelColumn,
    onShowEditDescriptionModal,
    onShowEditSchemaModal,
    maxHeight,
    isInDemoMode,
    hiddenModelColumns,
    isProxy,
    updateInputAndRun,
    ...rest
  } = props;

  const toggleShowDiffMode = useCallback(() => {
    setShowDiffMode(!showDiffMode);
  }, [showDiffMode, setShowDiffMode]);

  const { result: filteredTaskRunners, indexesDict } = useMemo(() => {
    const indexesDict = new Map<number, number>();
    const result: TaskRunner[] = [];

    taskRunners.forEach((taskRunner, index) => {
      if (hiddenModelColumns?.includes(index)) {
        return;
      }

      result.push(taskRunner);
      indexesDict.set(result.length - 1, index);
    });

    return { result, indexesDict };
  }, [taskRunners, hiddenModelColumns]);

  const referenceValue = useMemo(() => {
    if (!showDiffMode) {
      return undefined;
    }
    return filteredTaskRunners[0].data?.task_output;
  }, [filteredTaskRunners, showDiffMode]);

  const isHideModelColumnAvaible = useMemo(() => {
    return filteredTaskRunners.length > 1;
  }, [filteredTaskRunners]);

  const isAddModelColumnAvaible = useMemo(() => {
    return filteredTaskRunners.length < 3;
  }, [filteredTaskRunners]);

  const taskRuns = useMemo(() => {
    const result: RunV1[] = [];
    for (const taskRunner of filteredTaskRunners) {
      if (taskRunner.data) {
        result.push(taskRunner.data);
      }
    }
    return result;
  }, [filteredTaskRunners]);

  const minimumCostTaskRun = useMinimumCostTaskRun(taskRuns);
  const minimumLatencyTaskRun = useMinimumLatencyTaskRun(taskRuns);

  const onOutputsClick = useCallback(() => {
    onShowEditSchemaModal();
  }, [onShowEditSchemaModal]);

  const { isLoggedOut } = useDemoMode();
  const { noCreditsLeft } = useOrFetchOrganizationSettings(isLoggedOut ? 30000 : undefined);

  const shouldShowFreeCreditsLimitReachedInfo = useMemo(() => {
    if (!isLoggedOut) {
      return false;
    }
    return noCreditsLeft;
  }, [noCreditsLeft, isLoggedOut]);

  const [isHoveringOverHeader, setIsHoveringOverHeader] = useState(false);

  const notFilteredIndex = useCallback(
    (index: number) => {
      const allTaskRunnersIndex = indexesDict.get(index);
      if (allTaskRunnersIndex === undefined) {
        return index;
      }
      return allTaskRunnersIndex;
    },
    [indexesDict]
  );

  const onHideModelColumn = useCallback(
    (index: number) => {
      const allTaskRunnersIndex = indexesDict.get(index);
      if (allTaskRunnersIndex === undefined) {
        return;
      }
      hideModelColumn(allTaskRunnersIndex);
    },
    [hideModelColumn, indexesDict]
  );

  return (
    <div className='flex flex-col w-full overflow-hidden' style={maxHeight ? { maxHeight } : undefined}>
      <div
        className='w-full flex items-center justify-between px-4 h-[50px] shrink-0 border-b border-dashed border-gray-200'
        onMouseEnter={() => setIsHoveringOverHeader(true)}
        onMouseLeave={() => setIsHoveringOverHeader(false)}
      >
        <div className='flex flex-row items-center gap-3.5'>
          <div className='font-semibold text-gray-700 text-base'>{isProxy ? 'Assistant Messages' : 'Outputs'}</div>

          {isHoveringOverHeader && !isProxy && (
            <Button
              variant='newDesign'
              onClick={onOutputsClick}
              className='h-7 px-2 text-xs'
              size='none'
              disabled={isInDemoMode}
            >
              Edit Schema
            </Button>
          )}
        </div>
        <div className='flex items-center gap-2'>
          <SimpleTooltip content={showDiffMode ? 'Hide differences' : 'Show differences'}>
            <Button
              className='w-7 h-7'
              variant='newDesign'
              size='none'
              icon={showDiffMode ? <ColumnDoubleCompare20Filled /> : <ColumnDoubleCompare20Regular />}
              onClick={toggleShowDiffMode}
            />
          </SimpleTooltip>
          <Button
            className='sm:flex hidden'
            variant='newDesign'
            size='sm'
            icon={<Plus className='h-4 w-4' strokeWidth={2} />}
            onClick={addModelColumn}
            disabled={!isAddModelColumnAvaible}
          >
            Add Model
          </Button>
        </div>
      </div>
      {shouldShowFreeCreditsLimitReachedInfo ? (
        <div className='flex w-full h-[250px] items-center justify-center'>
          <FreeCreditsLimitReachedInfo />
        </div>
      ) : (
        <div className='flex flex-col sm:flex-row sm:flex-1 px-2 overflow-hidden'>
          {filteredTaskRunners.map((taskRunner, index) => (
            <ModelOutput
              {...rest}
              version={!!taskRunner.data?.version.id ? versionsForRuns[taskRunner.data?.version.id] : undefined}
              index={notFilteredIndex(index)}
              key={`${taskRunner.data?.id}-${notFilteredIndex(index)}`}
              minimumCostTaskRun={minimumCostTaskRun}
              minimumLatencyTaskRun={minimumLatencyTaskRun}
              taskRunner={taskRunner}
              referenceValue={index > 0 ? referenceValue : undefined}
              onShowEditDescriptionModal={onShowEditDescriptionModal}
              onShowEditSchemaModal={onShowEditSchemaModal}
              isInDemoMode={isInDemoMode}
              isHideModelColumnAvaible={isHideModelColumnAvaible}
              hideModelColumn={() => onHideModelColumn(index)}
              updateInputAndRun={updateInputAndRun}
              isProxy={isProxy}
            />
          ))}
        </div>
      )}
    </div>
  );
}
