import { TableViewHeaderEntry } from '@/components/ui/TableView';
import { TasksSortKey } from './utils';

type TasksTableHeadersProps = {
  onSortModeChange: (mode: TasksSortKey) => void;
};

export function TasksTableHeaders(props: TasksTableHeadersProps) {
  const { onSortModeChange } = props;
  return (
    <>
      <TableViewHeaderEntry title='AI agent' className='pl-2 flex-1' />
      <TableViewHeaderEntry
        title='Runs in last 7d'
        className='w-[100px]'
        onClick={() => onSortModeChange(TasksSortKey.Runs)}
      />
      <TableViewHeaderEntry
        title='Cost'
        className='w-[57px]'
        onClick={() => onSortModeChange(TasksSortKey.Cost)}
      />
    </>
  );
}
