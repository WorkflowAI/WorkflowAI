'use client';

import { useMemo } from 'react';
import { Loader } from '@/components/ui/Loader';
import { PageContainer } from '@/components/v2/PageContainer';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useOrFetchAllAiModels, useOrFetchTask, useOrFetchTaskRuns, useOrFetchVersions } from '@/store';
import { EmptyStateComponent } from '../reviews/EmptyStateComponent';
import { SideBySideTable } from './SideBySideTable';

export function SideBySideContainer() {
  const { tenant, taskId, taskSchemaId } = useTaskSchemaParams();

  const { taskRuns, isLoading: isTaskRunsLoading } = useOrFetchTaskRuns(
    tenant,
    taskId,
    taskSchemaId,
    'limit=10&sort_by=recent&unique_by=task_input_hash&include_fields=task_input'
  );

  const inputs = useMemo(() => {
    return taskRuns?.map((taskRun) => taskRun.task_input);
  }, [taskRuns]);

  const { task } = useOrFetchTask(tenant, taskId);
  const { versions, isLoading: isVersionsLoading } = useOrFetchVersions(tenant, taskId, taskSchemaId);
  const { models } = useOrFetchAllAiModels({ tenant, taskId, taskSchemaId });

  const numberOfVersions = !!versions ? versions.length : 0;
  const areThereAnyRuns = !!taskRuns && taskRuns.length > 0;

  const entriesForEmptyState = useMemo(() => {
    const isThereMoreThenOneVersion = versions?.length > 1;

    return [
      {
        title: 'Run AI Feature',
        subtitle: 'Run your AI Feature to see how it performs.',
        imageURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/EmptyPageImage1.jpg',
        state: areThereAnyRuns,
      },
      {
        title: 'Save at Least One Versions',
        subtitle: 'Save a version to be able to compare it with others.',
        imageURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/EmptyPageImage4.jpg',
        state: isThereMoreThenOneVersion,
      },
      {
        title: '🎉 Compare Versions',
        subtitle: "You'll see clearly how the versions stack up against each other in accuracy, price, and latency.",
        imageURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/EmptyPageImage5.jpg',
        state: undefined,
      },
    ];
  }, [versions, areThereAnyRuns]);

  if (isVersionsLoading || isTaskRunsLoading || !task) {
    return <Loader centered />;
  }

  if (numberOfVersions < 1 || !areThereAnyRuns) {
    return (
      <PageContainer task={task} isInitialized={true} name='Side by Side' showCopyLink={true} showBottomBorder={true}>
        <EmptyStateComponent
          title='Side by Side'
          subtitle='Compares versions to find the most effective based on accuracy, cost, and latency. Your thumbs up or down helps build the benchmark for that version.'
          info="After Runs have been reviewed and at least two versions saved, you'll be able to compare them Side by Side"
          documentationLink={undefined}
          entries={entriesForEmptyState}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer task={task} isInitialized={true} name='Side By Side' showCopyLink={true} showBottomBorder={true}>
      <div className='flex flex-col h-full w-full overflow-hidden font-lato px-4 py-4 gap-4'>
        <SideBySideTable
          tenant={tenant}
          taskId={taskId}
          taskSchemaId={taskSchemaId}
          inputs={inputs}
          versions={versions}
          models={models}
        />
      </div>
    </PageContainer>
  );
}
