import { ProxyMessagesView } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/proxy-messages/ProxyMessagesView';
import { ProxyMessage, VersionV1 } from '@/types/workflowAI';
import { TaskTemperatureBadge } from './TaskTemperatureBadge';

type TaskMetadataSectionProps = {
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export function TaskMetadataSection(props: TaskMetadataSectionProps) {
  const { title, children, footer } = props;

  return (
    <div className='flex flex-col gap-2 px-4 py-1.5 font-lato'>
      <div className='flex flex-col gap-1'>
        <div className='text-[13px] font-medium text-gray-900 capitalize'>{title}</div>
        <div className='flex-1 flex justify-start overflow-hidden'>
          <div className='truncate'>{children}</div>
        </div>
      </div>
      {footer}
    </div>
  );
}

type Props = {
  version: VersionV1;
};

export function ProxyMajorVersionDetails(props: Props) {
  const { version } = props;

  const properties = version?.properties;
  const { temperature, instructions, messages } = properties;

  return (
    <div className='flex flex-col w-full pb-1.5 bg-white'>
      <div className='flex flex-row gap-2 items-center justify-between border-b border-gray-200 border-dashed h-11 px-4 mb-2'>
        <div className='text-[15px] font-semibold text-gray-700'>Version Preview</div>
      </div>

      {!!instructions && (
        <div className='flex flex-col w-full items-top pl-4 pr-4 py-1.5 gap-1'>
          <div className='text-[13px] font-medium text-gray-800'>Instructions</div>
          <div>
            <div
              className={`flex-1 text-gray-900 bg-white px-3 py-2 border border-gray-300 rounded-[2px] overflow-auto font-lato font-normal text-[13px]`}
              style={{
                maxHeight: 250,
              }}
            >
              <p className='whitespace-pre-line'>{instructions}</p>
            </div>
          </div>
        </div>
      )}

      {!!messages && (
        <div className='flex flex-col w-full items-top pl-4 pr-4 py-1.5 gap-1'>
          <div className='text-[13px] font-medium text-gray-800'>Messages</div>
          <div className='flex flex-col w-full max-h-[400px] overflow-y-auto'>
            <ProxyMessagesView messages={messages as ProxyMessage[]} />
          </div>
        </div>
      )}

      <div className='grid grid-cols-3'>
        {temperature !== undefined && temperature !== null && (
          <TaskMetadataSection title='temperature'>
            <TaskTemperatureBadge temperature={temperature} />
          </TaskMetadataSection>
        )}
      </div>
    </div>
  );
}
