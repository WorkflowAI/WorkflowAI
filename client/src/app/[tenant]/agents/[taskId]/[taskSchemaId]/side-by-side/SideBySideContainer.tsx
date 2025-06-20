'use client';

import { useCallback, useMemo } from 'react';
import { InfinitlyPaging } from '@/components/ui/InfinitlyPaging';
import { Loader } from '@/components/ui/Loader';
import { PageContainer } from '@/components/v2/PageContainer';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useParsedSearchParams, useRedirectWithParams } from '@/lib/queryString';
import {
  useOrFetchLatestRun,
  useOrFetchSchemaAIModels,
  useOrFetchTask,
  useOrFetchTaskRuns,
  useOrFetchVersions,
} from '@/store';
import { EmptyStateComponent } from '../reviews/EmptyStateComponent';
import { SideBySideTable } from './SideBySideTable';

const ENTRIES_PER_PAGE = 10;

export function SideBySideContainer() {
  const { tenant, taskId, taskSchemaId } = useTaskSchemaParams();

  const { page: pageValue } = useParsedSearchParams('page');
  const page = useMemo(() => (pageValue ? parseInt(pageValue) : 0), [pageValue]);

  // We are fetching one more to always be able to determinate if there is a page after this
  const numberOfRunsToFetch = ENTRIES_PER_PAGE + 1;

  const searchParams = useMemo(() => {
    return (
      `limit=${numberOfRunsToFetch}&sort_by=recent&unique_by=task_input_hash&include_fields=task_input` +
      (page ? `&offset=${page * ENTRIES_PER_PAGE}` : '')
    );
  }, [page, numberOfRunsToFetch]);

  const redirectWithParams = useRedirectWithParams();

  const onPageSelected = useCallback(
    (page: number) => {
      redirectWithParams({
        params: { page },
        scroll: false,
      });
      const sideBySideTable = document.getElementById('side-by-side-table');
      if (sideBySideTable) {
        sideBySideTable.scrollTo(0, 0);
      }
    },
    [redirectWithParams]
  );

  // We are also fetching the last run to not need to wait for all the taskruns when changing page and in this way changing searchParams
  const { latestRun, isLoading: isLatestRunLoading } = useOrFetchLatestRun(tenant, taskId, taskSchemaId);
  const { taskRuns } = useOrFetchTaskRuns(tenant, taskId, taskSchemaId, searchParams);

  const isNextPageAvaible = taskRuns?.length === numberOfRunsToFetch;

  // Only the inputs to display without the one extra one to determinate if there is a next page
  const inputs = useMemo(() => {
    return taskRuns?.slice(0, ENTRIES_PER_PAGE).map((taskRun) => taskRun.task_input);
  }, [taskRuns]);

  const { task } = useOrFetchTask(tenant, taskId);
  const { versions, isLoading: isVersionsLoading } = useOrFetchVersions(tenant, taskId, taskSchemaId);
  const { models } = useOrFetchSchemaAIModels({ tenant, taskId, taskSchemaId });

  const numberOfVersions = !!versions ? versions.length : 0;
  const areThereAnyRuns = !!latestRun;

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

  if (isVersionsLoading || isLatestRunLoading || !task) {
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
      <div className='flex flex-col h-full w-full overflow-hidden font-lato px-4 py-4 gap-4 justify-between'>
        <SideBySideTable
          tenant={tenant}
          taskId={taskId}
          taskSchemaId={taskSchemaId}
          inputs={inputs}
          versions={versions}
          models={models}
          page={page}
        />
        <InfinitlyPaging
          nextPageAvailable={isNextPageAvaible}
          currentPage={page}
          onPageSelected={onPageSelected}
          className='py-1'
        />
      </div>
    </PageContainer>
  );
}
