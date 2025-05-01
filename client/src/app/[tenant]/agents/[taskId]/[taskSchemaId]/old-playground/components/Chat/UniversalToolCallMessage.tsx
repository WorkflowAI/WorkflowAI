import { ArrowSwapFilled, CheckmarkFilled, DismissFilled } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { useHotkeys } from 'react-hotkeys-hook';
import { Button } from '@/components/ui/Button';

type UniversalToolCallMessageProps = {
  title: string;
  titleInProgress: string;
  titleArchived: string;
  titleUsed: string;
  isInProgress: boolean;
  isArchived: boolean;
  wasUsed: boolean;
  onAction: () => void;
  onIgnore: () => void;
  onInactiveAction?: () => void;
};

export function UniversalToolCallMessage(props: UniversalToolCallMessageProps) {
  const {
    title,
    titleInProgress,
    titleArchived,
    titleUsed,
    isInProgress,
    isArchived,
    wasUsed,
    onAction,
    onIgnore,
    onInactiveAction,
  } = props;

  useHotkeys(
    'ctrl+n',
    (event) => {
      event.preventDefault();
      onIgnore();
    },
    {
      enabled: !wasUsed && !isInProgress && !isArchived,
      preventDefault: true,
      keydown: false,
      keyup: true,
    }
  );

  useHotkeys(
    'ctrl+y',
    (event) => {
      event.preventDefault();
      onAction();
    },
    {
      enabled: !wasUsed && !isInProgress && !isArchived,
      preventDefault: true,
      keydown: false,
      keyup: true,
    }
  );

  if (wasUsed) {
    return (
      <div
        className={cx(
          'flex flex-row items-center gap-2 bg-gray-50 border border-gray-200 rounded-[4px] px-3 py-2 text-[13px] text-gray-500 font-semibold',
          !!onInactiveAction && 'cursor-pointer hover:bg-gray-100'
        )}
        onClick={onInactiveAction}
      >
        <div className='flex items-center justify-center w-5 h-5 rounded-full bg-green-500'>
          <CheckmarkFilled className='w-[14px] h-[14px] text-white' />
        </div>
        <div className='flex-1'>{titleUsed}</div>
      </div>
    );
  }

  if (isArchived) {
    return (
      <div
        className={cx(
          'flex flex-row items-center gap-2 bg-gray-50 border border-gray-200 rounded-[4px] px-3 py-2 text-[13px] text-gray-500 font-semibold',
          !!onInactiveAction && 'cursor-pointer hover:bg-gray-100'
        )}
        onClick={onInactiveAction}
      >
        <div className='flex items-center justify-center w-5 h-5 rounded-full bg-red-500'>
          <DismissFilled className='w-[14px] h-[14px] text-white' />
        </div>
        <div className='flex-1'>{titleArchived}</div>
      </div>
    );
  }

  if (isInProgress) {
    return (
      <div className='flex flex-row items-center gap-2 bg-gray-50 border border-gray-200 rounded-[4px] px-3 py-2 text-[13px] text-gray-700 font-semibold'>
        <Loader2 className='h-4 w-4 animate-spin text-indigo-500' />
        <div className='flex-1'>{titleInProgress}</div>
      </div>
    );
  }

  return (
    <div className='flex flex-col gap-2 bg-gray-50 border border-gray-200 rounded-[4px] px-3 py-2 text-[13px] text-gray-700 font-semibold'>
      <div className='flex flex-row items-center gap-2'>
        <ArrowSwapFilled className='w-[18px] h-[18px] text-indigo-500' />
        <div className='flex-1'>{title}</div>
      </div>
      <div className='flex flex-row items-center gap-2 w-full justify-end'>
        <Button variant='newDesignGray' size='sm' onClick={onIgnore}>
          No
          <div className='text-[10px] text-gray-800 bg-white rounded-[2px] px-1 py-[2px] font-bold'>
            <span className='font-light'>⌃</span>N
          </div>
        </Button>
        <Button variant='newDesignIndigo' size='sm' onClick={onAction}>
          Yes
          <div className='text-[10px] text-indigo-700 bg-white/70 rounded-[2px] px-1 py-[2px] font-bold'>
            <span className='font-light'>⌃</span>Y
          </div>
        </Button>
      </div>
    </div>
  );
}
