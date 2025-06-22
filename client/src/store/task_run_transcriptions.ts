import { enableMapSet, produce } from 'immer';
import { isEqual } from 'lodash';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { TaskID, TenantID } from '@/types/aliases';
import { RunTranscriptionResponse } from '@/types/task_run';
import { taskSubPath } from './utils';

enableMapSet();

interface TaskRunTranscriptionsState {
  transcriptionsById: Map<string, Record<string, string>>;
  isInitializedById: Map<string, boolean>;
  isLoadingById: Map<string, boolean>;

  fetchTaskRunTranscriptions(tenant: TenantID | undefined, taskId: TaskID, runId: string): Promise<void>;
}

export const useTaskRunTranscriptions = create<TaskRunTranscriptionsState>((set, get) => ({
  transcriptionsById: new Map<string, Record<string, string>>(),
  isInitializedById: new Map<string, boolean>(),
  isLoadingById: new Map<string, boolean>(),

  fetchTaskRunTranscriptions: async (tenant: TenantID | undefined, taskId: TaskID, runId: string) => {
    if (get().isLoadingById.get(runId)) {
      return;
    }
    set(
      produce((state: TaskRunTranscriptionsState) => {
        state.isLoadingById.set(runId, true);
      })
    );
    try {
      const response = await client.get<RunTranscriptionResponse>(
        taskSubPath(tenant, taskId, `/runs/${runId}/transcriptions`)
      );

      const transcriptions = response.transcriptions_by_keypath;

      // When we poll the task run, we need to check if the task run has changed
      // Otherwise, it can trigger some useEffects that are not necessary
      if (!isEqual(get().transcriptionsById.get(runId), transcriptions)) {
        set(
          produce((state: TaskRunTranscriptionsState) => {
            state.transcriptionsById.set(runId, transcriptions);
          })
        );
      }
    } catch (error) {
      console.error('Failed to fetch AI agent run transcriptions', error);
    }
    set(
      produce((state: TaskRunTranscriptionsState) => {
        state.isLoadingById.set(runId, false);
        state.isInitializedById.set(runId, true);
      })
    );
  },
}));
