import { useState } from 'react';
import { AIModelCombobox } from '@/components/AIModelsCombobox/aiModelCombobox';
import { TaskOutputViewer } from '@/components/ObjectViewer/TaskOutputViewer';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { cn } from '@/lib/utils';
import { useOrFetchOrganizationSettings } from '@/store/fetchers';
import { ToolCallPreview } from '@/types';
import { TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { TaskOutput } from '@/types/task_run';
import { ModelResponse, ReasoningStep, RunV1 } from '@/types/workflowAI/models';
import { AIEvaluationReview } from './AIEvaluation/AIEvaluationReview';
import { CreateTaskRunButton } from './CreateTaskRunButton';
import { FreeCreditsLimitReachedInfo } from './FreeCreditsLimitReachedInfo';
import { ImprovePrompt } from './ImprovePrompt';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  modelId: string | undefined;
  compatibleModels: ModelResponse[] | undefined;
  onSelectModel: (model: string) => void;
  onRun: () => void;
  onStopRun: () => void;
  isRunning: boolean;
  isGenerating: boolean;
  errorMessage: string | undefined;
  wasRunSuccessfull: boolean;
  outputSchema: JsonSchema | undefined;
  toolCalls: ToolCallPreview[] | undefined;
  reasoningSteps: ReasoningStep[] | undefined;
  output: TaskOutput | undefined;
  run: RunV1 | undefined;
  onImproveInstructions: (text: string, runId: string | undefined) => Promise<void>;
};

export function PlaygroundOutput(props: Props) {
  const {
    tenant,
    taskId,
    modelId,
    compatibleModels,
    onSelectModel,
    onRun,
    onStopRun,
    isRunning,
    isGenerating,
    errorMessage,
    wasRunSuccessfull,
    outputSchema,
    toolCalls,
    reasoningSteps,
    output,
    run,
    onImproveInstructions,
  } = props;

  const { isLoggedOut } = useDemoMode();
  const { noCreditsLeft } = useOrFetchOrganizationSettings(isLoggedOut ? 30000 : undefined);

  const shouldShowFreeCreditsLimitReachedInfo = isLoggedOut && noCreditsLeft;

  const [openModelCombobox, setOpenModelCombobox] = useState(false);

  const emptyMode = !output;

  return (
    <div className='flex flex-col w-full'>
      <div className='flex flex-row border-b border-gray-200 w-full bg-gray-50 justify-between h-[48px] items-center px-4'>
        <div className='text-gray-700 text-[13px] font-semibold'>Output</div>
      </div>

      {shouldShowFreeCreditsLimitReachedInfo ? (
        <div className='flex w-full h-[250px] items-center justify-center'>
          <FreeCreditsLimitReachedInfo />
        </div>
      ) : (
        <div className='flex flex-col px-4 py-3 overflow-hidden'>
          <div className='flex flex-col w-full'>
            <div className='flex items-center gap-2 justify-between'>
              <AIModelCombobox
                value={modelId || ''}
                onModelChange={onSelectModel}
                models={compatibleModels}
                noOptionsMessage='Choose Model'
                fitToContent={false}
                open={openModelCombobox}
                setOpen={setOpenModelCombobox}
              />

              <CreateTaskRunButton
                onRun={onRun}
                onStopRun={onStopRun}
                isRunning={isRunning}
                disabled={isGenerating}
                containsError={!!errorMessage}
                wasRunSuccessfull={wasRunSuccessfull}
              />
            </div>
          </div>

          <div className='flex flex-col rounded-[2px] overflow-hidden my-3 border border-gray-200'>
            <TaskOutputViewer
              schema={outputSchema}
              value={output}
              defs={outputSchema?.$defs}
              textColor='text-gray-900'
              className={cn(
                'flex w-full border-b border-gray-200 border-dashed bg-white max-h-[400px]',
                !!output && 'min-h-[150px]'
              )}
              showTypes={emptyMode}
              showExamplesHints
              streamLoading={isRunning}
              toolCalls={toolCalls}
              reasoningSteps={reasoningSteps}
              showDescriptionExamples={emptyMode ? 'all' : undefined}
            />
            {!!run && (
              <div className='flex flex-col w-full overflow-hidden max-h-[400px]'>
                <ImprovePrompt onImprovePrompt={(text) => onImproveInstructions(text, run.id)} />

                <AIEvaluationReview
                  tenant={tenant}
                  taskId={taskId}
                  runId={run.id}
                  onImprovePrompt={(text) => onImproveInstructions(text, run.id)}
                  pollingInterval={5000}
                />
              </div>
            )}
            {/* <TaskRunOutputRows
              currentAIModel={model}
              minimumCostAIModel={minimumCostAIModel}
              taskRun={run}
              version={version}
              minimumLatencyTaskRun={minimumLatencyTaskRun}
              minimumCostTaskRun={minimumCostTaskRun}
              showVersion={true}
              contextWindowInformation={contextWindowInformation}
              showTaskIterationDetails={true}
            /> */}
          </div>
        </div>
      )}
    </div>
  );
}
