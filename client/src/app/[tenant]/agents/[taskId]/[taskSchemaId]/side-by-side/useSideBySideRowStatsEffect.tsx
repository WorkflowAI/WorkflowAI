import { useMemo } from 'react';
import { useOrFetchSchemaAIModels } from '@/store/fetchers';
import { SideBySideEntry, useSideBySideStore } from '@/store/side_by_side';
import { useTaskRuns } from '@/store/task_runs';
import { buildScopeKey } from '@/store/utils';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { ModelResponse, RunV1 } from '@/types/workflowAI';
import { useMinimumCostTaskRun } from '../playground/hooks/useMinimumCostTaskRun';
import { useMinimumLatencyTaskRun } from '../playground/hooks/useMinimumLatencyTaskRun';

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
  run: RunV1 | undefined;
  minimumCostRun: RunV1 | undefined;
  minimumLatencyRun: RunV1 | undefined;
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
  const { models } = useOrFetchSchemaAIModels({ tenant, taskId, taskSchemaId });

  const leftEntry = useMemo(
    () => findEntry(runs, inputHash, leftVersionId, undefined),
    [runs, inputHash, leftVersionId]
  );

  const rightEntry = useMemo(
    () => findEntry(runs, inputHash, rightVersionId, rightModelId),
    [runs, inputHash, rightVersionId, rightModelId]
  );

  const leftRun = useTaskRuns((state) => (leftEntry?.runId ? state.runV1ById.get(leftEntry.runId) : undefined));
  const rightRun = useTaskRuns((state) => (rightEntry?.runId ? state.runV1ById.get(rightEntry.runId) : undefined));

  const minimumCostRun = useMinimumCostTaskRun([leftRun, rightRun]);
  const minimumLatencyRun = useMinimumLatencyTaskRun([leftRun, rightRun]);

  const leftModel = useMemo(
    () => models.find((model) => model.id === leftRun?.version.properties?.model),
    [models, leftRun?.version.properties?.model]
  );

  const rightModel = useMemo(
    () => models.find((model) => model.id === rightRun?.version.properties?.model),
    [models, rightRun?.version.properties?.model]
  );

  const minimumCostModel = useMemo(
    () => models.find((model) => model.id === minimumCostRun?.version.properties?.model),
    [models, minimumCostRun?.version.properties?.model]
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
