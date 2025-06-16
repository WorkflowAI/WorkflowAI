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

  featureModels: ModelResponse[] | undefined;
  isLoadingFeatureModels: boolean;
  isInitializedFeatureModels: boolean;

  models: ModelResponse[] | undefined;
  isLoadingModels: boolean;
  isInitializedModels: boolean;

  fetchSchemaModels(tenant: TenantID | undefined, taskId: TaskID, taskSchemaId: TaskSchemaID): Promise<void>;
  fetchFeaturesModels(): Promise<void>;
  fetchModels(): Promise<void>;
}

export const useAIModels = create<AIModelsState>((set, get) => ({
  modelsByScope: new Map(),
  isLoadingByScope: new Map(),
  isInitializedByScope: new Map(),

  featureModels: undefined,
  isLoadingFeatureModels: false,
  isInitializedFeatureModels: false,

  models: undefined,
  isLoadingModels: false,
  isInitializedModels: false,

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

  fetchFeaturesModels: async () => {
    if (get().isLoadingFeatureModels) return;

    set(
      produce((state) => {
        state.isLoadingFeatureModels = true;
      })
    );

    const path = `/api/data/features/models`;

    try {
      const response = await client.get<Page_ModelResponse_>(path);
      set(
        produce((state) => {
          state.featureModels = response.items;
        })
      );
    } catch (error) {
      console.error('Failed to fetch ai models', error);
    } finally {
      set(
        produce((state) => {
          state.isLoadingFeatureModels = false;
          state.isInitializedFeatureModels = true;
        })
      );
    }
  },

  fetchModels: async () => {
    if (get().isLoadingModels) return;

    set(
      produce((state) => {
        state.isLoadingModels = true;
      })
    );

    const path = `/api/data/v1/models`;

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
          state.isLoadingModels = false;
          state.isInitializedModels = true;
        })
      );
    }
  },
}));
