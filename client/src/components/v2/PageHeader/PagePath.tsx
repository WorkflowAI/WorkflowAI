import { TaskSwitcherMode } from '@/app/[tenant]/components/TaskSwitcher';
import { SchemaSelectorContainer, TaskSwitcherContainer } from '@/app/[tenant]/components/TaskSwitcherContainer';
import { OrganizationInformation } from '@/app/api/users/organizations/[organizationId]/route';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { SerializableTask } from '@/types/workflowAI';
import { PageDocumentationLink } from './PageDocumentationLink';
import { TaskSection } from './TaskSection';

type PagePathProps = {
  tasks: SerializableTask[];
  taskPopoverOpen: boolean;
  setTaskPopoverOpen: (open: boolean) => void;
  task: SerializableTask;
  organization: OrganizationInformation | undefined;
  userOrganization: OrganizationInformation | undefined;
  showOrganization: boolean;
  tenant: TenantID;
  taskSchemaId: TaskSchemaID | undefined;
  showSchema: boolean;
  documentationLink?: string;
  name: string | React.ReactNode;
};

export function PagePath(props: PagePathProps) {
  const {
    tasks,
    taskPopoverOpen,
    setTaskPopoverOpen,
    task,
    organization,
    userOrganization,
    showOrganization,
    tenant,
    taskSchemaId,
    showSchema,
    documentationLink,
    name,
  } = props;

  return (
    <div className='flex sm:w-fit w-full flex-row items-center pl-4 sm:pr-0 pr-4'>
      <TaskSwitcherContainer
        mode={TaskSwitcherMode.TASKS}
        tasks={tasks}
        open={taskPopoverOpen}
        setOpen={setTaskPopoverOpen}
        trigger={
          <div className='flex flex-1 overflow-x-hidden'>
            <TaskSection
              task={task}
              organizationName={showOrganization ? organization?.name : undefined}
              isSelected={taskPopoverOpen}
            />
          </div>
        }
        titleForFeatures={showOrganization && !!userOrganization ? `${userOrganization.name}'s AI Agents` : undefined}
      />
      {!!taskSchemaId && showSchema && (
        <SchemaSelectorContainer tenant={tenant} taskId={task.id as TaskID} selectedSchemaId={taskSchemaId} />
      )}
      <PageDocumentationLink name={name} documentationLink={documentationLink} className='sm:flex hidden' />
    </div>
  );
}
