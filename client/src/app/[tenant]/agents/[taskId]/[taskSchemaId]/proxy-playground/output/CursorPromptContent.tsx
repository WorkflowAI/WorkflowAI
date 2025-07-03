import {
  Add16Regular,
  ArrowCircleUp16Filled,
  ChevronDown16Regular,
  Cloud16Regular,
  Dismiss16Regular,
  History16Regular,
  Image16Regular,
  Mention16Regular,
  MoreHorizontal16Regular,
} from '@fluentui/react-icons';
import { cn } from '@/lib/utils';

type Props = {
  text: string;
  className?: string;
};

export function CursorPromptContent(props: Props) {
  const { text, className } = props;

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <div className='flex w-full justify-between items-center'>
        <div className='text-gray-700 text-[12px] font-medium px-2 py-[3px] bg-gray-200 rounded-[4px]'>New Chat</div>
        <div className='text-gray-900 text-[12px] flex items-center gap-3 px-1'>
          <Add16Regular className='w-4 h-4' />
          <Cloud16Regular className='w-4 h-4' />
          <History16Regular className='w-4 h-4' />
          <MoreHorizontal16Regular className='w-4 h-4' />
          <Dismiss16Regular className='w-3.5 h-3.5' />
        </div>
      </div>
      <div className='flex flex-col gap-2 w-full h-full bg-white rounded-[8px] border border-gray-300 p-2'>
        <div className='flex gap-[3px] py-0.5 px-1 text-gray-500 border border-gray-200 rounded-[4px] text-[11px] font-medium items-center w-fit'>
          <Mention16Regular className='w-3.5 h-3.5' />
          <div className='text-gray-500'>Add Context</div>
        </div>
        <div className='text-gray-800 text-[11px] font-medium px-0.5 pb-3'>{text}</div>
        <div className='flex flex-row justify-between gap-1'>
          <div className='flex flex-row gap-2 items-center'>
            <div className='flex flex-row gap-1 bg-gray-100 rounded-full px-2 py-1 items-center'>
              <div className='text-[13px] font-medium text-gray-400'>∞</div>
              <div className='text-[11px] font-medium text-gray-500'>Agent</div>
              <div className='text-[11px] font-medium text-gray-400'>⌘I</div>
              <ChevronDown16Regular className='w-3 h-3 text-gray-400' />
            </div>
            <div className='flex flex-row gap-1 items-center'>
              <div className='text-indigo-600 text-[11px] font-medium'>claude-4-sonnet</div>
              <div className='text-indigo-600 text-[8px] font-semibold px-[1px] rounded-[2px] border border-1 border-gray-200 mt-[2px]'>
                MAX
              </div>
              <ChevronDown16Regular className='w-3 h-3 text-gray-400' />
            </div>
          </div>
          <div className='flex flex-row gap-2 items-center'>
            <Image16Regular className='w-4 h-4 text-gray-600' />
            <div className='flex gap-1 items-center justify-center w-7 y-7 border-2 border-gray-600 rounded-full'>
              <ArrowCircleUp16Filled className='w-6 h-6 text-gray-600' />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
