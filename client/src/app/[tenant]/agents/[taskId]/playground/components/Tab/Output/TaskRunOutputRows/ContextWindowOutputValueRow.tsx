import { ContextWindowProgressBar } from '@/components/ui/ContextWindowProgressBar';
import { ContextWindowInformation } from '@/lib/taskRunUtils';

type ContextWindowOutputValueRowProps = {
  isInitialized: boolean;
  contextWindowInformation: ContextWindowInformation | undefined;
};

export function ContextWindowOutputValueRow(props: ContextWindowOutputValueRowProps) {
  const { contextWindowInformation, isInitialized } = props;

  if (!contextWindowInformation && isInitialized) {
    return null;
  }

  return (
    <div className='flex flex-row justify-between items-center px-4 gap-2 w-full h-full'>
      <div className='text-gray-500 text-[13px] font-normal shrink-0'>Context Window</div>

      {!!contextWindowInformation ? (
        <ContextWindowProgressBar contextWindowInformation={contextWindowInformation} />
      ) : (
        <div className='text-gray-500 text-[13px] font-normal'>-</div>
      )}
    </div>
  );
}
