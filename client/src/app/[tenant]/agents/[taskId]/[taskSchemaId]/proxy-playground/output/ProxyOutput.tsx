'use client';

import { ColumnDoubleCompare20Filled, ColumnDoubleCompare20Regular } from '@fluentui/react-icons';
import { Plus } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { useNewTaskModal } from '@/components/NewTaskModal/NewTaskModal';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { useOrFetchOrganizationSettings } from '@/store';
import { JsonSchema } from '@/types';
import { Model } from '@/types/aliases';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { RunV1, VersionV1 } from '@/types/workflowAI';
import { TaskInputDict } from '@/types/workflowAI';
import { ModelResponse } from '@/types/workflowAI';
import { FreeCreditsLimitReachedInfo } from '../../playground/FreeCreditsLimitReachedInfo';
import { useMinimumCostTaskRun } from '../../playground/hooks/useMinimumCostTaskRun';
import { useMinimumLatencyTaskRun } from '../../playground/hooks/useMinimumLatencyTaskRun';
import { TaskRunner } from '../../playground/hooks/useTaskRunners';
import { PlaygroundModels } from '../../playground/hooks/utils';
import { ProxyModelOutput } from './ProxyModelOutput';

type Props = {
  aiModels: ModelResponse[];
  areInstructionsLoading: boolean;
  errorForModels: Omit<Map<string, Error>, 'set' | 'clear' | 'delete'>;
  models: PlaygroundModels;
  onModelsChange: (index: number, newModel: Model | null | undefined) => void;
  outputSchema: JsonSchema | undefined;
  tenant: TenantID | undefined;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  taskRunners: [TaskRunner, TaskRunner, TaskRunner];
  versionsForRuns: Record<string, VersionV1>;
  showDiffMode: boolean;
  setShowDiffMode: (showDiffMode: boolean) => void;
  maxHeight: number | undefined;
  addModelColumn: () => void;
  hideModelColumn: (index: number) => void;
  hiddenModelColumns: number[] | undefined;
  updateInputAndRun: (input: TaskInputDict) => Promise<void>;
  setVersionIdForCode: (versionId: string | undefined) => void;
};

export function ProxyOutput(props: Props) {
  const {
    taskRunners,
    versionsForRuns,
    showDiffMode,
    setShowDiffMode,
    addModelColumn,
    hideModelColumn,
    maxHeight,
    hiddenModelColumns,
    updateInputAndRun,
    aiModels,
    areInstructionsLoading,
    errorForModels,
    models,
    onModelsChange,
    outputSchema,
    taskId,
    taskSchemaId,
    tenant,
    setVersionIdForCode,
  } = props;

  const toggleShowDiffMode = useCallback(() => {
    setShowDiffMode(!showDiffMode);
  }, [showDiffMode, setShowDiffMode]);

  const { result: filteredTaskRunners, indexesDict } = useMemo(() => {
    const indexesDict = new Map<number, number>();
    const result: TaskRunner[] = [];

    taskRunners.forEach((taskRunner, index) => {
      if (hiddenModelColumns?.includes(index)) {
        return;
      }

      result.push(taskRunner);
      indexesDict.set(result.length - 1, index);
    });

    return { result, indexesDict };
  }, [taskRunners, hiddenModelColumns]);

  const referenceValue = useMemo(() => {
    if (!showDiffMode) {
      return undefined;
    }
    return filteredTaskRunners[0].data?.task_output;
  }, [filteredTaskRunners, showDiffMode]);

  const isHideModelColumnAvaible = useMemo(() => {
    return filteredTaskRunners.length > 1;
  }, [filteredTaskRunners]);

  const isAddModelColumnAvaible = useMemo(() => {
    return filteredTaskRunners.length < 3;
  }, [filteredTaskRunners]);

  const taskRuns = useMemo(() => {
    const result: RunV1[] = [];
    for (const taskRunner of filteredTaskRunners) {
      if (taskRunner.data) {
        result.push(taskRunner.data);
      }
    }
    return result;
  }, [filteredTaskRunners]);

  const minimumCostTaskRun = useMinimumCostTaskRun(taskRuns);
  const minimumLatencyTaskRun = useMinimumLatencyTaskRun(taskRuns);

  const { isLoggedOut, isInDemoMode } = useDemoMode();
  const { noCreditsLeft } = useOrFetchOrganizationSettings(isLoggedOut ? 30000 : undefined);

  const shouldShowFreeCreditsLimitReachedInfo = useMemo(() => {
    if (!isLoggedOut) {
      return false;
    }
    return noCreditsLeft;
  }, [noCreditsLeft, isLoggedOut]);

  const notFilteredIndex = useCallback(
    (index: number) => {
      const allTaskRunnersIndex = indexesDict.get(index);
      if (allTaskRunnersIndex === undefined) {
        return index;
      }
      return allTaskRunnersIndex;
    },
    [indexesDict]
  );

  const onHideModelColumn = useCallback(
    (index: number) => {
      const allTaskRunnersIndex = indexesDict.get(index);
      if (allTaskRunnersIndex === undefined) {
        return;
      }
      hideModelColumn(allTaskRunnersIndex);
    },
    [hideModelColumn, indexesDict]
  );

  const [isHovering, setIsHovering] = useState(false);
  const { openModal: openEditTaskModal } = useNewTaskModal();
  const { checkIfAllowed } = useIsAllowed();

  const openEditSchemaModal = useCallback(async () => {
    if (!checkIfAllowed()) return;
    openEditTaskModal({
      mode: 'editSchema',
      redirectToPlaygrounds: 'false',
    });
  }, [checkIfAllowed, openEditTaskModal]);

  return (
    <div
      className='flex flex-col w-full overflow-hidden'
      style={maxHeight ? { maxHeight } : undefined}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <div className='w-full flex items-center justify-between px-4 h-[50px] shrink-0 border-b border-dashed border-gray-200'>
        <div className='flex flex-row items-center gap-3.5'>
          <div className='font-semibold text-gray-700 text-base'>Assistant Messages</div>
          {isHovering && (
            <Button
              variant='newDesign'
              onClick={openEditSchemaModal}
              className='h-7 px-2 text-xs'
              size='none'
              disabled={isInDemoMode}
            >
              Edit Schema
            </Button>
          )}
        </div>
        <div className='flex items-center gap-2'>
          <SimpleTooltip content={showDiffMode ? 'Hide differences' : 'Show differences'}>
            <Button
              className='w-7 h-7'
              variant='newDesign'
              size='none'
              icon={showDiffMode ? <ColumnDoubleCompare20Filled /> : <ColumnDoubleCompare20Regular />}
              onClick={toggleShowDiffMode}
            />
          </SimpleTooltip>
          <Button
            className='sm:flex hidden'
            variant='newDesign'
            size='sm'
            icon={<Plus className='h-4 w-4' strokeWidth={2} />}
            onClick={addModelColumn}
            disabled={!isAddModelColumnAvaible}
          >
            Add Model
          </Button>
        </div>
      </div>
      {shouldShowFreeCreditsLimitReachedInfo ? (
        <div className='flex w-full h-[250px] items-center justify-center'>
          <FreeCreditsLimitReachedInfo />
        </div>
      ) : (
        <div className='flex flex-col sm:flex-row sm:flex-1 px-2 overflow-hidden'>
          {filteredTaskRunners.map((taskRunner, index) => (
            <ProxyModelOutput
              aiModels={aiModels}
              areInstructionsLoading={areInstructionsLoading}
              errorForModels={errorForModels}
              models={models}
              onModelsChange={onModelsChange}
              outputSchema={outputSchema}
              taskId={taskId}
              taskSchemaId={taskSchemaId}
              tenant={tenant}
              version={!!taskRunner.data?.version.id ? versionsForRuns[taskRunner.data?.version.id] : undefined}
              index={notFilteredIndex(index)}
              key={`${taskRunner.data?.id}-${notFilteredIndex(index)}`}
              minimumCostTaskRun={minimumCostTaskRun}
              minimumLatencyTaskRun={minimumLatencyTaskRun}
              taskRunner={taskRunner}
              referenceValue={index > 0 ? referenceValue : undefined}
              isHideModelColumnAvaible={isHideModelColumnAvaible}
              hideModelColumn={() => onHideModelColumn(index)}
              updateInputAndRun={updateInputAndRun}
              setVersionIdForCode={setVersionIdForCode}
            />
          ))}
        </div>
      )}
    </div>
  );
}
