import { TaskTemperatureView } from '@/components/v2/TaskTemperatureBadge';
import { MajorVersion } from '@/types/workflowAI';

type MajorVersionDetailsProps = {
  majorVersion: MajorVersion;
};

export function MajorVersionDetails(props: MajorVersionDetailsProps) {
  const { majorVersion } = props;

  return (
    <div className='flex flex-col w-[356px] overflow-hidden'>
      <div className='text-gray-700 text-[16px] font-semibold px-4 py-3 border-b border-gray-200 border-dashed'>
        Preview
      </div>
      <div className='flex flex-col flex-1 px-4 pt-2 pb-3 gap-3'>
        <div className='flex flex-col gap-1.5 w-full flex-1 overflow-hidden'>
          <div className='text-gray-900 text-[13px] font-medium flex flex-shrink-0 w-full'>Instructions:</div>
          <div className='text-gray-900 text-[13px] font-normal px-3 py-2 bg-white rounded-[2px] border border-gray-200 whitespace-pre-wrap overflow-y-auto flex w-full max-h-[350px]'>
            {majorVersion.properties.instructions}
          </div>
        </div>
        <div className='flex flex-col gap-0.5'>
          <div className='text-gray-900 text-[13px] font-medium'>Temperature:</div>
          <div>
            <TaskTemperatureView temperature={majorVersion.properties.temperature} className='text-gray-900 gap-0.5' />
          </div>
        </div>
      </div>
    </div>
  );
}
