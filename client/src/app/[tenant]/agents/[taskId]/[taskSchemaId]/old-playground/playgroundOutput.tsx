'use client';

import {
  ColumnDoubleCompare20Filled,
  ColumnDoubleCompare20Regular,
  LayoutColumnThree20Regular,
  LayoutColumnTwo20Regular,
} from '@fluentui/react-icons';
import { isEqual } from 'lodash';
import { useCallback, useMemo, useState } from 'react';
import { AIModelCombobox } from '@/components/AIModelsCombobox/aiModelCombobox';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useRedirectWithParams } from '@/lib/queryString';
import { useOrFetchOrganizationSettings } from '@/store';
import { GeneralizedTaskInput, JsonSchema, TaskRun } from '@/types';
import { Model, TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { ModelResponse, VersionV1 } from '@/types/workflowAI';
import { FreeCreditsLimitReachedInfo } from './FreeCreditsLimitReachedInfo';
import { CreateTaskRunButton } from './components/CreateTaskRunButton';
import { ModelOutputErrorInformation } from './components/ModelOutputErrorInformation';
import { useMinimumCostTaskRun } from './hooks/useMinimumCostTaskRun';
import { useMinimumLatencyTaskRun } from './hooks/useMinimumLatencyTaskRun';
import { TaskRunner } from './hooks/useTaskRunners';
import { PlaygroundModels } from './hooks/utils';
import { PlaygroundModelOutputContent } from './playgroundModelOutputContent';

function computeHasInputChanged(taskRun: TaskRun | undefined, generatedInput: GeneralizedTaskInput | undefined) {
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
  minimumCostTaskRun: TaskRun | undefined;
  minimumLatencyTaskRun: TaskRun | undefined;
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
  } = props;

  const taskRun = taskRunner.data;
  const taskRunId = taskRun?.id;
  const hasInputChanged = useMemo(() => computeHasInputChanged(taskRun, generatedInput), [taskRun, generatedInput]);

  const redirectWithParams = useRedirectWithParams();
  const onOpenTaskRun = useCallback(() => {
    redirectWithParams({
      params: { taskRunId },
      scroll: false,
    });
  }, [taskRunId, redirectWithParams]);

  const currentModel = models[index];
  const currentAIModel = useMemo(
    () => aiModels.find((model) => model.id === taskRun?.group.properties?.model),
    [aiModels, taskRun?.group.properties?.model]
  );
  const minimumCostAIModel = useMemo(
    () => aiModels.find((model) => model.id === minimumCostTaskRun?.group.properties?.model),
    [aiModels, minimumCostTaskRun?.group.properties?.model]
  );

  const onImprovePrompt = useCallback(
    async (evaluation: string) => {
      if (!taskRunId) return;
      await improveInstructions(evaluation, taskRunId);
    },
    [taskRunId, improveInstructions]
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
  show2ColumnLayout: boolean;
  setShowDiffMode: (showDiffMode: boolean) => void;
  setShow2ColumnLayout: (show2ColumnLayout: boolean) => void;
  maxHeight: number | undefined;
  isInDemoMode: boolean;
};

export function PlaygroundOutput(props: PlaygroundOutputProps) {
  const {
    taskRunners,
    versionsForRuns,
    showDiffMode,
    show2ColumnLayout,
    setShowDiffMode,
    setShow2ColumnLayout,
    onShowEditDescriptionModal,
    onShowEditSchemaModal,
    maxHeight,
    isInDemoMode,
    ...rest
  } = props;

  const toggleShowDiffMode = useCallback(() => {
    setShowDiffMode(!showDiffMode);
  }, [showDiffMode, setShowDiffMode]);
  const toggleShow2ColumnLayout = useCallback(() => {
    setShow2ColumnLayout(!show2ColumnLayout);
  }, [show2ColumnLayout, setShow2ColumnLayout]);

  const referenceValue = useMemo(() => {
    if (!showDiffMode) {
      return undefined;
    }
    return taskRunners[0].data?.task_output;
  }, [taskRunners, showDiffMode]);

  const filteredTaskRunners = useMemo(() => {
    if (show2ColumnLayout) {
      return [taskRunners[0], taskRunners[1]];
    }
    return taskRunners;
  }, [taskRunners, show2ColumnLayout]);

  const taskRuns = useMemo(() => [taskRunners[0].data, taskRunners[1].data, taskRunners[2].data], [taskRunners]);
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
  return (
    <div className='flex flex-col w-full overflow-hidden' style={{ maxHeight }}>
      <div
        className='w-full flex items-center justify-between px-4 h-[50px] shrink-0 border-b border-dashed border-gray-200'
        onMouseEnter={() => setIsHoveringOverHeader(true)}
        onMouseLeave={() => setIsHoveringOverHeader(false)}
      >
        <div className='flex flex-row items-center gap-3.5'>
          <div className='font-semibold text-gray-700 text-base'>Outputs</div>

          {isHoveringOverHeader && (
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
          <SimpleTooltip content={show2ColumnLayout ? 'Show third column' : 'Hide third column'}>
            <Button
              className='w-7 h-7 sm:block hidden'
              variant='newDesign'
              size='none'
              icon={show2ColumnLayout ? <LayoutColumnThree20Regular /> : <LayoutColumnTwo20Regular />}
              onClick={toggleShow2ColumnLayout}
            />
          </SimpleTooltip>
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
              version={!!taskRunner.data?.group.id ? versionsForRuns[taskRunner.data?.group.id] : undefined}
              index={index}
              key={`${taskRunner.data?.id}-${index}`}
              minimumCostTaskRun={minimumCostTaskRun}
              minimumLatencyTaskRun={minimumLatencyTaskRun}
              taskRunner={taskRunner}
              referenceValue={index > 0 ? referenceValue : undefined}
              onShowEditDescriptionModal={onShowEditDescriptionModal}
              onShowEditSchemaModal={onShowEditSchemaModal}
              isInDemoMode={isInDemoMode}
            />
          ))}
        </div>
      )}
    </div>
  );
}
