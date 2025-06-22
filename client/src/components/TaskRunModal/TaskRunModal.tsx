'use client';

import { redirect, useSearchParams } from 'next/navigation';
import { useCallback, useMemo, useState } from 'react';
import { checkSchemaForProxy } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/utils';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { Loader } from '@/components/ui/Loader';
import { TASK_RUN_ID_PARAM } from '@/lib/constants';
import { useFavoriteToggle } from '@/lib/hooks/useFavoriteToggle';
import { useRedirectWithParams } from '@/lib/queryString';
import { taskSchemaRoute } from '@/lib/routeFormatter';
import { useOrFetchRunV1, useOrFetchSchema, useOrFetchTaskRunTranscriptions, useOrFetchVersion } from '@/store';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { TaskRunView } from './TaskRunView';
import { ProxyRunView } from './proxy/ProxyRunView';

type TaskRunModalProps = {
  taskId: TaskID;
  tenant: TenantID | undefined;
  taskSchemaIdFromParams: TaskSchemaID;
  onClose: () => void;
  open: boolean;
  showPlaygroundButton?: boolean;
  runId: string;
  taskRunIds?: string[];
};

export default function TaskRunModal(props: TaskRunModalProps) {
  const { onClose, open, showPlaygroundButton, taskId, runId, taskSchemaIdFromParams, taskRunIds, tenant } = props;
  const { run: taskRun, isInitialized } = useOrFetchRunV1(tenant, taskId, runId);
  const { version } = useOrFetchVersion(tenant, taskId, taskRun?.version.id);
  const [isPrevNextBtnCooldown, setIsPrevNextBtnCooldown] = useState<boolean>(false);
  const [showMetadataModal, setShowMetadataModal] = useState(false);
  const { redirectWithParams } = useRedirectWithParams();

  const taskSchemaId = (taskRun?.task_schema_id ?? taskSchemaIdFromParams) as TaskSchemaID;

  const { taskSchema: schema } = useOrFetchSchema(tenant, taskId, taskSchemaId);

  const taskRunIndex = useMemo(() => taskRunIds?.findIndex((id) => id === runId) || 0, [runId, taskRunIds]);
  const runsLength = taskRunIds?.length ?? 0;

  const { run: prevTaskRun } = useOrFetchRunV1(tenant, taskId, taskRunIds?.[taskRunIndex - 1]);
  const { run: nextTaskRun } = useOrFetchRunV1(tenant, taskId, taskRunIds?.[taskRunIndex + 1]);

  const {} = useOrFetchSchema(
    tenant,
    taskId,
    !!prevTaskRun?.task_schema_id ? (`${prevTaskRun.task_schema_id}` as TaskSchemaID) : undefined
  );
  const {} = useOrFetchSchema(
    tenant,
    taskId,
    !!nextTaskRun?.task_schema_id ? (`${nextTaskRun.task_schema_id}` as TaskSchemaID) : undefined
  );

  useOrFetchVersion(tenant, taskId, prevTaskRun?.version.id);
  useOrFetchVersion(tenant, taskId, nextTaskRun?.version.id);

  const { transcriptions } = useOrFetchTaskRunTranscriptions(tenant, taskId, runId);

  const { handleFavoriteToggle } = useFavoriteToggle({
    tenant,
    taskId,
  });

  const onFavoriteToggle = useCallback(() => {
    if (!version) {
      return;
    }
    handleFavoriteToggle(version);
  }, [handleFavoriteToggle, version]);

  const onPrev = useCallback(() => {
    if (isPrevNextBtnCooldown) {
      return;
    }
    if (taskRunIndex <= 0 || !taskRunIds) {
      return;
    }
    const newRunId = taskRunIds[taskRunIndex - 1];
    if (newRunId) {
      redirectWithParams({
        params: { runId: newRunId },
      });
    }
  }, [taskRunIndex, redirectWithParams, taskRunIds, isPrevNextBtnCooldown]);

  const onNext = useCallback(() => {
    if (isPrevNextBtnCooldown) {
      return;
    }
    if (taskRunIndex >= runsLength - 1 || !taskRunIds) {
      return;
    }
    const newRunId = taskRunIds[taskRunIndex + 1];
    if (newRunId) {
      redirectWithParams({
        params: { runId: newRunId },
      });
    }
  }, [taskRunIndex, redirectWithParams, taskRunIds, runsLength, isPrevNextBtnCooldown]);

  const playgroundInputRoute = useMemo(() => {
    if (!showPlaygroundButton) {
      return undefined;
    }
    return taskSchemaRoute(tenant, taskId, taskSchemaId, {
      inputRunId: runId,
    });
  }, [showPlaygroundButton, tenant, taskId, taskSchemaId, runId]);

  const playgroundFullRoute = useMemo(() => {
    if (!showPlaygroundButton) {
      return undefined;
    }

    return taskSchemaRoute(tenant, taskId, taskSchemaId, {
      versionId: version?.id,
      runId1: runId,
    });
  }, [showPlaygroundButton, tenant, taskId, taskSchemaId, runId, version]);

  const isProxy = useMemo(() => {
    if (!schema) {
      return false;
    }
    return checkSchemaForProxy(schema);
  }, [schema]);

  if (taskRun && taskRun.task_id !== taskId) {
    return redirect(taskSchemaRoute(tenant, taskId, taskSchemaId));
  }

  return (
    <div>
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className='min-w-[90vw] min-h-[90vh] max-h-[90vh] h-[90vh] p-0 rounded-[2px]'>
          {!taskRun || !schema || !version ? (
            <Loader centered />
          ) : isProxy ? (
            <ProxyRunView
              onClose={onClose}
              onNext={onNext}
              onPrev={onPrev}
              runIndex={taskRunIndex}
              totalModalRuns={runsLength}
              tenant={tenant}
              run={taskRun}
              schema={schema}
              playgroundFullRoute={playgroundFullRoute}
              version={version}
            />
          ) : (
            <TaskRunView
              tenant={tenant}
              isInitialized={isInitialized}
              onClose={onClose}
              onFavoriteToggle={onFavoriteToggle}
              onNext={onNext}
              onPrev={onPrev}
              playgroundInputRoute={playgroundInputRoute}
              playgroundFullRoute={playgroundFullRoute}
              schemaInput={schema?.input_schema}
              schemaOutput={schema?.output_schema}
              version={version}
              taskRun={taskRun}
              taskRunIndex={taskRunIndex}
              totalModalRuns={runsLength}
              transcriptions={transcriptions}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function useRunIDParam() {
  const params = useSearchParams();
  const redirectWithParams = useRedirectWithParams();
  const runId = params.get(TASK_RUN_ID_PARAM);

  const setRunId = useCallback(
    (runId: string | undefined) => {
      redirectWithParams({
        params: { runId: runId },
      });
    },
    [redirectWithParams]
  );

  const clearRunId = useCallback(() => {
    redirectWithParams({
      params: { runId: undefined },
    });
  }, [redirectWithParams]);

  return { runId, setRunId, clearRunId };
}
