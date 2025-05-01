'use client';

import { useCallback, useMemo } from 'react';
import { Loader } from '@/components/ui/Loader';
import { PageContainer } from '@/components/v2/PageContainer';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useOrFetchTask } from '@/store';
import {
  useOrFetchEvaluation,
  useOrFetchEvaluationInputs,
  useOrFetchLatestRun,
  useOrFetchTaskSchema,
} from '@/store/fetchers';
import { useTaskEvaluation } from '@/store/task_evaluation';
import { EmptyStateComponent } from './EmptyStateComponent';
import { ReviewEntry } from './ReviewEntry';
import { ReviewMainInstructions } from './ReviewMainInstructions';
import { ReviewsHeader } from './ReviewsHeader';

export default function ReviewsContainer() {
  const { tenant, taskId, taskSchemaId } = useTaskSchemaParams();

  const { task, isInitialized: isTaskInitialized } = useOrFetchTask(tenant, taskId);

  const { taskSchema: currentTaskSchema, isInitialized: isTaskSchemaInitialized } = useOrFetchTaskSchema(
    tenant,
    taskId,
    taskSchemaId
  );

  const { evaluation, isInitialized: isEvaluationInitialized } = useOrFetchEvaluation(tenant, taskId, taskSchemaId);

  const { evaluationInputs, isInitialized: isEvaluationInputsInitialized } = useOrFetchEvaluationInputs(
    tenant,
    taskId,
    taskSchemaId
  );

  const sortedEvaluationInputs = evaluationInputs?.sort((a, b) => {
    return a.task_input_hash.localeCompare(b.task_input_hash);
  });

  const updateEvaluation = useTaskEvaluation((state) => state.updateEvaluation);

  const handleUpdateEvaluation = useCallback(
    (instructions: string) => {
      updateEvaluation(tenant, taskId, taskSchemaId, instructions);
    },
    [tenant, taskId, taskSchemaId, updateEvaluation]
  );

  const { latestRun, isLoading: isLatestRunLoading } = useOrFetchLatestRun(tenant, taskId, taskSchemaId);

  const { isInDemoMode } = useDemoMode();

  const entriesForEmptyState = useMemo(() => {
    const areThereAnyRuns = !!latestRun;

    return [
      {
        title: 'Run AI Feature',
        subtitle: 'Run your AI Feature with different inputs to see how it performs',
        imageURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/EmptyPageImage1.jpg',
        state: areThereAnyRuns,
      },
      {
        title: 'Review Runs',
        subtitle:
          'Each review you leave will be recorded on your AI Feature’s Review page and used to Benchmark different versions’ performance',
        imageURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/EmptyPageImage2.jpg',
        state: false,
      },
      {
        title: '🎉 Continue Adding to Your Dataset',
        subtitle: 'We recommend starting with 10–20 evaluated runs to create a solid dataset.',
        imageURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/EmptyPageImage3.jpg',
        state: undefined,
      },
    ];
  }, [latestRun]);

  if (
    !task ||
    !isTaskSchemaInitialized ||
    !isEvaluationInitialized ||
    !isEvaluationInputsInitialized ||
    isLatestRunLoading
  ) {
    return <Loader centered />;
  }

  if (!sortedEvaluationInputs || sortedEvaluationInputs.length === 0) {
    return (
      <PageContainer task={task} isInitialized={isTaskInitialized} name='Reviews' showCopyLink={true}>
        <EmptyStateComponent
          title='Reviews'
          subtitle='Reviews rate whether a run’s output is correct or not. They help measure an AI feature’s accuracy and improve Benchmarking. The more reviews you add, the more accurate the Benchmarks become.'
          info='Once at least one review is added, you’ll see the content here'
          documentationLink={undefined}
          entries={entriesForEmptyState}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer task={task} isInitialized={isTaskInitialized} name='Reviews' showCopyLink={true}>
      <div className='flex flex-col h-full w-full overflow-hidden font-lato px-4 py-4 gap-4'>
        <ReviewMainInstructions
          instructions={evaluation?.evaluation_instructions}
          onChange={handleUpdateEvaluation}
          disabled={isInDemoMode}
        />
        <div className='flex flex-col w-full flex-1 border border-gray-200 rounded-[2px] px-2 pb-2 bg-gradient-to-b from-white/50 to-white/20 overflow-hidden'>
          <ReviewsHeader />
          <div className='flex flex-col w-full flex-1 overflow-y-auto'>
            {sortedEvaluationInputs?.map((data) => (
              <ReviewEntry
                key={data.task_input_hash}
                tenant={tenant}
                taskId={taskId}
                taskSchemaId={taskSchemaId}
                data={data}
                schemaInput={currentTaskSchema?.input_schema}
                schemaOutput={currentTaskSchema?.output_schema}
                isInDemoMode={isInDemoMode}
              />
            ))}
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
