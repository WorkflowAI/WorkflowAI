import { useCallback, useMemo } from 'react';
import { useState } from 'react';
import { ProxyModelCombobox } from '@/components/ProxyModelsCombobox/ProxyModelCombobox';
import { useRedirectWithParams } from '@/lib/queryString';
import { JsonSchema } from '@/types';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { VersionV1 } from '@/types/workflowAI';
import { ModelResponse } from '@/types/workflowAI';
import { TaskInputDict } from '@/types/workflowAI';
import { RunV1 } from '@/types/workflowAI';
import { ModelOutputErrorInformation } from '../../playground/components/ModelOutputErrorInformation';
import { TaskRunner } from '../../playground/hooks/useTaskRunners';
import { ProxyPlaygroundModels, getModelAndReasoning } from '../utils';
import { ProxyModelOutputContent } from './ProxyModelOutputContent';
import { ProxyRunButton } from './ProxyRunButton';

type Props = {
  version: VersionV1 | undefined;
  aiModels: ModelResponse[];
  areInstructionsLoading: boolean;
  errorForModels: Omit<Map<string, Error>, 'set' | 'clear' | 'delete'>;
  index: number;
  minimumCostTaskRun: RunV1 | undefined;
  minimumLatencyTaskRun: RunV1 | undefined;
  models: ProxyPlaygroundModels;
  onModelsChange: (index: number, newModel: string | undefined, newReasoning: string | undefined) => void;
  outputSchema: JsonSchema | undefined;
  referenceValue: Record<string, unknown> | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  taskRunner: TaskRunner;
  tenant: TenantID | undefined;
  isHideModelColumnAvaible: boolean;
  hideModelColumn: () => void;
  updateInputAndRun: (input: TaskInputDict) => Promise<void>;
  setVersionIdForCode: (versionId: string | undefined) => void;
};

export function ProxyModelOutput(props: Props) {
  const {
    aiModels,
    areInstructionsLoading,
    errorForModels,
    index,
    minimumCostTaskRun,
    minimumLatencyTaskRun,
    models,
    onModelsChange,
    outputSchema,
    referenceValue,
    taskId,
    taskSchemaId,
    taskRunner,
    tenant,
    version,
    isHideModelColumnAvaible,
    hideModelColumn,
    updateInputAndRun,
    setVersionIdForCode,
  } = props;

  const taskRun = taskRunner.data;
  const taskRunId = taskRun?.id;

  const redirectWithParams = useRedirectWithParams();
  const onOpenTaskRun = useCallback(() => {
    redirectWithParams({
      params: { taskRunId },
      scroll: false,
    });
  }, [taskRunId, redirectWithParams]);

  const { model: currentModel, reasoning: currentReasoning } = getModelAndReasoning(index, models);
  const currentAIModel = useMemo(
    () => aiModels.find((model) => model.id === taskRun?.version.properties?.model),
    [aiModels, taskRun?.version.properties?.model]
  );
  const minimumCostAIModel = useMemo(
    () => aiModels.find((model) => model.id === minimumCostTaskRun?.version.properties?.model),
    [aiModels, minimumCostTaskRun?.version.properties?.model]
  );

  const handleModelChange = useCallback(
    (value: string) => {
      onModelsChange(index, value, undefined);
    },
    [index, onModelsChange]
  );

  const handleReasoningChange = useCallback(
    (reasoning: string | undefined) => {
      onModelsChange(index, currentModel, reasoning);
    },
    [index, currentModel, onModelsChange]
  );

  const taskOutput = useMemo(() => {
    const taskRunOutput = taskRun?.task_output;
    return taskRunOutput || taskRunner.streamingOutput;
  }, [taskRun?.task_output, taskRunner.streamingOutput]);

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
          <ProxyModelCombobox
            value={currentModel}
            reasoning={currentReasoning}
            onReasoningChange={handleReasoningChange}
            onModelChange={handleModelChange}
            models={aiModels}
            noOptionsMessage='Choose Model'
            fitToContent={false}
            open={openModelCombobox}
            setOpen={setOpenModelCombobox}
            isProxy={true}
            taskId={taskId}
          />
          <ProxyRunButton
            taskRunner={taskRunner}
            disabled={areInstructionsLoading}
            containsError={!!errorForModel}
            version={version}
            tenant={tenant}
            taskId={taskId}
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
            <ProxyModelOutputContent
              currentAIModel={currentAIModel}
              minimumCostAIModel={minimumCostAIModel}
              hasInputChanged={false}
              minimumCostTaskRun={minimumCostTaskRun}
              minimumLatencyTaskRun={minimumLatencyTaskRun}
              onOpenTaskRun={onOpenTaskRun}
              outputSchema={outputSchema}
              referenceValue={referenceValue}
              version={version}
              taskOutput={taskOutput}
              taskRun={taskRun}
              taskSchemaId={taskSchemaId}
              tenant={tenant}
              taskId={taskId}
              streamLoading={!!taskRunner.streamingOutput}
              toolCalls={taskRunner.toolCalls}
              reasoningSteps={taskRunner.reasoningSteps}
              isHideModelColumnAvaible={isHideModelColumnAvaible}
              hideModelColumn={hideModelColumn}
              updateInputAndRun={updateInputAndRun}
              setVersionIdForCode={setVersionIdForCode}
            />
          </div>
        )}
      </div>
    </div>
  );
}
