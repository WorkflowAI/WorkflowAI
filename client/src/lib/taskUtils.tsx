import { TaskSchemaID } from '@/types/aliases';
import { SerializableTask } from '@/types/workflowAI';

export function getVisibleSchemaIds(task?: SerializableTask) {
  if (!task) return [];

  const result = new Set<number>();

  task.versions.forEach(({ schema_id, is_hidden }) => {
    if (!is_hidden) {
      result.add(schema_id);
    }
  });

  return Array.from(result)
    .sort((a, b) => b - a)
    .map((id) => id.toString() as TaskSchemaID);
}

export function getNewestSchemaId(task?: SerializableTask): TaskSchemaID {
  if (!task) return '1' as TaskSchemaID;
  const visibleSchemaIds = getVisibleSchemaIds(task);
  if (visibleSchemaIds.length === 0) {
    return (`${task.versions[0].schema_id}` as TaskSchemaID) ?? ('1' as TaskSchemaID);
  }
  return visibleSchemaIds[0];
}

export function getHiddenSchemaIds(task?: SerializableTask) {
  if (!task) return [];

  const result = new Set<number>();

  task.versions.forEach(({ schema_id, is_hidden }) => {
    if (is_hidden) {
      result.add(schema_id);
    }
  });

  return Array.from(result)
    .sort((a, b) => b - a)
    .map((id) => id.toString() as TaskSchemaID);
}

export function getActiveSchemaIds(task?: SerializableTask) {
  if (!task) return [];

  const result = new Set<number>();
  const fortyEightHoursAgo = new Date(Date.now() - 48 * 60 * 60 * 1000);

  task.versions.forEach(({ schema_id, last_active_at }) => {
    if (!!last_active_at) {
      const lastActiveDate = new Date(last_active_at);
      if (lastActiveDate >= fortyEightHoursAgo) {
        result.add(schema_id);
      }
    }
  });

  return Array.from(result)
    .sort((a, b) => b - a)
    .map((id) => id.toString() as TaskSchemaID);
}

export function isActiveTask(task?: SerializableTask) {
  if (!task) return false;
  return getActiveSchemaIds(task).length > 0;
}

export function filterActiveTasksIDs(tasks: SerializableTask[]): string[] {
  return tasks.filter((task) => isActiveTask(task)).map((task) => task.id);
}

export function getLatestActivityDate(task?: SerializableTask): Date | undefined {
  if (!task) return undefined;

  let latest: Date | undefined;
  task.versions.forEach(({ last_active_at }) => {
    if (last_active_at) {
      const current = new Date(last_active_at);
      if (!latest || current > latest) {
        latest = current;
      }
    }
  });

  return latest;
}
