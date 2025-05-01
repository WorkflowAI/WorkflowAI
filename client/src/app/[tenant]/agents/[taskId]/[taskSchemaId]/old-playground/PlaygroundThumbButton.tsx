import { ThumbDislike16Regular, ThumbLike16Regular } from '@fluentui/react-icons';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/HoverCard';
import { Textarea } from '@/components/ui/Textarea';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { cn } from '@/lib/utils';

export enum PlaygroundThumbButtonMode {
  UP = 'up',
  DOWN = 'down',
}

type PlaygroundThumbButtonProps = {
  mode: PlaygroundThumbButtonMode;
  isOn: boolean;

  disabled: boolean;
  tooltipContent?: string;
  onSubmitUserEvaluation: (rating: boolean, userEvaluation: string | undefined) => Promise<void>;
};

export function PlaygroundThumbButton(props: PlaygroundThumbButtonProps) {
  const { mode, isOn, disabled, onSubmitUserEvaluation, tooltipContent } = props;
  const [userEvaluation, setUserEvaluation] = useState<string>('');
  const [hoverCardVisible, setHoverCardVisible] = useState(false);
  const hideHoverCard = useCallback(() => {
    setHoverCardVisible(false);
    setUserEvaluation('');
  }, []);
  const [loading, setLoading] = useState(false);

  const hoverCardRef = useRef<HTMLDivElement>(null);

  const handleClickOutside = useCallback(
    (event: MouseEvent) => {
      if (!loading && !!hoverCardRef.current && !hoverCardRef.current.contains(event.target as Node)) {
        setHoverCardVisible(false);
      }
    },
    [loading]
  );

  useEffect(() => {
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [handleClickOutside]);

  const onInstructionsChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setUserEvaluation(e.target.value);
  }, []);

  const onSubmit = useCallback(async () => {
    if (isOn) {
      return;
    }

    const rating = mode === PlaygroundThumbButtonMode.UP;

    setLoading(true);
    try {
      await onSubmitUserEvaluation(rating, !!userEvaluation ? userEvaluation : undefined);
      hideHoverCard();
    } finally {
      setLoading(false);
    }
  }, [userEvaluation, onSubmitUserEvaluation, hideHoverCard, mode, isOn]);

  const showHoverCard = useCallback(async () => {
    switch (mode) {
      case PlaygroundThumbButtonMode.UP:
        setLoading(true);
        try {
          await onSubmitUserEvaluation(true, undefined);
        } finally {
          setLoading(false);
        }
        break;
      case PlaygroundThumbButtonMode.DOWN:
        setHoverCardVisible(true);
        break;
    }
  }, [mode, onSubmitUserEvaluation]);

  const button = (
    <Button
      variant='newDesign'
      size='none'
      icon={
        mode === PlaygroundThumbButtonMode.DOWN ? (
          <ThumbDislike16Regular className='h-4 w-4 text-gray-500' />
        ) : (
          <ThumbLike16Regular className='h-4 w-4 text-gray-500' />
        )
      }
      onClick={showHoverCard}
      disabled={disabled}
      className={cn(
        'h-7 w-7 border-none shadow-sm shadow-gray-400/30',
        mode === PlaygroundThumbButtonMode.UP && isOn
          ? '!bg-green-100 !text-green-600 !hover:bg-green-200 border-green-300'
          : undefined,
        mode === PlaygroundThumbButtonMode.DOWN && isOn
          ? '!bg-red-100 !text-red-600 !hover:bg-red-200 !border-red-300'
          : undefined
      )}
    />
  );

  return hoverCardVisible ? (
    <HoverCard open>
      <HoverCardTrigger asChild>{button}</HoverCardTrigger>
      <HoverCardContent side='top' className='w-[450px] p-0 rounded-[2px] border-gray-200' ref={hoverCardRef}>
        <div>
          <div className='px-4 py-3 border-b text-gray-500 text-medium font-lato'>
            <div className='flex items-center justify-between pb-2 text-sm'>
              <div>
                {mode === PlaygroundThumbButtonMode.DOWN
                  ? 'What was wrong with this output?'
                  : 'Why is this output correct?'}
              </div>
              <Button disabled={!userEvaluation} variant='newDesign' onClick={onSubmit}>
                Submit
              </Button>
            </div>
            <div className='text-xs text-normal'>
              {mode === PlaygroundThumbButtonMode.DOWN
                ? 'We will use your response to generate improved instructions'
                : 'We will use your response to generate evaluation instructions'}
            </div>
          </div>
          <div className='px-4 py-3'>
            <Textarea
              value={userEvaluation}
              onChange={onInstructionsChange}
              className='min-h-[120px]'
              placeholder={
                mode === PlaygroundThumbButtonMode.DOWN
                  ? 'Describe what was wrong with the output or what you want to see instead.'
                  : 'Describe why this output is correct (optional)'
              }
              autoFocus
            />
          </div>
        </div>
      </HoverCardContent>
    </HoverCard>
  ) : (
    <SimpleTooltip
      content={!!tooltipContent ? <div className='whitespace-break-spaces max-w-[450px]'>{tooltipContent}</div> : null}
    >
      {button}
    </SimpleTooltip>
  );
}
