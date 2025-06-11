import { produce } from 'immer';
import { useEffect } from 'react';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { Page } from '@/types';
import { TenantID } from '@/types/aliases';
import { AgentStat } from '@/types/workflowAI';
import { rootTenantPath } from './utils';

interface AgentsStatsState {
  agentsStatsByTenant: Map<TenantID, Map<number, AgentStat>>;
  isInitializedByTenant: Map<TenantID, boolean>;
  isLoadingByTenant: Map<TenantID, boolean>;
  fetchAgentsStats(tenant: TenantID): Promise<void>;
}

const useAgentsStats = create<AgentsStatsState>((set, get) => ({
  agentsStatsByTenant: new Map(),
  isInitializedByTenant: new Map(),
  isLoadingByTenant: new Map(),
  fetchAgentsStats: async (tenant: TenantID) => {
    if (get().isLoadingByTenant.get(tenant)) return;
    set(
      produce((state: AgentsStatsState) => {
        state.isLoadingByTenant.set(tenant, true);
      })
    );
    try {
      const agentsStats = await client.get<Page<AgentStat>>(`${rootTenantPath(tenant, true)}/agents/stats`);
      const byUid = new Map<number, AgentStat>();
      agentsStats.items.forEach((agentStat) => {
        const id = agentStat.agent_id ?? agentStat.agent_uid;
        byUid.set(id, agentStat);
      });
      set(
        produce((state: AgentsStatsState) => {
          state.agentsStatsByTenant.set(tenant, byUid);
          state.isInitializedByTenant.set(tenant, true);
          state.isLoadingByTenant.set(tenant, false);
        })
      );
    } catch (e: unknown) {
      console.error(e);
      set(
        produce((state: AgentsStatsState) => {
          state.isInitializedByTenant.set(tenant, true);
          state.isLoadingByTenant.set(tenant, false);
        })
      );
    }
  },
}));

export function useOrFetchAgentsStats(tenant: TenantID) {
  const { agentsStatsByTenant, isInitializedByTenant, isLoadingByTenant, fetchAgentsStats } = useAgentsStats();
  const isInitialized = isInitializedByTenant.get(tenant);
  const isLoading = isLoadingByTenant.get(tenant) ?? false;

  useEffect(() => {
    fetchAgentsStats(tenant);
  }, [tenant, fetchAgentsStats]);

  return {
    agentsStats: agentsStatsByTenant.get(tenant),
    isInitialized,
    isLoading,
  };
}
