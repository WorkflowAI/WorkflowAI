import { produce } from 'immer';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { JsonSchema } from '@/types';
import { TenantID } from '@/types/aliases';
import { Provider, ProviderSettings, TenantData } from '../types/workflowAI/models';
import { rootTenantPath } from './utils';

export type ProviderConfig = {
  provider: Provider;
};

interface OrganizationSettingsState {
  settingsForTenant: Record<TenantID, TenantData>;
  isLoading: boolean;
  isInitialized: boolean;
  fetchOrganizationSettings: (tenant: TenantID | undefined) => Promise<void>;
  addProviderConfig: (config: ProviderConfig, tenant: TenantID | undefined) => Promise<void>;
  deleteProviderConfig: (configID: string, tenant: TenantID | undefined) => Promise<void>;
  isLoadingProviderSchemas: boolean;
  providerSchemas: Record<Provider, JsonSchema> | undefined;
  fetchProviderSchemas: () => Promise<void>;
}

export const useOrganizationSettings = create<OrganizationSettingsState>((set) => ({
  settingsForTenant: {},
  isLoading: false,
  isInitialized: false,

  fetchOrganizationSettings: async (tenant: TenantID | undefined) => {
    const tenantToUse = tenant ?? ('_' as TenantID);

    set(
      produce((state: OrganizationSettingsState) => {
        state.isLoading = true;
      })
    );
    try {
      const settings = await client.get<TenantData>(`${rootTenantPath(tenantToUse)}/organization/settings`);

      set(
        produce((state: OrganizationSettingsState) => {
          state.settingsForTenant[tenantToUse] = settings;
        })
      );
    } finally {
      set(
        produce((state: OrganizationSettingsState) => {
          state.isLoading = false;
          state.isInitialized = true;
        })
      );
    }
  },

  addProviderConfig: async (config: ProviderConfig, tenant: TenantID | undefined) => {
    const tenantToUse = tenant ?? ('_' as TenantID);

    const providerSettings = await client.post<ProviderConfig, ProviderSettings>(
      `${rootTenantPath(tenantToUse)}/organization/settings/providers`,
      config
    );
    set(
      produce((state: OrganizationSettingsState) => {
        if (state.settingsForTenant[tenantToUse] === undefined) {
          state.settingsForTenant[tenantToUse] = { providers: [] };
        }
        state.settingsForTenant[tenantToUse].providers?.push(providerSettings);
        return state;
      })
    );
  },

  deleteProviderConfig: async (configID: string, tenant: TenantID | undefined) => {
    const tenantToUse = tenant ?? ('_' as TenantID);

    await client.del(`${rootTenantPath(tenantToUse)}/organization/settings/providers/${configID}`);
    set(
      produce((state: OrganizationSettingsState) => {
        if (state.settingsForTenant[tenantToUse] === undefined) {
          return state;
        }
        state.settingsForTenant[tenantToUse].providers = state.settingsForTenant[tenantToUse].providers?.filter(
          (provider) => provider.id !== configID
        );
        return state;
      })
    );
  },

  providerSchemas: undefined,
  isLoadingProviderSchemas: false,

  fetchProviderSchemas: async () => {
    set({ isLoadingProviderSchemas: true });
    try {
      const providerSchemas = await client.get<Record<Provider, JsonSchema>>(
        `${rootTenantPath()}/organization/settings/providers/schemas`
      );
      set({ providerSchemas });
    } finally {
      set({ isLoadingProviderSchemas: false });
    }
  },
}));
