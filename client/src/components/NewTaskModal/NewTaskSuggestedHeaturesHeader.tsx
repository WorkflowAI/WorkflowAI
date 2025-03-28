import { ArrowUpFilled } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

type NewTaskSuggestedFeaturesHeaderProps = {
  userMessage: string;
  setUserMessage: (message: string) => void;
  onSendIteration: () => Promise<void>;
  loading: boolean;
};

export function NewTaskSuggestedFeaturesHeader(props: NewTaskSuggestedFeaturesHeaderProps) {
  const { userMessage, setUserMessage, onSendIteration, loading } = props;
  const inputRef = useRef<HTMLInputElement>(null);

  const [inProgress, setInProgress] = useState(false);
  const isLoading = loading || inProgress;

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus({ preventScroll: true });
    }
  }, []);

  const onSendMessage = useCallback(async () => {
    setInProgress(true);

    await onSendIteration();

    setTimeout(() => {
      setInProgress(false);
    }, 1000);
  }, [onSendIteration]);

  const isGenerateButtonActive = !isLoading && userMessage.length > 0;

  const [isFocused, setIsFocused] = useState(false);
  const showGradientBorder = !isLoading && isFocused;

  const showSendButton = userMessage.length > 0 || isFocused;

  return (
    <div className='flex flex-col gap-2 w-full'>
      <div
        className={cx(
          'flex w-full rounded-[4px]',
          showGradientBorder ? 'bg-custom-gradient-solid shadow-md' : 'bg-gray-200'
        )}
      >
        <div
          className={cx(
            'flex flex-row w-full items-center justify-between gap-2 rounded-[2px]',
            isLoading ? 'bg-gray-100' : 'bg-white',
            showGradientBorder ? 'm-[2px] px-2 py-1' : 'm-[1px] px-[9px] py-[5px]'
          )}
        >
          <Input
            ref={inputRef}
            placeholder='Write a description of the feature you want to build.'
            className={cx(
              'w-full text-[16px] font-normal py-0 pr-0 pl-1 focus-visible:ring-0 border-none bg-transparent',
              isLoading ? 'text-gray-400' : 'text-gray-900'
            )}
            value={userMessage}
            onChange={(event) => setUserMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && isGenerateButtonActive) {
                onSendMessage();
              }
            }}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
          />
          {showSendButton && (
            <Button
              variant='newDesignIndigo'
              icon={<ArrowUpFilled className='w-3.5 h-3.5' />}
              size='none'
              className={cx(
                'w-8 h-8 rounded-full flex-shrink-0 disabled:text-gray-400 disabled:opacity-100',
                isGenerateButtonActive
                  ? 'bg-custom-indigo-gradient'
                  : isLoading
                    ? 'bg-gray-50 disabled:bg-gray-50'
                    : 'bg-gray-100 disabled:bg-gray-100'
              )}
              disabled={!isGenerateButtonActive}
              onClick={() => onSendMessage()}
              loading={isLoading}
            />
          )}
        </div>
      </div>
    </div>
  );
}
