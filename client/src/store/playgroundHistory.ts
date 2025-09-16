import { produce } from 'immer';
import { isEqual } from 'lodash';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { GeneralizedTaskInput } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { buildScopeKey } from './utils';
import { safeLocalStorageGetItem, safeLocalStorageSetItem, safeLocalStorageRemoveItem } from '@/lib/localStorage';

type ParametersHistoryEntry = {
  instructions: string;
  temperature: number;
};

export type InputHistoryEntry = {
  input: GeneralizedTaskInput;
};

interface PlaygroundHistoryStore {
  // Record instead of Map becasue Map is not correctly supported with the zustand persist
  parametersHistoryByScope: Record<string, ParametersHistoryEntry[]>;
  inputHistoryByScope: Record<string, InputHistoryEntry[]>;
  addInputHistoryEntry: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaID: TaskSchemaID,
    entry: InputHistoryEntry
  ) => void;
  addParametersHistoryEntry: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaID: TaskSchemaID,
    entry: ParametersHistoryEntry
  ) => void;
}

export const usePlaygroundHistoryStore = create<PlaygroundHistoryStore>()(
  persist(
    (set) => ({
      parametersHistoryByScope: {},
      inputHistoryByScope: {},
      addParametersHistoryEntry: (tenant, taskId, taskSchemaId, entry) => {
        const scope = buildScopeKey({
          tenant,
          taskId,
          taskSchemaId,
        });

        set(
          produce((state) => {
            const scopeHistory = state.parametersHistoryByScope[scope] || [];
            const filteredScopeHistory = scopeHistory.filter(
              (historyEntry: ParametersHistoryEntry) =>
                historyEntry.instructions !== entry.instructions || historyEntry.temperature !== entry.temperature
            );
            state.parametersHistoryByScope[scope] = [...filteredScopeHistory, entry];
          })
        );
      },
      addInputHistoryEntry: (tenant, taskId, taskSchemaId, entry) => {
        const scope = buildScopeKey({
          tenant,
          taskId,
          taskSchemaId,
        });

        set(
          produce((state) => {
            const scopeHistory = state.inputHistoryByScope[scope] || [];
            const filteredScopeHistory = scopeHistory.filter(
              (historyEntry: InputHistoryEntry) => !isEqual(historyEntry.input, entry.input)
            );
            state.inputHistoryByScope[scope] = [...filteredScopeHistory, entry];
          })
        );
      },
    }),
    {
      name: 'playground-history-storage',
      storage: createJSONStorage(() => ({
        getItem: (name: string) => safeLocalStorageGetItem(name),
        setItem: (name: string, value: string) => safeLocalStorageSetItem(name, value),
        removeItem: (name: string) => safeLocalStorageRemoveItem(name),
      })),
    }
  )
);
