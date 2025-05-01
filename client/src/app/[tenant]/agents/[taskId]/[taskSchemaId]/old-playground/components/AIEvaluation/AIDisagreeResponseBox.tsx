import { useState } from 'react';
import { useCallback } from 'react';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { useTaskRunReviews } from '@/store/task_run_reviews';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';

type AIDisagreeResponseBoxProps = {
  reviewId: string;
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskRunId: string;
  placeholder: string;
  onClose: () => void;
};

export function AIDisagreeResponseBox(props: AIDisagreeResponseBoxProps) {
  const { reviewId, tenant, taskId, taskRunId, placeholder, onClose } = props;

  const [comment, setComment] = useState('');

  const { respondToReview } = useTaskRunReviews();

  const onSend = useCallback(
    async (comment: string) => {
      try {
        await respondToReview(tenant, taskId, taskRunId, reviewId, comment);
      } finally {
        onClose();
      }
    },
    [respondToReview, onClose, reviewId, tenant, taskId, taskRunId]
  );

  return (
    <div className='flex flex-col justify-center gap-2 pb-2 border-gray-200 border-b border-dashed'>
      <Textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder={placeholder}
        className='text-gray-900 border-gray-300 font-lato text-[13px] placeholder:text-gray-400'
      />
      {comment.length > 0 && (
        <Button
          variant='newDesign'
          size='none'
          onClick={() => onSend(comment)}
          className='w-fit px-2 py-1.5 font-semibold text-xs'
        >
          Send Feedback
        </Button>
      )}
    </div>
  );
}
