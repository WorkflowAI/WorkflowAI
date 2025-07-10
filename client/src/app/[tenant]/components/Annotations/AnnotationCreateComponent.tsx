import { nanoid } from 'nanoid';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { Annotation } from '@/types/workflowAI/models';

type Props = {
  onCreateAnnotation: (annotation: Annotation) => void;
  onCancel: () => void;
};

export function AnnotationCreateComponent(props: Props) {
  const { onCreateAnnotation, onCancel } = props;

  const [text, setText] = useState('');

  const handleAddAnnotation = useCallback(() => {
    onCreateAnnotation({
      id: nanoid(),
      comment: text,
      type: 'approval',
      timestamp: new Date().toISOString(),
      user: 'Pierre',
    });
  }, [onCreateAnnotation, text]);

  const isDisabled = text.length === 0;

  return (
    <div className='flex flex-col gap-2 w-full p-4 border border-gray-200 rounded-[2px]'>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder='Add a comment'
        className='text-gray-900 border-gray-300 font-lato text-[13px] placeholder:text-gray-400 py-2 focus-within:ring-inset'
        autoFocus={true}
      />
      <div className='flex flex-row gap-2 items-center'>
        <Button variant='newDesign' size='sm' onClick={onCancel}>
          Cancel
        </Button>
        <Button variant='newDesignDark' size='sm' onClick={handleAddAnnotation} disabled={isDisabled}>
          Add Annotation
        </Button>
      </div>
    </div>
  );
}
