import { useMemo } from 'react';
import { ProxyTools } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/parameters-section/ProxyTools';
import { ProxyMessagesView } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/proxy-messages/ProxyMessagesView';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { TaskModelBadge } from '@/components/v2/TaskModelBadge';
import { TaskTemperatureBadge } from '@/components/v2/TaskTemperatureBadge';
import { ProxyMessage, VersionV1 } from '@/types/workflowAI';
import { ProxyRunDetailsParameterEntry } from './ProxyRunDetailsParameterEntry';

type Props = {
  version: VersionV1;
};

export function ProxyRunDetailsVersionMessagesView(props: Props) {
  const { version } = props;

  const messages = useMemo(() => {
    if (!version) {
      return undefined;
    }
    return version.properties.messages as ProxyMessage[];
  }, [version]);

  return (
    <div className='flex flex-col h-full w-full overflow-hidden'>
      <div className='flex w-full h-12 border-b border-dashed border-gray-200 items-center px-4'>
        <div className='text-[16px] font-semibold text-gray-700'>Version Details</div>
      </div>
      <div className='flex w-full max-h-[calc(100%-48px)] overflow-hidden p-4'>
        <div className='flex flex-col w-full h-full overflow-hidden bg-white rounded-[2px] border border-gray-200'>
          <ProxyRunDetailsParameterEntry title='Version' className='border-b border-gray-100'>
            <TaskVersionBadgeContainer version={version} side='top' showDetails={false} />
          </ProxyRunDetailsParameterEntry>

          <div className='grid grid-cols-[repeat(auto-fit,minmax(max(160px,50%),1fr))] [&>*]:border-gray-100 [&>*]:border-b [&>*:nth-child(odd)]:border-r'>
            <ProxyRunDetailsParameterEntry title='Temperature' className='border-b border-gray-100'>
              <TaskTemperatureBadge temperature={version.properties.temperature} />
            </ProxyRunDetailsParameterEntry>
            <div className='flex items-center border-b border-gray-100 px-3'>
              <TaskModelBadge
                model={version.properties.model_name}
                providerId={version.properties.provider}
                modelIcon={version.properties.model_icon}
              />
            </div>
            <ProxyRunDetailsParameterEntry title='Max Tokens' className='border-b border-gray-100'>
              {!!version.properties.max_tokens ? (
                <div className='text-[13px] text-gray-700 px-2 py-0.5 border border-gray-200 rounded-[2px]'>
                  {version.properties.max_tokens}
                </div>
              ) : (
                <div className='text-[16px] text-gray-400 pr-2'>-</div>
              )}
            </ProxyRunDetailsParameterEntry>
            <ProxyRunDetailsParameterEntry title='Top P' className='border-b border-gray-100'>
              {!!version.properties.top_p ? (
                <div className='text-[13px] text-gray-700 px-2 py-0.5 border border-gray-200 rounded-[2px]'>
                  {version.properties.top_p}
                </div>
              ) : (
                <div className='text-[16px] text-gray-400 pr-2'>-</div>
              )}
            </ProxyRunDetailsParameterEntry>
          </div>

          {!!messages && messages.length > 0 && (
            <div className='flex flex-col w-full overflow-y-auto border-b border-gray-100'>
              <ProxyMessagesView messages={messages} className='flex w-full h-max px-4 py-3' />
            </div>
          )}

          <div className='flex flex-col w-full px-4 py-2 gap-1'>
            <div className='text-[13px] text-gray-500'>Available Tools</div>
            {version?.properties.enabled_tools ? (
              <ProxyTools toolCalls={version?.properties.enabled_tools} isReadonly />
            ) : (
              <div className='text-[13px] text-gray-400'>none</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
