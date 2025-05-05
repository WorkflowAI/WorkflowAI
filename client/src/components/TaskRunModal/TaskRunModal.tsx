'use client';

import { redirect, useSearchParams } from 'next/navigation';
import { useCallback, useMemo } from 'react';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { TASK_RUN_ID_PARAM } from '@/lib/constants';
import { useFavoriteToggle } from '@/lib/hooks/useFavoriteToggle';
import { useRedirectWithParams } from '@/lib/queryString';
import { taskSchemaRoute } from '@/lib/routeFormatter';
import { useOrFetchTaskRun, useOrFetchTaskRunTranscriptions, useOrFetchTaskSchema, useOrFetchVersion } from '@/store';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { TaskRunView } from './TaskRunView';

type TaskRunModalProps = {
  taskId: TaskID;
  tenant: TenantID | undefined;
  taskSchemaIdFromParams: TaskSchemaID;
  onClose: () => void;
  open: boolean;
  showPlaygroundButton?: boolean;
  taskRunId: string;
  taskRunIds?: string[];
};

export default function TaskRunModal(props: TaskRunModalProps) {
  const { onClose, open, showPlaygroundButton, taskId, taskRunId, taskSchemaIdFromParams, taskRunIds, tenant } = props;
  const { taskRun, isInitialized } = useOrFetchTaskRun(tenant, taskId, taskRunId);

  const taskSchemaId = (taskRun?.task_schema_id ?? taskSchemaIdFromParams) as TaskSchemaID;

  const { taskSchema: currentTaskSchema } = useOrFetchTaskSchema(tenant, taskId, taskSchemaId);

  const taskRunIndex = useMemo(() => taskRunIds?.findIndex((id) => id === taskRunId) || 0, [taskRunId, taskRunIds]);
  const runsLength = taskRunIds?.length ?? 0;

  useOrFetchTaskRun(tenant, taskId, taskRunIds?.[taskRunIndex - 1] || '');
  useOrFetchTaskRun(tenant, taskId, taskRunIds?.[taskRunIndex + 1] || '');

  const { transcriptions } = useOrFetchTaskRunTranscriptions(tenant, taskId, taskRunId);

  const { handleFavoriteToggle } = useFavoriteToggle({
    tenant,
    taskId,
  });

  const { version } = useOrFetchVersion(tenant, taskId, taskRun?.group.id);

  const onFavoriteToggle = useCallback(() => {
    if (!version) {
      return;
    }
    handleFavoriteToggle(version);
  }, [handleFavoriteToggle, version]);

  const redirectWithParams = useRedirectWithParams();

  const onPrev = useCallback(() => {
    if (taskRunIndex <= 0 || !taskRunIds) {
      return;
    }
    const newTaskRunId = taskRunIds[taskRunIndex - 1];
    if (newTaskRunId) {
      redirectWithParams({
        params: { taskRunId: newTaskRunId },
      });
    }
  }, [taskRunIndex, redirectWithParams, taskRunIds]);

  const onNext = useCallback(() => {
    if (taskRunIndex >= runsLength - 1 || !taskRunIds) {
      return;
    }
    const newTaskRunId = taskRunIds[taskRunIndex + 1];
    if (newTaskRunId) {
      redirectWithParams({
        params: { taskRunId: newTaskRunId },
      });
    }
  }, [taskRunIndex, redirectWithParams, taskRunIds, runsLength]);

  const playgroundInputRoute = useMemo(() => {
    if (!showPlaygroundButton) {
      return undefined;
    }
    return taskSchemaRoute(tenant, taskId, taskSchemaId, {
      inputTaskRunId: taskRunId,
    });
  }, [showPlaygroundButton, tenant, taskId, taskSchemaId, taskRunId]);

  const playgroundFullRoute = useMemo(() => {
    if (!showPlaygroundButton) {
      return undefined;
    }

    return taskSchemaRoute(tenant, taskId, taskSchemaId, {
      inputTaskRunId: taskRunId,
      versionId: version?.id,
      preselectedVariantId: version?.properties.task_variant_id,
    });
  }, [showPlaygroundButton, tenant, taskId, taskSchemaId, taskRunId, version]);

  if (taskRun && taskRun.task_id !== taskId) {
    return redirect(taskSchemaRoute(tenant, taskId, taskSchemaId));
  }

  return (
    <div>
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className='min-w-[90vw] min-h-[90vh] p-0 rounded-[2px]'>
          <TaskRunView
            tenant={tenant}
            isInitialized={isInitialized}
            onClose={onClose}
            onFavoriteToggle={onFavoriteToggle}
            onNext={onNext}
            onPrev={onPrev}
            playgroundInputRoute={playgroundInputRoute}
            playgroundFullRoute={playgroundFullRoute}
            schemaInput={currentTaskSchema?.input_schema}
            schemaOutput={currentTaskSchema?.output_schema}
            version={version}
            taskRun={taskRun}
            taskRunIndex={taskRunIndex}
            totalModalRuns={runsLength}
            transcriptions={transcriptions}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function useRunIDParam() {
  const params = useSearchParams();
  const redirectWithParams = useRedirectWithParams();
  const taskRunId = params.get(TASK_RUN_ID_PARAM);

  const setTaskRunId = useCallback(
    (taskRunId: string | undefined) => {
      redirectWithParams({
        params: { taskRunId: taskRunId },
        scroll: false,
      });
    },
    [redirectWithParams]
  );

  const clearTaskRunId = useCallback(() => {
    redirectWithParams({
      params: { taskRunId: undefined },
      scroll: false,
    });
  }, [redirectWithParams]);

  return { taskRunId, setTaskRunId, clearTaskRunId };
}
