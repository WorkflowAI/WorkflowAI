import { useMemo } from 'react';
import { AIEvaluationReview } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/components/AIEvaluation/AIEvaluationReview';
import { TaskRunOutputRows } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/components/TaskRunOutputRows/TaskRunOutputRows';
import { getContextWindowInformation } from '@/lib/taskRunUtils';
import { TaskID, TenantID } from '@/types/aliases';
import { LLMCompletionTypedMessages, RunV1, VersionV1 } from '@/types/workflowAI';
import { FeedbackBoxContainer } from './FeedbackBox';

type TaskRunDetailsProps = {
  tenant: TenantID | undefined;
  taskRun: RunV1;
  version: VersionV1 | undefined;
  completions: LLMCompletionTypedMessages[] | undefined;
};

export function TaskRunDetails(props: TaskRunDetailsProps) {
  const { taskRun, tenant, version, completions } = props;

  const contextWindowInformation = useMemo(() => {
    return getContextWindowInformation(completions);
  }, [completions]);

  return (
    <div className='h-full flex flex-col bg-white border-l border-gray-200 border-dashed'>
      <div className='flex flex-col flex-1 overflow-auto p-4 gap-6'>
        <AIEvaluationReview runId={taskRun.id} tenant={tenant} taskId={taskRun.task_id as TaskID} showFullBorder />

        <FeedbackBoxContainer runId={taskRun.id} tenant={tenant} taskId={taskRun.task_id as TaskID} />

        {!!version && (
          <div className='border border-gray-200 rounded-[2px]'>
            <TaskRunOutputRows
              currentAIModel={undefined}
              minimumCostAIModel={undefined}
              taskRun={taskRun}
              version={version}
              minimumLatencyTaskRun={undefined}
              minimumCostTaskRun={undefined}
              showVersion={true}
              contextWindowInformation={contextWindowInformation}
              showAllFields
            />
          </div>
        )}
      </div>
    </div>
  );
}
