'use client';

import { MultiselectLtr16Regular } from '@fluentui/react-icons';
import { keyBy } from 'lodash';
import { useCallback, useMemo, useState } from 'react';
import { useInterval } from 'usehooks-ts';
import { useDeployVersionModal } from '@/components/DeployIterationModal/DeployVersionModal';
import {
  DEFAULT_TASK_VERSION_EDITABLE_PROPERTIES,
  NewGroupModal,
  TaskVersionEditableProperties,
} from '@/components/NewVersionModal';
import { Loader } from '@/components/ui/Loader';
import { PageContainer } from '@/components/v2/PageContainer';
import { PageSection } from '@/components/v2/PageSection';
import { useCompatibleAIModels } from '@/lib/hooks/useCompatibleAIModels';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { useRedirectWithParams } from '@/lib/queryString';
import { Params, taskApiRoute, taskRunsRoute, taskSchemaRoute } from '@/lib/routeFormatter';
import { environmentsForVersion } from '@/lib/versionUtils';
import {
  useOrFetchEvaluationInputs,
  useOrFetchReviewBenchmark,
  useOrFetchSchemaAIModels,
  useOrFetchTask,
  useOrFetchVersions,
} from '@/store';
import { useReviewBenchmark } from '@/store/task_review_benchmark';
import { useVersions } from '@/store/versions';
import { UNDEFINED_MODEL } from '@/types/aliases';
import { VersionResult, VersionV1 } from '@/types/workflowAI';
import { EmptyStateComponent } from '../reviews/EmptyStateComponent';
import { BenchmarkGraph } from './BenchmarkGraph';
import { BenchmarkVersionSelection } from './BenchmarkVersionSelection';
import { BenchmarksGroupTable } from './BenchmarksGroupTable';
import { findBestOnes } from './utils';

export function BenchmarksContainer() {
  const { tenant, taskId, taskSchemaId } = useTaskSchemaParams();

  const { benchmark, isInitialized } = useOrFetchReviewBenchmark(tenant, taskId, taskSchemaId);

  const fetchBenchmark = useReviewBenchmark((state) => state.fetchBenchmark);
  const updateBenchmark = useReviewBenchmark((state) => state.updateBenchmark);

  const {
    versions,
    versionsPerEnvironment,
    isLoading: isVersionsLoading,
  } = useOrFetchVersions(tenant, taskId, taskSchemaId);

  const versionById = useMemo(() => keyBy(versions, 'id'), [versions]);
  const versionByIteration = useMemo(() => keyBy(versions, 'iteration'), [versions]);

  const bestOnes = useMemo(() => {
    return findBestOnes(benchmark?.results ?? []);
  }, [benchmark]);

  const benchmarkIterations: Set<number> | undefined = useMemo(() => {
    if (benchmark) {
      return new Set(benchmark.results.map((result) => result.iteration));
    }
    return undefined;
  }, [benchmark]);

  const updateBenchmarkIterations = useCallback(
    async (iterations: Set<number> | undefined) => {
      let iterationsToAdd: number[] = [];
      let iterationsToRemove: number[] = [];

      const oldSet = benchmarkIterations || new Set<number>();
      const newSet = iterations || new Set<number>();

      iterationsToAdd = Array.from(newSet).filter((iteration) => !oldSet.has(iteration));

      iterationsToRemove = Array.from(oldSet).filter((iteration) => !newSet.has(iteration));

      await updateBenchmark(tenant, taskId, taskSchemaId, iterationsToAdd, iterationsToRemove);
    },
    [benchmarkIterations, updateBenchmark, tenant, taskId, taskSchemaId]
  );

  const benchmarkResultsDictionary = useMemo(() => {
    const result = new Map<number, VersionResult>();

    benchmark?.results.forEach((entry) => {
      if (!entry.iteration) {
        return;
      }
      result.set(entry.iteration, entry);
    });

    return result;
  }, [benchmark]);

  useInterval(() => {
    fetchBenchmark(tenant, taskId, taskSchemaId);
  }, 1000);

  const { task } = useOrFetchTask(tenant, taskId);

  const redirectWithParams = useRedirectWithParams();

  const onTryInPlayground = useCallback(
    (versionId: string) => {
      redirectWithParams({
        path: taskSchemaRoute(tenant, taskId, taskSchemaId, {
          versionId: versionId,
        }),
      });
    },
    [redirectWithParams, tenant, taskId, taskSchemaId]
  );

  const onViewCode = useCallback(
    (version: VersionV1) => {
      const environments = environmentsForVersion(version);
      redirectWithParams({
        path: taskApiRoute(tenant, taskId, taskSchemaId),
        params: {
          selectedVersionId: version.id,
          selectedEnvironment: environments?.[0],
        },
      });
    },
    [redirectWithParams, tenant, taskSchemaId, taskId]
  );

  const { onDeployToClick } = useDeployVersionModal();

  const [newGroupModalOpen, setNewGroupModalOpen] = useState(false);

  const [editableProperties, setEditableProperties] = useState<TaskVersionEditableProperties>(
    DEFAULT_TASK_VERSION_EDITABLE_PROPERTIES
  );

  const onClone = useCallback(
    (versionId: string) => {
      const version = versionById[versionId];
      if (!version) return;
      const { properties } = version;
      const newEditableProperties: TaskVersionEditableProperties = {
        instructions: properties.instructions ?? '',
        temperature: properties.temperature ?? 0,
        // We don't want to clone the modelId on purpose to avoid reusing the same model
        modelId: UNDEFINED_MODEL,
        variantId: version.properties.task_variant_id ?? '',
      };
      setEditableProperties(newEditableProperties);
      setNewGroupModalOpen(true);
    },
    [setEditableProperties, setNewGroupModalOpen, versionById]
  );

  const { compatibleModels: models } = useCompatibleAIModels({
    tenant,
    taskId,
    taskSchemaId,
  });

  const createVersion = useVersions((state) => state.createVersion);
  const saveVersion = useVersions((state) => state.saveVersion);

  const addOrReuseVersion = useCallback(
    async (properties: TaskVersionEditableProperties) => {
      if (!properties.modelId) return false;

      const result = await createVersion(tenant, taskId, taskSchemaId, {
        properties: {
          model: properties.modelId,
          instructions: properties.instructions,
          temperature: properties.temperature,
          task_variant_id: properties.variantId,
        },
      });
      const saveResult = await saveVersion(tenant, taskId, result.id);

      if (!!saveResult && !!saveResult.iteration) {
        const iterations = new Set(benchmarkIterations);
        iterations.add(result.iteration);
        await updateBenchmarkIterations(iterations);
      }

      return true;
    },
    [createVersion, saveVersion, tenant, taskId, taskSchemaId, benchmarkIterations, updateBenchmarkIterations]
  );

  const onOpenTaskRuns = useCallback(
    (version: string, state: 'positive' | 'negative' | 'unsure') => {
      const params: Params = {
        field_name: 'version,review',
        operator: 'is,is',
        value: `${version},${state}`,
      };

      redirectWithParams({
        path: taskRunsRoute(tenant, taskId, taskSchemaId, params),
      });
    },
    [redirectWithParams, tenant, taskId, taskSchemaId]
  );

  const emptyStateCopy = useMemo(() => {
    if (!isInitialized) {
      return undefined;
    }

    if (versions.length === 0 && !!task?.name) {
      return `Run ${task.name} at least once to create a version to benchmark`;
    }

    if (benchmark?.results.length === 0) {
      return 'Select one or more versions to benchmark';
    }

    return undefined;
  }, [isInitialized, benchmark, versions, task]);

  const closeNewGroupModal = useCallback(() => {
    setNewGroupModalOpen(false);
  }, []);

  const { findIconURLForModel } = useOrFetchSchemaAIModels({
    tenant,
    taskId,
    taskSchemaId,
  });

  const { isInDemoMode } = useDemoMode();

  const { evaluationInputs, isLoading: isEvaluationInputsLoading } = useOrFetchEvaluationInputs(
    tenant,
    taskId,
    taskSchemaId
  );

  const areThereAnyReviews = !!evaluationInputs && evaluationInputs.length > 0;
  const numberOfVersions = !!versions ? versions.length : 0;

  const entriesForEmptyState = useMemo(() => {
    const areThereAnyRuns = areThereAnyReviews;
    const isThereMoreThenOneVersion = versions?.length > 1;

    return [
      {
        title: 'Review Runs',
        subtitle: 'We recommend starting with 10–20 evaluated runs, depending on the complexity of your AI feature.',
        imageURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/EmptyPageImage2.jpg',
        state: areThereAnyRuns,
      },
      {
        title: 'Save at Least Two Versions',
        subtitle: 'Save versions to be able to benchmark and easily find them again.',
        imageURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/EmptyPageImage4.jpg',
        state: isThereMoreThenOneVersion,
      },
      {
        title: '🎉 Compare Versions',
        subtitle: 'You’ll see clearly how the versions stack up against each other in accuracy, price, and latency.',
        imageURL: 'https://workflowai.blob.core.windows.net/workflowai-public/landing/EmptyPageImage5.jpg',
        state: undefined,
      },
    ];
  }, [versions, areThereAnyReviews]);

  if (numberOfVersions < 2 || !areThereAnyReviews) {
    return (
      <PageContainer
        task={task}
        isInitialized={isInitialized}
        name='Benchmarks'
        showCopyLink={true}
        showBottomBorder={true}
        documentationLink='https://docs.workflowai.com/features/benchmarks'
      >
        <EmptyStateComponent
          title='Benchmarks'
          subtitle='Compares versions to find the most effective based on accuracy, cost, and latency. Your thumbs up or down helps build the benchmark for that version.'
          info='After Runs have been reviewed and at least two versions saved, you’ll be able to start benchmarking '
          documentationLink='https://docs.workflowai.com/features/benchmarks'
          entries={entriesForEmptyState}
        />
      </PageContainer>
    );
  }

  if (isEvaluationInputsLoading || isVersionsLoading) {
    return <Loader centered />;
  }

  return (
    <PageContainer
      task={task}
      isInitialized={isInitialized}
      name='Benchmarks'
      showCopyLink={true}
      showBottomBorder={true}
      documentationLink='https://docs.workflowai.com/features/benchmarks'
    >
      <div className='flex flex-row w-full h-full'>
        <div className='flex flex-col w-[215px] h-full flex-shrink-0 border-r border-dashed border-gray-200'>
          <PageSection title='Versions' />
          <BenchmarkVersionSelection
            versions={versions}
            versionsPerEnvironment={versionsPerEnvironment}
            benchmarkIterations={benchmarkIterations}
            updateBenchmarkIterations={updateBenchmarkIterations}
          />
        </div>
        <div className='flex flex-col h-full w-full overflow-auto bg-gradient-to-b from-white/60 to-white/0'>
          <PageSection title='Overview' />

          {!isInitialized && (
            <div className='flex flex-col gap-2 items-center justify-center w-full h-[160px] shrink-0'>
              <Loader />
            </div>
          )}

          {emptyStateCopy && isInitialized && (
            <div className='flex flex-col gap-2 items-center justify-center w-full h-[160px] shrink-0'>
              <MultiselectLtr16Regular className='text-gray-500' />
              <div className='text-gray-500 text-[13px]'>{emptyStateCopy}</div>
            </div>
          )}

          {!emptyStateCopy && isInitialized && (
            <BenchmarksGroupTable
              versionByIteration={versionByIteration}
              benchmarkResults={benchmark?.results ?? []}
              bestOnes={bestOnes}
              onClone={onClone}
              onTryInPlayground={onTryInPlayground}
              onViewCode={onViewCode}
              onDeploy={onDeployToClick}
              onOpenTaskRuns={onOpenTaskRuns}
              findIconURLForModel={findIconURLForModel}
              isInDemoMode={isInDemoMode}
            />
          )}
          <PageSection title='Price & Latency' showTopBorder />
          <div className='flex w-full flex-shrink-0 p-4'>
            <BenchmarkGraph
              kind='latency'
              bestOnes={bestOnes}
              benchmarkResultsDictionary={benchmarkResultsDictionary}
              selectedIterations={benchmarkIterations}
              versionByIteration={versionByIteration}
            />
          </div>
          <PageSection title='Accuracy & Price' showTopBorder />
          <div className='flex w-full flex-shrink-0 p-4'>
            <BenchmarkGraph
              kind='accuracy'
              bestOnes={bestOnes}
              benchmarkResultsDictionary={benchmarkResultsDictionary}
              selectedIterations={benchmarkIterations}
              versionByIteration={versionByIteration}
            />
          </div>
        </div>
        <NewGroupModal
          tenant={tenant}
          taskId={taskId}
          taskSchemaId={taskSchemaId}
          open={newGroupModalOpen}
          onClose={closeNewGroupModal}
          addOrReuseVersion={addOrReuseVersion}
          versionWasNotAddedAlertTitle='Version Already Benchmarked'
          versionWasNotAddedAlertBody='Looks like this version already exists in your benchmark! No need to create another.'
          models={models}
          editableProperties={editableProperties}
          setEditableProperties={setEditableProperties}
        />
      </div>
    </PageContainer>
  );
}
