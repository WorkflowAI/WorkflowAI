import { filterActiveTasksIDs } from '@/lib/taskUtils';
import { AgentStat, SerializableTask } from '@/types/workflowAI';

export enum TasksSortKey {
  Runs = 'runs',
  Cost = 'cost',
}

export function filterTasks(tasks: SerializableTask[], searchQuery: string) {
  // If search query is empty, return all tasks
  if (!searchQuery.trim()) {
    return tasks;
  }

  // Split the search query into individual words and convert to lowercase
  const searchTerms = searchQuery
    .toLowerCase()
    .split(' ')
    .filter((term) => term.length > 0);

  if (searchTerms.length === 0) {
    return tasks;
  }

  // Filter tasks that match all search terms
  return tasks.filter((task) => {
    const key = `${task.name} ${task.id}`.toLowerCase();
    // Check if all search terms are included in the task name
    return searchTerms.every((term) => key.includes(term));
  });
}

export function sortTasks(tasks: SerializableTask[]) {
  const activeTasksIds = filterActiveTasksIDs(tasks);

  return tasks.toSorted((a, b) => {
    // First priority: run_count
    if (!!a.run_count && !!b.run_count) {
      return b.run_count - a.run_count;
    }

    if (!a.run_count && !!b.run_count) {
      return 1;
    }
    if (!!a.run_count && !b.run_count) {
      return -1;
    }

    // Second priority: active status
    const aIsActive = activeTasksIds.includes(a.id);
    const bIsActive = activeTasksIds.includes(b.id);

    if (aIsActive && !bIsActive) {
      return -1;
    }
    if (!aIsActive && bIsActive) {
      return 1;
    }

    // Last priority: alphabetical by name/id
    const aName = a.name.length === 0 ? a.id : a.name;
    const bName = b.name.length === 0 ? b.id : b.name;
    return aName.localeCompare(bName);
  });
}

export function sortTasksByStats(
  tasks: SerializableTask[],
  stats: Map<number, AgentStat> | undefined,
  sortKey: TasksSortKey,
  revertOrder: boolean
) {
  const sorted = tasks.toSorted((a, b) => {
    const aStat = stats?.get(a.uid);
    const bStat = stats?.get(b.uid);

    const aValue = sortKey === TasksSortKey.Runs ? aStat?.run_count ?? 0 : aStat?.total_cost_usd ?? 0;
    const bValue = sortKey === TasksSortKey.Runs ? bStat?.run_count ?? 0 : bStat?.total_cost_usd ?? 0;

    return bValue - aValue;
  });

  return revertOrder ? sorted.reverse() : sorted;
}
