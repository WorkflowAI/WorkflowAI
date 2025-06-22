import { enableMapSet, produce } from 'immer';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { TaskID, TenantID } from '@/types/aliases';
import { LLMCompletionTypedMessages, LLMCompletionsResponse } from '@/types/workflowAI';
import { taskSubPath } from './utils';

enableMapSet();

interface RunCompletionsState {
  runCompletionsById: Map<string, Array<LLMCompletionTypedMessages>>;
  isInitializedById: Map<string, boolean>;
  isLoadingById: Map<string, boolean>;

  fetchRunCompletion(tenant: TenantID | undefined, taskId: TaskID, runId: string): Promise<void>;
}

export const useRunCompletions = create<RunCompletionsState>((set, get) => ({
  runCompletionsById: new Map<string, LLMCompletionTypedMessages[]>(),
  isInitializedById: new Map<string, boolean>(),
  isLoadingById: new Map<string, boolean>(),

  fetchRunCompletion: async (tenant: TenantID | undefined, taskId: TaskID, runId: string) => {
    if (get().isLoadingById.get(runId)) {
      return;
    }

    set(
      produce((state: RunCompletionsState) => {
        state.isLoadingById.set(runId, true);
      })
    );

    const completions = await client.get<LLMCompletionTypedMessages[]>(
      taskSubPath(tenant, taskId, `/runs/${runId}/completions`, true)
    );

    set(
      produce((state: RunCompletionsState) => {
        state.runCompletionsById.set(runId, completions);
      })
    );

    set(
      produce((state: RunCompletionsState) => {
        state.isLoadingById.set(runId, false);
        state.isInitializedById.set(runId, true);
      })
    );
  },
}));
