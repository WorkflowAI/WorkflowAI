import { ArchiveFilled, CheckmarkFilled, ChevronDownRegular } from '@fluentui/react-icons';
import { ReactNode, useState } from 'react';
import { SimpleTooltip } from '@/components/ui/Tooltip';

type ToolCallMessageProps = {
  usedToolCallText: string;
  archivedText: string;
  content: ReactNode;
  wasUsed: boolean;
  isArchived: boolean;
};

export function ToolCallMessage(props: ToolCallMessageProps) {
  const { usedToolCallText, archivedText, content, wasUsed, isArchived } = props;

  const [isOpen, setIsOpen] = useState(false);

  if (wasUsed) {
    return (
      <div className='flex flex-col gap-2 w-full'>
        <SimpleTooltip content={isOpen ? 'Hide the Tool Call' : 'Show the Tool Call'} tooltipDelay={0}>
          <div
            className='flex flex-row items-center gap-2 bg-gray-50 border border-gray-200 rounded-[4px] px-2 py-2 text-[13px] text-gray-500 cursor-pointer hover:bg-gray-100'
            onClick={() => setIsOpen(!isOpen)}
          >
            <div className='flex items-center justify-center w-5 h-5 rounded-full bg-green-500'>
              <CheckmarkFilled className='w-[14px] h-[14px] text-white' />
            </div>
            <div className='flex-1'>{usedToolCallText}</div>
            <ChevronDownRegular className={`w-4 h-4 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
          </div>
        </SimpleTooltip>
        {isOpen && content}
      </div>
    );
  }

  if (isArchived) {
    return (
      <div className='flex flex-col gap-2 w-full'>
        <SimpleTooltip content={isOpen ? 'Hide the Tool Call' : 'Show the Tool Call'} tooltipDelay={0}>
          <div
            className='flex flex-row items-center gap-2 bg-gray-50 border border-gray-200 rounded-[4px] px-2 py-2 text-[13px] text-gray-500 cursor-pointer hover:bg-gray-100'
            onClick={() => setIsOpen(!isOpen)}
          >
            <div className='flex items-center justify-center w-5 h-5 rounded-full bg-gray-500'>
              <ArchiveFilled className='w-[13px] h-[13px] text-white' />
            </div>
            <div className='flex-1'>{archivedText}</div>
            <ChevronDownRegular className={`w-4 h-4 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
          </div>
        </SimpleTooltip>
        {isOpen && content}
      </div>
    );
  }

  return content;
}
