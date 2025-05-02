import { useMemo } from 'react';
import { useOrFetchAllAiModels } from '@/store/fetchers';
import { SideBySideEntry, useSideBySideStore } from '@/store/side_by_side';
import { useTaskRuns } from '@/store/task_runs';
import { buildScopeKey } from '@/store/utils';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { TaskRun } from '@/types/task_run';
import { ModelResponse } from '@/types/workflowAI';
import { useMinimumCostTaskRun } from '../../playground/components/Tab/hooks/useMinimumCostTaskRun';
import { useMinimumLatencyTaskRun } from '../../playground/components/Tab/hooks/useMinimumLatencyTaskRun';

function findEntry(
  runs: Set<SideBySideEntry> | undefined,
  inputHash: string,
  versionId: string | undefined,
  modelId: string | undefined
) {
  if (!runs) {
    return undefined;
  }

  if (!versionId && !modelId) {
    return undefined;
  }

  return Array.from(runs).find(
    (entry) =>
      entry.inputHash === inputHash &&
      ((entry.versionId === versionId && !!versionId) || (entry.modelId === modelId && !!modelId))
  );
}

export type SideBySideRowStats = {
  run: TaskRun | undefined;
  minimumCostRun: TaskRun | undefined;
  minimumLatencyRun: TaskRun | undefined;
  model: ModelResponse | undefined;
  minimumCostModel: ModelResponse | undefined;
};

export function useSideBySideRowStatsEffect(
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  inputHash: string,
  leftVersionId: string | undefined,
  rightVersionId: string | undefined,
  rightModelId: string | undefined
): { left: SideBySideRowStats; right: SideBySideRowStats } {
  const scopeKey = buildScopeKey({
    tenant,
    taskId,
    taskSchemaId,
  });

  const runs = useSideBySideStore((state) => state.runs.get(scopeKey));
  const { models } = useOrFetchAllAiModels({ tenant, taskId, taskSchemaId });

  const leftEntry = useMemo(
    () => findEntry(runs, inputHash, leftVersionId, undefined),
    [runs, inputHash, leftVersionId]
  );

  const rightEntry = useMemo(
    () => findEntry(runs, inputHash, rightVersionId, rightModelId),
    [runs, inputHash, rightVersionId, rightModelId]
  );

  const leftRun = useTaskRuns((state) => (leftEntry?.runId ? state.taskRunsById.get(leftEntry.runId) : undefined));
  const rightRun = useTaskRuns((state) => (rightEntry?.runId ? state.taskRunsById.get(rightEntry.runId) : undefined));

  const minimumCostRun = useMinimumCostTaskRun([leftRun, rightRun]);
  const minimumLatencyRun = useMinimumLatencyTaskRun([leftRun, rightRun]);

  const leftModel = useMemo(
    () => models.find((model) => model.id === leftRun?.group.properties?.model),
    [models, leftRun?.group.properties?.model]
  );

  const rightModel = useMemo(
    () => models.find((model) => model.id === rightRun?.group.properties?.model),
    [models, rightRun?.group.properties?.model]
  );

  const minimumCostModel = useMemo(
    () => models.find((model) => model.id === minimumCostRun?.group.properties?.model),
    [models, minimumCostRun?.group.properties?.model]
  );

  return {
    left: {
      run: leftRun,
      minimumCostRun,
      minimumLatencyRun,
      model: leftModel,
      minimumCostModel: minimumCostModel,
    },
    right: {
      run: rightRun,
      minimumCostRun,
      minimumLatencyRun,
      model: rightModel,
      minimumCostModel: minimumCostModel,
    },
  };
}
