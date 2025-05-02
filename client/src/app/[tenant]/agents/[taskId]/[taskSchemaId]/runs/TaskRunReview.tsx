import { Loader2 } from 'lucide-react';
import {
  AIEvaluationReviewButton,
  AIEvaluationReviewButtonMode,
  AIEvaluationReviewButtonThumb,
} from '@/app/[tenant]/agents/[taskId]/playground/components/Tab/Output/AIEvaluation/AIEvaluationReviewButton';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { TaskRun } from '@/types/task_run';

type TaskRunReviewProps = {
  taskRun: Pick<TaskRun, 'ai_review' | 'user_review'>;
};

export function TaskRunReview(props: TaskRunReviewProps) {
  const { taskRun } = props;

  const userReview = taskRun.user_review;
  const aiReview = taskRun.ai_review;

  let mode: AIEvaluationReviewButtonMode = AIEvaluationReviewButtonMode.NORMAL;
  let thumb: AIEvaluationReviewButtonThumb = AIEvaluationReviewButtonThumb.UP;

  if (!!userReview) {
    mode = AIEvaluationReviewButtonMode.USER_SELECTED;
    thumb = userReview === 'positive' ? AIEvaluationReviewButtonThumb.UP : AIEvaluationReviewButtonThumb.DOWN;
  } else if (!!aiReview) {
    mode = AIEvaluationReviewButtonMode.AI_SELECTED;
    thumb = aiReview === 'positive' ? AIEvaluationReviewButtonThumb.UP : AIEvaluationReviewButtonThumb.DOWN;
  }

  if (aiReview === 'in_progress' && !userReview) {
    return <Loader2 className='h-4 w-4 animate-spin text-gray-400 ml-1.5' />;
  }

  if (!aiReview && !userReview) {
    return null;
  }

  if (aiReview === 'unsure') {
    return null;
  }

  const tooltipContent = (
    <div className='flex flex-row gap-1.5 py-0.5'>
      <AIEvaluationReviewButton
        mode={AIEvaluationReviewButtonMode.USER_SELECTED}
        thumb={userReview === 'positive' ? AIEvaluationReviewButtonThumb.UP : AIEvaluationReviewButtonThumb.DOWN}
        disabled={false}
      />
      <AIEvaluationReviewButton
        mode={AIEvaluationReviewButtonMode.AI_SELECTED}
        thumb={aiReview === 'positive' ? AIEvaluationReviewButtonThumb.UP : AIEvaluationReviewButtonThumb.DOWN}
        disabled={false}
      />
    </div>
  );

  return (
    <SimpleTooltip
      content={!!userReview && !!aiReview && tooltipContent}
      side='top'
      align='center'
      tooltipClassName='bg-white border border-gray-200'
    >
      <div className='flex w-fit h-fit items-center justify-center'>
        <AIEvaluationReviewButton mode={mode} thumb={thumb} disabled={false} />
      </div>
    </SimpleTooltip>
  );
}
