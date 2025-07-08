'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { Loader } from '@/components/ui/Loader';
import { taskSchemaRoute } from '@/lib/routeFormatter';
import { getNewestSchemaId } from '@/lib/taskUtils';
import { useOrFetchTask } from '@/store';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';

type TaskPageProps = {
  taskId: TaskID;
  tenant: TenantID;
};

function TaskPage(props: TaskPageProps) {
  const { taskId, tenant } = props;
  const { task: currentTask } = useOrFetchTask(tenant, taskId);
  const newestTaskSchemaId = getNewestSchemaId(currentTask);
  const router = useRouter();

  useEffect(() => {
    if (newestTaskSchemaId && currentTask !== undefined) {
      router.push(taskSchemaRoute(tenant, taskId, `${newestTaskSchemaId}` as TaskSchemaID));
    }
  }, [newestTaskSchemaId, router, tenant, taskId, currentTask]);

  return <Loader centered />;
}

export default function TaskNamePage({ params: { taskId, tenant } }: { params: { taskId: TaskID; tenant: TenantID } }) {
  return <TaskPage taskId={taskId} tenant={tenant} />;
}
