import { enableMapSet, produce } from 'immer';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { TaskID, TaskSchemaID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { ModelResponse, Page_ModelResponse_ } from '@/types/workflowAI';
import { buildScopeKey, taskSchemaSubPath } from './utils';

enableMapSet();

interface AIModelsState {
  modelsByScope: Map<string, ModelResponse[]>;
  isLoadingByScope: Map<string, boolean>;
  isInitializedByScope: Map<string, boolean>;

  models: ModelResponse[] | undefined;
  isLoading: boolean;
  isInitialized: boolean;

  fetchSchemaModels(tenant: TenantID | undefined, taskId: TaskID, taskSchemaId: TaskSchemaID): Promise<void>;
  fetchUniversalModels(): Promise<void>;
}

export const useAIModels = create<AIModelsState>((set, get) => ({
  modelsByScope: new Map(),
  isLoadingByScope: new Map(),
  isInitializedByScope: new Map(),

  models: undefined,
  isLoading: false,
  isInitialized: false,

  fetchSchemaModels: async (tenant: TenantID | undefined, taskId: TaskID, taskSchemaId: TaskSchemaID) => {
    const scope = buildScopeKey({ tenant, taskId, taskSchemaId });

    if (get().isLoadingByScope.get(scope)) return;

    set(
      produce((state) => {
        state.isLoadingByScope.set(scope, true);
      })
    );

    try {
      const response = await client.get<Page_ModelResponse_>(
        taskSchemaSubPath(tenant, taskId, taskSchemaId, '/models', true)
      );

      set(
        produce((state) => {
          state.modelsByScope.set(scope, response.items);
        })
      );
    } catch (error) {
      console.error('Failed to fetch ai models', error);
    }
    set(
      produce((state) => {
        state.isLoadingByScope.set(scope, false);
        state.isInitializedByScope.set(scope, true);
      })
    );
  },

  fetchUniversalModels: async () => {
    if (get().isLoading) return;

    set(
      produce((state) => {
        state.isLoading = true;
      })
    );

    const path = `/api/data/features/models`;

    try {
      const response = await client.get<Page_ModelResponse_>(path);
      set(
        produce((state) => {
          state.models = response.items;
        })
      );
    } catch (error) {
      console.error('Failed to fetch ai models', error);
    } finally {
      set(
        produce((state) => {
          state.isLoading = false;
          state.isInitialized = true;
        })
      );
    }
  },
}));
