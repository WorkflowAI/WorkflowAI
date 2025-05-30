import { HoverCardContentProps } from '@radix-ui/react-hover-card';
import { TaskModelBadge } from '@/components/TaskModelBadge';
import { TaskTemperatureBadge } from '@/components/v2/TaskTemperatureBadge';
import { ContextWindowInformation } from '@/lib/taskRunUtils';
import { ModelResponse, RunV1, VersionV1 } from '@/types/workflowAI';
import { BaseOutputValueRow } from './BaseOutputValueRow';
import { ContextWindowOutputValueRow } from './ContextWindowOutputValueRow';
import { LatencyOutputValueRow } from './LatencyOutputValueRow';
import { PriceOutputValueRow } from './PriceOutputValueRow';
import { VersionOutputValueRow } from './VersionOutputValueRow';

type AdditionalFieldsProps = {
  showAllFields: boolean;
  model?: string | null;
  provider?: string | null;
  temperature?: number | null;
};

function AdditionalFields({ showAllFields, model, provider, temperature }: AdditionalFieldsProps) {
  if (!showAllFields) return null;

  return (
    <>
      {model && (
        <div className='flex h-10 items-center pl-4'>
          <TaskModelBadge model={model} providerId={provider} />
        </div>
      )}

      {temperature !== undefined && temperature !== null && (
        <div className='flex h-10'>
          <BaseOutputValueRow label='Temperature' value={<TaskTemperatureBadge temperature={temperature} />} />
        </div>
      )}
    </>
  );
}

type TaskRunOutputRowsProps = {
  currentAIModel: ModelResponse | undefined;
  minimumCostAIModel: ModelResponse | undefined;
  taskRun: RunV1 | undefined;
  contextWindowInformation: ContextWindowInformation | undefined;
  minimumLatencyTaskRun: RunV1 | undefined;
  minimumCostTaskRun: RunV1 | undefined;
  showVersion?: boolean;
  showAllFields?: boolean;
  side?: HoverCardContentProps['side'];
  showTaskIterationDetails?: boolean;
  version: VersionV1 | undefined;
  setVersionIdForCode?: (versionId: string | undefined) => void;
};

export function TaskRunOutputRows({
  currentAIModel,
  minimumCostAIModel,
  taskRun,
  version,
  minimumLatencyTaskRun,
  minimumCostTaskRun,
  showVersion = true,
  contextWindowInformation,
  showAllFields = false,
  side,
  showTaskIterationDetails = false,
  setVersionIdForCode,
}: TaskRunOutputRowsProps) {
  const properties = version?.properties;
  const { temperature, instructions, model, provider } = properties ?? {};

  return (
    <div className='flex flex-col'>
      <div className='grid grid-cols-[repeat(auto-fit,minmax(max(160px,50%),1fr))] [&>*]:border-gray-100 [&>*]:border-b [&>*:nth-child(odd)]:border-r'>
        {showVersion && (
          <div className='flex h-10'>
            <VersionOutputValueRow
              version={version}
              side={side}
              showTaskIterationDetails={showTaskIterationDetails}
              setVersionIdForCode={setVersionIdForCode}
            />
          </div>
        )}
        <div className='flex h-10'>
          <PriceOutputValueRow
            currentAIModel={currentAIModel}
            minimumCostAIModel={minimumCostAIModel}
            taskRun={taskRun}
            minimumCostTaskRun={minimumCostTaskRun}
          />
        </div>
        <div className='flex h-10'>
          <LatencyOutputValueRow
            currentAIModel={currentAIModel}
            minimumCostAIModel={minimumCostAIModel}
            taskRun={taskRun}
            minimumLatencyTaskRun={minimumLatencyTaskRun}
          />
        </div>
        <div className='flex h-10'>
          <ContextWindowOutputValueRow isInitialized={!!taskRun} contextWindowInformation={contextWindowInformation} />
        </div>
        <AdditionalFields showAllFields={showAllFields} model={model} provider={provider} temperature={temperature} />
      </div>

      {showAllFields && !!instructions && (
        <div className='flex flex-col w-full items-top px-4 py-2 gap-2'>
          <div className='text-[13px] font-normal text-gray-500'>Instructions</div>
          <div className='flex flex-col'>
            <div
              className={`flex flex-1 text-gray-700 bg-white p-2 border border-gray-200 rounded-[2px] font-lato font-normal text-[13px]`}
              style={{
                maxHeight: '200px',
              }}
            >
              <div className={'flex whitespace-pre-line overflow-y-auto w-full'}>{instructions}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
