import { ChevronDown12Filled } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useState } from 'react';

type Props = {
  text: string;
  wrapTextIfNeeded?: boolean;
  className?: string;
};

export function WrappedTextView(props: Props) {
  const { text, wrapTextIfNeeded = false, className } = props;

  const [isExpanded, setIsExpanded] = useState(false);
  const shouldShowWrapText = wrapTextIfNeeded && text.length > 1000 && !isExpanded;
  const textToShow = isExpanded ? text : text.slice(0, 1000);

  return (
    <div className={cx('flex flex-col text-gray-700 text-[13px]', className)}>
      <div className={'flex-1 whitespace-pre-wrap'}>{shouldShowWrapText ? textToShow : text}</div>
      {shouldShowWrapText && (
        <div
          className='flex w-full items-center justify-between pt-2 cursor-pointer'
          onClick={() => setIsExpanded(true)}
        >
          <div className='flex flex-row items-center gap-1'>
            <div className='text-indigo-500 text-[13px] font-medium'>View More</div>
            <ChevronDown12Filled className='w-3 h-3 text-indigo-500' />
          </div>
          <div className='text-gray-400 text-[12px]'>
            {textToShow.length} of {text.length} characters
          </div>
        </div>
      )}
    </div>
  );
}
