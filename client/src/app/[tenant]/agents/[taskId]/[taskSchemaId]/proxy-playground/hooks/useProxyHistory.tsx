import { useEffect } from 'react';
import { QueryParam } from '@/lib/queryString';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';

export function getFromProxyHistory<T>(historyId: string | undefined, key: string): T | undefined {
  if (!historyId) {
    return undefined;
  }

  const fullKey = historyId + '-' + key;
  const item = sessionStorage.getItem(fullKey);

  if (item === null) {
    return undefined;
  }

  try {
    return JSON.parse(item) as T;
  } catch (error) {
    console.error('Failed to parse stored input:', error);
    sessionStorage.removeItem(fullKey);
    return undefined;
  }
}

export function useSaveToProxyHistory<T>(historyId: string | undefined, key: string, value: T | undefined) {
  useEffect(() => {
    if (value === undefined) {
      sessionStorage.removeItem(historyId + '-' + key);
    } else {
      sessionStorage.setItem(historyId + '-' + key, JSON.stringify(value));
    }
  }, [value, historyId, key]);
}

export function saveToProxyHistory<T>(historyId: string | undefined, key: string, value: T | undefined) {
  if (value === undefined) {
    sessionStorage.removeItem(historyId + '-' + key);
  } else {
    sessionStorage.setItem(historyId + '-' + key, JSON.stringify(value));
  }
}

export function saveSearchParamsToHistory(
  tenant: TenantID | undefined,
  taskId: TaskID | undefined,
  taskSchemaId: TaskSchemaID | undefined,
  params: Record<string, QueryParam>
) {
  const historyId = `${tenant}-${taskId}-${taskSchemaId}`;
  saveToProxyHistory(historyId, 'params', params);
}

export function getSearchParamsFromHistory(
  tenant: TenantID | undefined,
  taskId: TaskID | undefined,
  taskSchemaId: TaskSchemaID | undefined
): Record<string, QueryParam> | undefined {
  const historyId = `${tenant}-${taskId}-${taskSchemaId}`;
  return getFromProxyHistory(historyId, 'params');
}
