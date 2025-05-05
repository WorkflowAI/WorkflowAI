import { produce } from 'immer';
import { isEqual } from 'lodash';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { GeneralizedTaskInput } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { buildScopeKey } from './utils';

export type InputHistoryEntry = {
  input: GeneralizedTaskInput;
};

interface PlaygroundHistoryStore {
  // Record instead of Map becasue Map is not correctly supported with the zustand persist
  inputHistoryByScope: Record<string, InputHistoryEntry[]>;
  addInputHistoryEntry: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaID: TaskSchemaID,
    entry: InputHistoryEntry
  ) => void;
}

export const usePlaygroundHistoryStore = create<PlaygroundHistoryStore>()(
  persist(
    (set) => ({
      inputHistoryByScope: {},
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
      storage: createJSONStorage(() => localStorage),
    }
  )
);
