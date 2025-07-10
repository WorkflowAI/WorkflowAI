import { formatRelativeTime } from '@/lib/formatters/timeFormatter';
import { Annotation } from '@/types/workflowAI/models';

type Props = {
  annotation: Annotation;
};

export function ExistingAnnotationView(props: Props) {
  const { annotation } = props;
  return (
    <div className='flex flex-col p-2 border border-gray-200 rounded-[2px] bg-white'>
      <div className='flex flex-row gap-2'>
        <div className='w-4 h-4 bg-gray-200 rounded-full mt-[1px]' />
        <div className='flex flex-col gap-1'>
          <div className='flex flex-row text-gray-700 text-[12px] font-medium gap-2'>
            <div>{annotation.user}</div>
            <div className='text-gray-400 text-[12px]'>{formatRelativeTime(annotation.timestamp)}</div>
          </div>
          <div className='text-gray-700 text-[13px] whitespace-pre-wrap flex w-full'>{annotation.comment}</div>
        </div>
      </div>
    </div>
  );
}
