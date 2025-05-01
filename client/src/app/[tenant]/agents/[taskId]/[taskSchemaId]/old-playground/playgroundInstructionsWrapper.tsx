import { useCallback, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/Button';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/HoverCard';

type PlaygroundInstructionsWrapperProps = {
  children: React.ReactNode;
  improveVersionChangelog: string;
  resetImproveVersionChangelog: () => void;
};

export function PlaygroundInstructionsWrapper(props: PlaygroundInstructionsWrapperProps) {
  const { children, improveVersionChangelog, resetImproveVersionChangelog } = props;

  const hoverCardRef = useRef<HTMLDivElement>(null);

  const handleClickOutside = useCallback(
    (event: MouseEvent) => {
      if (!!hoverCardRef.current && !hoverCardRef.current.contains(event.target as Node)) {
        resetImproveVersionChangelog();
      }
    },
    [resetImproveVersionChangelog]
  );

  useEffect(() => {
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [handleClickOutside]);

  return (
    <HoverCard open={!!improveVersionChangelog}>
      <HoverCardTrigger asChild>{children}</HoverCardTrigger>
      <HoverCardContent
        side='top'
        className='max-w-[350px] p-2 bg-slate-700 text-white text-xs font-medium flex flex-col gap-2 border-slate-500'
        ref={hoverCardRef}
      >
        <div className='whitespace-break-spaces'>{improveVersionChangelog}</div>
        <Button
          variant='outline'
          className='h-[30px] text-xs px-2 w-fit bg-transparent border-slate-600 text-slate-100 hover:text-slate-100 hover:bg-slate-600'
          onClick={resetImproveVersionChangelog}
        >
          Dismiss
        </Button>
      </HoverCardContent>
    </HoverCard>
  );
}
