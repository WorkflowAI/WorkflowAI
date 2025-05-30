import { useState } from 'react';
import { useLoggedInTenantID, useTaskParams } from '@/lib/hooks/useTaskParams';
import { cn } from '@/lib/utils';
import { useOrFetchClerkOrganization, useOrFetchTasks } from '@/store';
import { TaskSchemaID } from '@/types/aliases';
import { SerializableTask } from '@/types/workflowAI';
import { PagePath } from './PagePath';

type PageHeaderProps = {
  task: SerializableTask;
  name: string | React.ReactNode;
  className?: string;
  children?: React.ReactNode;
  showSchema: boolean;
  documentationLink?: string;
  schemaId?: TaskSchemaID;
};

export function PageHeader(props: PageHeaderProps) {
  const { task, name, className, children, showSchema, documentationLink, schemaId } = props;
  const { tenant, taskSchemaId: urlSchemaId } = useTaskParams();

  const [taskPopoverOpen, setTaskPopoverOpen] = useState(false);

  const loggedInTenant = useLoggedInTenantID();
  const { organization } = useOrFetchClerkOrganization(tenant);
  const { organization: userOrganization } = useOrFetchClerkOrganization(loggedInTenant);
  const showOrganization = loggedInTenant !== tenant;

  const { tasks } = useOrFetchTasks(loggedInTenant ?? tenant);

  return (
    <div className={cn('flex sm:flex-row flex-col w-full sm:py-0 py-3 items-center justify-between', className)}>
      <PagePath
        tasks={tasks}
        taskPopoverOpen={taskPopoverOpen}
        setTaskPopoverOpen={setTaskPopoverOpen}
        task={task}
        organization={organization}
        userOrganization={userOrganization}
        showOrganization={showOrganization}
        tenant={tenant}
        taskSchemaId={schemaId ?? urlSchemaId}
        showSchema={showSchema}
        documentationLink={documentationLink}
        name={name}
      />
      <div className='flex flex-row sm:w-fit w-full gap-2 justify-end items-center'>{children}</div>
    </div>
  );
}
