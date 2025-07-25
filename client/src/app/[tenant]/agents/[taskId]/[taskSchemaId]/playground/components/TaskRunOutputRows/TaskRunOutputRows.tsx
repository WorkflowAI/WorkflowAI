import { HoverCardContentProps } from '@radix-ui/react-hover-card';
import { useMemo } from 'react';
import { TaskModelBadge } from '@/components/TaskModelBadge';
import { TaskTemperatureBadge } from '@/components/v2/TaskTemperatureBadge';
import { LEGACY_TASK_RUN_RUN_BY_METADATA_KEY, WORKFLOW_AI_METADATA_PREFIX } from '@/lib/constants';
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
  filteredMetadata?: [string, unknown][];
  // Old playground only supports reasoning_effort
  reasoning_effort?: string | null;
};

function renderMetadataValue(value: unknown): React.ReactNode {
  if (value === null) return <span className='text-gray-400 text-[12px]'>null</span>;
  if (value === undefined) return <span className='text-gray-400 text-[12px]'>undefined</span>;
  if (typeof value === 'object') {
    let json: string;
    try {
      json = JSON.stringify(value, null, 2);
    } catch (err) {
      return (
        <span className='text-red-400'>
          Unserializable object{err instanceof Error && err.message ? `: ${err.message}` : ''}
        </span>
      );
    }
    return <div className='text-[12px] p-1 overflow-x-auto max-w-full whitespace-pre-wrap'>{json}</div>;
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return value;
  if (typeof value === 'string') return value;
  return '';
}

function AdditionalFields({ showAllFields, model, provider, temperature, filteredMetadata }: AdditionalFieldsProps) {
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

      {filteredMetadata?.map(([key, value]) => (
        <div className='flex min-h-10 items-center' key={key}>
          <BaseOutputValueRow label={key} value={renderMetadataValue(value)} />
        </div>
      ))}
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
  const { temperature, instructions, model, provider, reasoning_effort } = properties ?? {};

  const filteredMetadata = useMemo(() => {
    if (!taskRun?.metadata) {
      return undefined;
    }
    const filtered = Object.entries(taskRun.metadata).filter(
      ([key]) => !key.startsWith(WORKFLOW_AI_METADATA_PREFIX) && !key.startsWith(LEGACY_TASK_RUN_RUN_BY_METADATA_KEY)
    );

    return filtered.length > 0 ? filtered : undefined;
  }, [taskRun?.metadata]);

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
        <AdditionalFields
          showAllFields={showAllFields}
          model={model}
          provider={provider}
          temperature={temperature}
          filteredMetadata={filteredMetadata}
          reasoning_effort={reasoning_effort}
        />
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
