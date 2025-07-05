'use client';

import * as amplitude from '@amplitude/analytics-browser';
import { AppsList20Regular } from '@fluentui/react-icons';
import { PlusIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useMemo } from 'react';
import { useApiKeysModal } from '@/components/ApiKeysModal/ApiKeysModal';
import { NotFoundForNotMatchingTenant } from '@/components/NotFound';
import { Button } from '@/components/ui/Button';
import { PageContainer } from '@/components/v2/PageContainer';
import { NEW_PROXY_AGENT_MODAL_OPEN, useQueryParamModal } from '@/lib/globalModal';
import { useIsAllowed } from '@/lib/hooks/useIsAllowed';
import { useIsSameTenant } from '@/lib/hooks/useTaskParams';
import { taskApiRoute, taskDeploymentsRoute, taskRunsRoute, taskSchemaRoute } from '@/lib/routeFormatter';
import { getNewestSchemaId } from '@/lib/taskUtils';
import { useOrFetchApiKeys, useOrFetchTasks } from '@/store/fetchers';
import { TaskID, TenantID } from '@/types/aliases';
import { SerializableTask } from '@/types/workflowAI';
import { ManageApiKeysButton } from '../[taskId]/[taskSchemaId]/code/ManageApiKeyButton';
import { LoadingTasksTable } from './LoadingTasksTable';
import { NoTasksView } from './NoTasksView';
import { TasksTable } from './TasksTable';
import { sortTasks } from './utils';

type TasksContainerProps = {
  tenant: TenantID;
};

export function TasksContainer(props: TasksContainerProps) {
  const { tenant } = props;
  const router = useRouter();
  const isSameTenant = useIsSameTenant();
  const { tasks, isInitialized } = useOrFetchTasks(tenant);
  const { checkIfSignedIn } = useIsAllowed();

  const sortedTasks = useMemo(() => {
    return sortTasks(tasks);
  }, [tasks]);

  const onTryInPlayground = useCallback(
    (task: SerializableTask) => {
      const schemaId = getNewestSchemaId(task);
      router.push(taskSchemaRoute(tenant, task.id as TaskID, schemaId));
    },
    [router, tenant]
  );

  const onViewRuns = useCallback(
    (task: SerializableTask) => {
      const schemaId = getNewestSchemaId(task);
      const taskId = task.id as TaskID;
      router.push(taskRunsRoute(tenant, taskId, schemaId));
    },
    [router, tenant]
  );

  const onViewCode = useCallback(
    (task: SerializableTask) => {
      const schemaId = getNewestSchemaId(task);
      const taskId = task.id as TaskID;
      router.push(taskApiRoute(tenant, taskId, schemaId));
    },
    [router, tenant]
  );

  const onViewDeployments = useCallback(
    (task: SerializableTask) => {
      const schemaId = getNewestSchemaId(task);
      const taskId = task.id as TaskID;
      router.push(taskDeploymentsRoute(tenant, taskId, schemaId));
    },
    [router, tenant]
  );

  const { apiKeys } = useOrFetchApiKeys(tenant);
  const { openModal: openNewTaskModal } = useQueryParamModal(NEW_PROXY_AGENT_MODAL_OPEN);
  const { openModal: openApiKeysModal } = useApiKeysModal();

  const onNewTask = useCallback(() => {
    if (!checkIfSignedIn()) return;
    amplitude.track('user.clicked.new_task');
    openNewTaskModal();
  }, [openNewTaskModal, checkIfSignedIn]);

  if (!isSameTenant) {
    return <NotFoundForNotMatchingTenant tenant={tenant} />;
  }

  return (
    <PageContainer
      task={undefined}
      isInitialized={true}
      name={
        <div className='flex flex-row gap-3 items-center'>
          <AppsList20Regular className='w-5 h-5 text-gray-500' />
          <div className='text-[16px] font-semibold text-gray-700'>AI Agents</div>
        </div>
      }
      showCopyLink={false}
      showBottomBorder={true}
      showSchema={false}
      rightBarChildren={
        <div className='flex flex-row gap-2'>
          <ManageApiKeysButton
            apiKeys={apiKeys}
            openApiKeysModal={openApiKeysModal}
            disabled={false}
            buttonVariant='newDesign'
          />
          <Button variant='newDesign' icon={<PlusIcon className='w-4 h-4' />} onClick={onNewTask}>
            Add WorkflowAI to Cursor (MCP)
          </Button>
        </div>
      }
    >
      <div className='flex w-full h-full p-4'>
        {tasks.length > 0 ? (
          <TasksTable
            tenant={tenant}
            tasks={sortedTasks}
            onTryInPlayground={onTryInPlayground}
            onViewRuns={onViewRuns}
            onViewCode={onViewCode}
            onViewDeployments={onViewDeployments}
          />
        ) : isInitialized ? (
          <div className='flex justify-center w-full pt-[80px]'>
            <NoTasksView onNewTask={onNewTask} />
          </div>
        ) : (
          <LoadingTasksTable />
        )}
      </div>
    </PageContainer>
  );
}
