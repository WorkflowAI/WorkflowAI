import { Info12Regular } from '@fluentui/react-icons';
import { Loader2 } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { cn } from '@/lib/utils';
import { useOrFetchTaskRunReviews } from '@/store/fetchers';
import { useTaskRunReviews } from '@/store/task_run_reviews';
import { TaskID, TenantID } from '@/types/aliases';
import { AIDisagreeResponseBox } from './AIDisagreeResponseBox';
import {
  AIEvaluationReviewButton,
  AIEvaluationReviewButtonMode,
  AIEvaluationReviewButtonThumb,
} from './AIEvaluationReviewButton';
import { AIEvaluationReviewComment } from './AIEvaluationReviewComment';
import { combineReviewAspects } from './utils';

interface AIEvaluationReviewProps {
  runId: string;
  tenant: TenantID | undefined;
  taskId: TaskID;
  showFullBorder?: boolean;
  showOnlyButtons?: boolean;
  onImprovePrompt?: (evaluation: string) => Promise<void>;
  pollingInterval?: number;
}

export function AIEvaluationReview(props: AIEvaluationReviewProps) {
  const {
    runId,
    tenant,
    taskId,
    showFullBorder = false,
    showOnlyButtons = false,
    onImprovePrompt,
    pollingInterval,
  } = props;

  const { reviews } = useOrFetchTaskRunReviews(tenant, taskId, runId, pollingInterval);
  const { createReview } = useTaskRunReviews();

  const latestReviews = useMemo(() => {
    if (!reviews?.length) return { ai: undefined, user: undefined };
    return {
      ai: reviews.find((review) => review.created_by.reviewer_type === 'ai'),
      user: reviews.find((review) => review.created_by.reviewer_type === 'user'),
    };
  }, [reviews]);

  const { ai: latestAIReview, user: latestUserReview } = latestReviews;

  const reviewScores = useMemo(
    () => ({
      ai: !latestAIReview || latestAIReview.outcome === null ? undefined : latestAIReview.outcome,
      user:
        !latestUserReview || latestUserReview.outcome === null ? undefined : latestUserReview.outcome === 'positive',
    }),
    [latestAIReview, latestUserReview]
  );

  const getButtonMode = useCallback(
    (isPositive: boolean) => {
      if (reviewScores.user !== undefined) {
        return reviewScores.user === isPositive
          ? AIEvaluationReviewButtonMode.USER_SELECTED
          : AIEvaluationReviewButtonMode.NORMAL;
      }

      if (reviewScores.ai !== undefined) {
        switch (isPositive) {
          case true:
            return reviewScores.ai === 'positive'
              ? AIEvaluationReviewButtonMode.AI_SELECTED
              : AIEvaluationReviewButtonMode.NORMAL;
          case false:
            return reviewScores.ai === 'negative'
              ? AIEvaluationReviewButtonMode.AI_SELECTED
              : AIEvaluationReviewButtonMode.NORMAL;
        }
      }

      return AIEvaluationReviewButtonMode.NORMAL;
    },
    [reviewScores]
  );

  const [disagreeBoxReviewId, setDisagreeBoxReviewId] = useState<string>();

  const handleReview = useCallback(
    async (isPositive: boolean) => {
      await createReview(tenant, taskId, runId, isPositive ? 'positive' : 'negative');

      const value = isPositive ? 'positive' : 'negative';

      if (reviewScores.ai !== undefined && reviewScores.ai !== value) {
        setDisagreeBoxReviewId(latestAIReview?.id);
      }
    },
    [reviewScores.ai, createReview, tenant, taskId, runId, latestAIReview?.id]
  );

  const showAIEvaluation = {
    loading: !latestUserReview && latestAIReview?.status === 'in_progress',
    review: !latestUserReview && latestAIReview?.status === 'completed',
  };

  const disagreeBoxPlaceholder = useMemo(() => {
    if (reviewScores.ai === undefined && reviewScores.user === undefined) {
      return '';
    }

    switch (reviewScores.ai) {
      case 'positive':
      case 'negative':
        return 'Tell us why you disagree with the AI’s review. (Optional)';
      default:
        switch (reviewScores.user) {
          case true:
            return 'Tell us why you think this output was correct.';
          default:
            return 'Tell us why you think this output was incorrect.';
        }
    }
  }, [reviewScores.ai, reviewScores.user]);

  const onCloseDisagreeBox = useCallback(() => {
    setDisagreeBoxReviewId(undefined);
  }, []);

  const onImprovePromptWithCombinedReview = useCallback(async () => {
    if (!latestAIReview || !onImprovePrompt) return undefined;

    const combinedReview = combineReviewAspects({
      review: latestAIReview,
    });

    await onImprovePrompt(combinedReview);
  }, [latestAIReview, onImprovePrompt]);

  const { isInDemoMode } = useDemoMode();

  if (showOnlyButtons) {
    return (
      <div className='flex flex-row gap-1'>
        <AIEvaluationReviewButton
          mode={getButtonMode(true)}
          thumb={AIEvaluationReviewButtonThumb.UP}
          onClick={() => handleReview(true)}
          disabled={isInDemoMode}
        />
        <AIEvaluationReviewButton
          mode={getButtonMode(false)}
          thumb={AIEvaluationReviewButtonThumb.DOWN}
          onClick={() => handleReview(false)}
          disabled={isInDemoMode}
        />
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex flex-col w-full px-4 font-lato overflow-y-hidden',
        showFullBorder ? 'border border-gray-200' : 'border-b border-gray-200'
      )}
    >
      <div className='flex flex-row justify-between items-center py-2'>
        <div className='flex flex-row items-center'>
          <div className='text-[13px] font-normal text-gray-500'>Review Output</div>
          <SimpleTooltip
            content={`Give a thumbs up to set an example of a Good response,
              and the Review Assistant will help review future outputs.`}
            tooltipClassName='whitespace-pre-line'
          >
            <Info12Regular className='w-3 h-3 text-indigo-500 m-1' />
          </SimpleTooltip>
        </div>
        <div className='flex flex-row gap-1'>
          <AIEvaluationReviewButton
            mode={getButtonMode(true)}
            thumb={AIEvaluationReviewButtonThumb.UP}
            onClick={() => handleReview(true)}
            disabled={isInDemoMode}
          />
          <AIEvaluationReviewButton
            mode={getButtonMode(false)}
            thumb={AIEvaluationReviewButtonThumb.DOWN}
            onClick={() => handleReview(false)}
            disabled={isInDemoMode}
          />
        </div>
      </div>
      {showAIEvaluation.loading && (
        <div className='flex flex-row gap-2.5 items-center py-2.5 px-2.5 mb-2 border border-gray-300 rounded-[2px] text-gray-700 text-[13px]'>
          <Loader2 className='h-4 w-4 animate-spin text-gray-400' />
          <div>AI is currently reviewing...</div>
        </div>
      )}
      {showAIEvaluation.review && (
        <AIEvaluationReviewComment
          state={reviewScores.ai}
          summary={latestAIReview?.summary ?? undefined}
          positiveAspects={latestAIReview?.positive_aspects ?? undefined}
          negativeAspects={latestAIReview?.negative_aspects ?? undefined}
          onImprovePrompt={!!onImprovePrompt ? onImprovePromptWithCombinedReview : undefined}
        />
      )}
      {!!disagreeBoxReviewId && (
        <AIDisagreeResponseBox
          reviewId={disagreeBoxReviewId}
          tenant={tenant}
          taskId={taskId}
          taskRunId={runId}
          placeholder={disagreeBoxPlaceholder}
          onClose={onCloseDisagreeBox}
        />
      )}
    </div>
  );
}
