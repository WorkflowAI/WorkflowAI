import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';

interface ImprovePromptProps {
  onImprovePrompt: (evaluation: string) => Promise<void>;
}

export function ImprovePrompt(props: ImprovePromptProps) {
  const { onImprovePrompt } = props;
  const [evaluation, setEvaluation] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleImprovePrompt = useCallback(async () => {
    setIsLoading(true);
    await onImprovePrompt(evaluation);
    setIsLoading(false);
  }, [evaluation, onImprovePrompt]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      if (evaluation.length > 0) {
        handleImprovePrompt();
      }
    }
  };

  return (
    <div className='flex flex-col justify-center gap-2 p-4 border-gray-200 border-b border-dashed'>
      <Textarea
        value={evaluation}
        onChange={(e) => setEvaluation(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder='Write feedback to refine your prompt…'
        className='text-gray-900 border-gray-300 font-lato text-[13px] placeholder:text-gray-400'
        disabled={isLoading}
      />
      {evaluation.length > 0 && (
        <Button
          variant='newDesign'
          size='none'
          onClick={() => handleImprovePrompt()}
          className='w-fit px-2 py-1.5 font-semibold text-xs'
          loading={isLoading}
        >
          Send Feedback
        </Button>
      )}
    </div>
  );
}
