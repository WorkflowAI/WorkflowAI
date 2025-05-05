'use client';

import { Archive16Regular, ArrowCounterclockwise16Regular, Edit16Regular, Open16Filled } from '@fluentui/react-icons';
import { captureException } from '@sentry/nextjs';
import { useRouter } from 'next/navigation';
import { usePathname } from 'next/navigation';
import { useCallback, useMemo } from 'react';
import { toast } from 'sonner';
import { useNewTaskModal } from '@/components/NewTaskModal/NewTaskModal';
import { Button } from '@/components/ui/Button';
import { PageContainer } from '@/components/v2/PageContainer';
import { useDemoMode } from '@/lib/hooks/useDemoMode';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { useTaskSchemaParams } from '@/lib/hooks/useTaskParams';
import { replaceTaskSchemaId, taskSchemaRoute } from '@/lib/routeFormatter';
import { getActiveSchemaIds, getHiddenSchemaIds, getVisibleSchemaIds } from '@/lib/taskUtils';
import { useOrFetchTask, useOrFetchTaskSchema } from '@/store';
import { useTaskSchemas } from '@/store/task_schemas';
import { TaskSchemaID } from '@/types/aliases';
import { SchemasContent } from './schemasContent';

export function SchemasContainer() {
  const { tenant, taskId, taskSchemaId } = useTaskSchemaParams();
  const { taskSchema, isInitialized } = useOrFetchTaskSchema(tenant, taskId, taskSchemaId);
  const { task } = useOrFetchTask(tenant, taskId, true);
  const { openModal: openEditTaskModal } = useNewTaskModal();
  const { checkIfAllowed } = useIsAllowed();
  const router = useRouter();
  const pathname = usePathname();

  const handleOpenEditTaskModal = useCallback(() => {
    if (!checkIfAllowed()) return;
    openEditTaskModal({
      mode: 'editSchema',
      redirectToPlaygrounds: 'true',
      variantId: undefined,
    });
  }, [openEditTaskModal, checkIfAllowed]);

  const visibleSchemaIds = useMemo(() => {
    return getVisibleSchemaIds(task);
  }, [task]);

  const hiddenSchemaIds = useMemo(() => {
    return getHiddenSchemaIds(task);
  }, [task]);

  const activeSchemaIds = useMemo(() => {
    return getActiveSchemaIds(task);
  }, [task]);

  const onTaskSchemaChange = useCallback(
    (schemaId: TaskSchemaID) => {
      if (!taskId) return;
      let newUrl: string;
      if (!taskSchemaId) {
        newUrl = taskSchemaRoute(tenant, taskId, schemaId);
      } else {
        newUrl = replaceTaskSchemaId(pathname, schemaId);
      }
      router.push(newUrl);
    },
    [pathname, router, taskId, tenant, taskSchemaId]
  );

  const isArchived = useMemo(() => {
    return hiddenSchemaIds.includes(taskSchemaId);
  }, [hiddenSchemaIds, taskSchemaId]);

  const { changeTaskSchemaVisibility } = useTaskSchemas();

  const handleRestoreTaskSchema = useCallback(async () => {
    if (!tenant || !taskId || !taskSchemaId) return;

    const promise = changeTaskSchemaVisibility(tenant, taskId, taskSchemaId, true);

    toast.promise(promise, {
      loading: 'Restoring AI agent schema...',
      success: 'AI agent schema restored successfully',
      error: (error) => {
        captureException(error);
        return 'Failed to restore AI agent schema';
      },
    });

    await promise; // This will keep the button in its loading state until the promise resolves
  }, [tenant, taskId, taskSchemaId, changeTaskSchemaVisibility]);

  const handleArchiveTaskSchema = useCallback(async () => {
    if (!tenant || !taskId || !taskSchemaId) return;

    const promise = changeTaskSchemaVisibility(tenant, taskId, taskSchemaId, false);

    toast.promise(promise, {
      loading: 'Archiving AI agent schema...',
      success: 'AI agent schema archived successfully',
      error: (error) => {
        captureException(error);
        return 'Failed to archive AI agent schema';
      },
    });

    await promise; // This will keep the button in its loading state until the promise resolves
  }, [tenant, taskId, taskSchemaId, changeTaskSchemaVisibility]);

  const { isInDemoMode } = useDemoMode();

  return (
    <PageContainer
      task={task}
      isInitialized={true}
      name='Schemas'
      showCopyLink={false}
      showBottomBorder={true}
      showSchema={false}
      documentationLink='https://docs.workflowai.com/concepts/schemas'
      rightBarChildren={
        <div className='flex flex-row items-center gap-2 font-lato'>
          <Button
            onClick={handleOpenEditTaskModal}
            icon={<Edit16Regular />}
            variant='newDesign'
            disabled={isInDemoMode}
          >
            Add or Update Fields
          </Button>
          <Button toRoute={taskSchemaRoute(tenant, taskId, taskSchemaId)} icon={<Open16Filled />} variant='newDesign'>
            Try in Playground
          </Button>
          {isArchived ? (
            <Button
              variant='newDesign'
              icon={<ArrowCounterclockwise16Regular />}
              onClick={handleRestoreTaskSchema}
              disabled={isInDemoMode}
            >
              Restore
            </Button>
          ) : (
            <Button
              variant='newDesign'
              icon={<Archive16Regular />}
              onClick={handleArchiveTaskSchema}
              disabled={isInDemoMode}
            >
              Archive
            </Button>
          )}
        </div>
      }
    >
      <SchemasContent
        currentSchemaId={taskSchemaId}
        taskSchema={taskSchema}
        isInitialized={isInitialized}
        visibleSchemaIds={visibleSchemaIds}
        hiddenSchemaIds={hiddenSchemaIds}
        activeSchemaIds={activeSchemaIds}
        onSelect={onTaskSchemaChange}
      />
    </PageContainer>
  );
}
