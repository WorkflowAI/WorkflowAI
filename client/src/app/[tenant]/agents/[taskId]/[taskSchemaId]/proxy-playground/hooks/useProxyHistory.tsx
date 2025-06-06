import { useEffect } from 'react';
import { QueryParam } from '@/lib/queryString';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { TaskSchemaID } from '@/types/aliases';

// Helper function to safely store data
function safeSetItem(key: string, value: string): boolean {
  try {
    sessionStorage.setItem(key, value);
    return true;
  } catch (error) {
    if (error instanceof Error && error.name === 'QuotaExceededError') {
      console.warn('Storage quota exceeded for key:', key);
      return false;
    }
    console.error('Error storing data:', error);
    return false;
  }
}

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
    if (!historyId) return;

    const fullKey = historyId + '-' + key;
    if (value === undefined) {
      sessionStorage.removeItem(fullKey);
    } else {
      const stringValue = JSON.stringify(value);
      // Check if the value is too large (e.g., > 1MB)
      if (stringValue.length > 1024 * 1024) {
        console.warn('Value too large to store in sessionStorage:', key);
        return;
      }
      safeSetItem(fullKey, stringValue);
    }
  }, [value, historyId, key]);
}

export function saveToProxyHistory<T>(historyId: string | undefined, key: string, value: T | undefined) {
  if (!historyId) return;

  const fullKey = historyId + '-' + key;
  if (value === undefined) {
    sessionStorage.removeItem(fullKey);
  } else {
    const stringValue = JSON.stringify(value);
    // Check if the value is too large (e.g., > 1MB)
    if (stringValue.length > 1024 * 1024) {
      console.warn('Value too large to store in sessionStorage:', key);
      return;
    }
    safeSetItem(fullKey, stringValue);
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
