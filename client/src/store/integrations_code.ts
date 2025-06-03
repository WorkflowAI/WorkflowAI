import { produce } from 'immer';
import { useEffect } from 'react';
import { create } from 'zustand';
import { Method, SSEClient } from '@/lib/api/client';
import { API_URL } from '@/lib/constants';
import { TaskSchemaID, TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';

interface IntegrationsCodeState {
  isLoadingByScope: Record<string, boolean>;
  isInitializedByScope: Record<string, boolean>;
  codeByScope: Record<string, string | undefined>;

  getIntegrationsCode: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    versionId: string,
    integrationId: string,
    key: string | undefined
  ) => Promise<void>;
}

export const useIntegrations = create<IntegrationsCodeState>((set, get) => ({
  isLoadingByScope: {},
  isInitializedByScope: {},
  codeByScope: {},

  getIntegrationsCode: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    versionId: string,
    integrationId: string,
    key: string | undefined
  ) => {
    const scope = `${tenant}-${taskId}-${taskSchemaId}-${versionId}-${integrationId}-${key}`;

    if (get().isLoadingByScope[scope]) {
      return;
    }

    set(
      produce((state: IntegrationsCodeState) => {
        state.codeByScope[scope] = undefined;
        state.isLoadingByScope[scope] = true;
      })
    );
    const path = `${API_URL}/v1/agents/${taskId}/schemas/${taskSchemaId}/integrations/code`;

    try {
      const { code } = await SSEClient<{ version_id: string; integration_kind: string }, { code: string }>(
        path,
        Method.POST,
        {
          version_id: versionId,
          integration_kind: integrationId,
        },
        (response) => {
          set(
            produce((state: IntegrationsCodeState) => {
              state.codeByScope[scope] = response.code;
            })
          );
        }
      );

      set(
        produce((state: IntegrationsCodeState) => {
          state.codeByScope[scope] = code;
          state.isInitializedByScope[scope] = true;
          state.isLoadingByScope[scope] = false;
        })
      );
    } catch (error) {
      console.error('Failed to fetch integrations code', error);
      set(
        produce((state: IntegrationsCodeState) => {
          state.isLoadingByScope[scope] = false;
        })
      );
    }
  },
}));

export const useOrFetchIntegrationsCode = (
  tenant: TenantID | undefined,
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  versionId: string | undefined,
  integrationId: string | undefined,
  key: string | undefined
) => {
  const scope = `${tenant}-${taskId}-${taskSchemaId}-${versionId}-${integrationId}-${key}`;

  const code = useIntegrations((state) => (versionId ? state.codeByScope[scope] : undefined));
  const isLoading = useIntegrations((state) => (versionId ? state.isLoadingByScope[scope] : false));
  const isInitialized = useIntegrations((state) => (versionId ? state.isInitializedByScope[scope] : false));
  const getIntegrationsCode = useIntegrations((state) => state.getIntegrationsCode);

  useEffect(() => {
    if (versionId && integrationId) {
      getIntegrationsCode(tenant, taskId, taskSchemaId, versionId, integrationId, key);
    }
  }, [getIntegrationsCode, tenant, taskId, taskSchemaId, versionId, integrationId, key]);

  return {
    code,
    isLoading,
    isInitialized,
  };
};
