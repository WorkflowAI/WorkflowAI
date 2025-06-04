import { TableView } from '@/components/ui/TableView';
import { TenantID } from '@/types/aliases';
import { SerializableTask } from '@/types/workflowAI';
import { TaskRowContainer } from './TaskRow';
import { TasksTableHeaders } from './TasksTableHeaders';
import { TasksSortKey } from './utils';

type TasksTableProps = {
  tenant: TenantID;
  tasks: SerializableTask[];
  onTryInPlayground: (task: SerializableTask) => void;
  onViewRuns: (task: SerializableTask) => void;
  onViewCode: (task: SerializableTask) => void;
  onViewDeployments: (task: SerializableTask) => void;
  onSortModeChange: (mode: TasksSortKey) => void;
};

export function TasksTable(props: TasksTableProps) {
  const { tasks, onTryInPlayground, onViewRuns, onViewCode, onViewDeployments, tenant, onSortModeChange } = props;

  return (
    <TableView headers={<TasksTableHeaders onSortModeChange={onSortModeChange} />}>
      {tasks.map((task) => (
        <TaskRowContainer
          tenant={tenant}
          key={task.id}
          task={task}
          onTryInPlayground={() => onTryInPlayground(task)}
          onViewRuns={() => onViewRuns(task)}
          onViewCode={() => onViewCode(task)}
          onViewDeployments={() => onViewDeployments(task)}
        />
      ))}
    </TableView>
  );
}
