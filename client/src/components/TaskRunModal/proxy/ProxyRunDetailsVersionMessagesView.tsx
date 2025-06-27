import { useRouter } from 'next/navigation';
import { useCallback, useMemo } from 'react';
import { ProxyTools } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/parameters-section/ProxyTools';
import { ProxyMessagesView } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/proxy-messages/ProxyMessagesView';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { TaskModelBadge } from '@/components/v2/TaskModelBadge';
import { TaskTemperatureBadge } from '@/components/v2/TaskTemperatureBadge';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { taskRunsRoute } from '@/lib/routeFormatter';
import { Params } from '@/lib/routeFormatter';
import { TaskID } from '@/types/aliases';
import { ProxyMessage, RunV1, VersionV1 } from '@/types/workflowAI';
import { FeedbackBoxContainer } from '../FeedbackBox';
import { AdvencedSettingsDetails } from './AdvencedSettingsDetails';
import { ProxyRunDetailsParameterEntry } from './ProxyRunDetailsParameterEntry';

type MetadataEntryProps = {
  title: string;
  value: string;
  onOpenTaskRuns: (key: string, value: string) => void;
};

function MetadataEntry(props: MetadataEntryProps) {
  const { title, value, onOpenTaskRuns } = props;

  return (
    <div className='flex flex-wrap w-full px-4 py-2 gap-2 items-center justify-between'>
      <div className='text-[13px] text-gray-500'>{title}</div>
      <SimpleTooltip content='Search runs with this metadata value' side='top' tooltipDelay={100}>
        <div
          className='text-[13px] text-gray-700 border border-gray-200 rounded-[2px] px-2 py-0.5 cursor-pointer'
          onClick={() => onOpenTaskRuns(title, value)}
        >
          {value}
        </div>
      </SimpleTooltip>
    </div>
  );
}

function stringifyMetadataValue(value: unknown | undefined | null) {
  if (value === undefined || value === null) {
    return 'Empty';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
}

type Props = {
  version: VersionV1;
  run: RunV1;
};

export function ProxyRunDetailsVersionMessagesView(props: Props) {
  const { version, run } = props;
  const { tenant, taskId, taskSchemaId } = useTaskSchemaParams();
  const router = useRouter();

  const messages = useMemo(() => {
    if (!version) {
      return undefined;
    }
    return version.properties.messages as ProxyMessage[];
  }, [version]);

  const metadataEntries: { key: string; value: string }[] = useMemo(() => {
    if (!run.metadata) {
      return [];
    }
    const keys = Object.keys(run.metadata).filter((key) => !key.includes('workflowai.'));
    if (keys.length === 0) {
      return [];
    }
    return keys.map((key) => ({
      key,
      value: stringifyMetadataValue(run.metadata?.[key]),
    }));
  }, [run.metadata]);

  const onOpenTaskRuns = useCallback(
    (key: string, value: string) => {
      const params: Params = {
        field_name: `metadata.${key}`,
        operator: 'contains',
        value: value,
      };

      router.push(taskRunsRoute(tenant, taskId, taskSchemaId, params));
    },
    [router, tenant, taskId, taskSchemaId]
  );

  return (
    <div className='flex flex-col h-full w-full overflow-y-auto'>
      <div className='flex flex-col w-full h-max'>
        <div className='flex w-full h-12 border-b border-dashed border-gray-200 items-center px-4 flex-shrink-0'>
          <div className='text-[16px] font-semibold text-gray-700'>Version Details</div>
        </div>
        <div className='flex flex-col gap-2 w-full overflow-hidden p-4'>
          <div className='flex flex-col w-full h-full overflow-hidden bg-white rounded-[2px] border border-gray-200'>
            <ProxyRunDetailsParameterEntry title='Version' className='border-b border-gray-100'>
              <TaskVersionBadgeContainer version={version} side='top' showDetails={false} />
            </ProxyRunDetailsParameterEntry>

            <div className='grid grid-cols-[repeat(auto-fit,minmax(max(160px,50%),1fr))] [&>*]:border-gray-100 [&>*]:border-b [&>*:nth-child(odd)]:border-r'>
              <ProxyRunDetailsParameterEntry title='Temperature' className='border-b border-gray-100'>
                <TaskTemperatureBadge temperature={version.properties.temperature} />
              </ProxyRunDetailsParameterEntry>
              <div className='flex items-center border-b border-gray-100 px-3 py-2'>
                <TaskModelBadge
                  model={version.properties.model_name}
                  providerId={version.properties.provider}
                  modelIcon={version.properties.model_icon}
                  // Reasoning is hardcoded for now becasue we are wating for the information to be added on the backend side
                  reasoning={'medium'}
                />
              </div>
            </div>

            <AdvencedSettingsDetails version={version} style='table' />

            {!!messages && messages.length > 0 && (
              <div className='flex flex-col w-full overflow-y-auto border-b border-gray-100'>
                <ProxyMessagesView messages={messages} className='flex w-full h-max px-4 py-3' />
              </div>
            )}

            <div className='flex flex-col w-full px-4 py-2 gap-1'>
              <div className='text-[13px] text-gray-500'>Available Tools</div>
              {version?.properties.enabled_tools ? (
                <ProxyTools toolCalls={version?.properties.enabled_tools} isReadonly messages={messages} />
              ) : (
                <div className='text-[13px] text-gray-400'>none</div>
              )}
            </div>
          </div>

          <FeedbackBoxContainer taskRunId={run.id} tenant={tenant} taskId={run.task_id as TaskID} />
        </div>
        {metadataEntries.length > 0 && (
          <>
            <div className='flex w-full h-12 border-b border-t border-dashed border-gray-200 items-center px-4 flex-shrink-0'>
              <div className='text-[16px] font-semibold text-gray-700'>Metadata</div>
            </div>
            <div className='flex w-full px-4 py-3'>
              <div className='flex flex-col w-full h-full overflow-hidden bg-white rounded-[2px] border border-gray-200 [&>*]:border-gray-100 [&>*]:border-b'>
                {metadataEntries.map((entry) => (
                  <MetadataEntry
                    key={entry.key}
                    title={entry.key}
                    value={entry.value}
                    onOpenTaskRuns={onOpenTaskRuns}
                  />
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
