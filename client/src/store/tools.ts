import { enableMapSet, produce } from 'immer';
import { useCallback, useEffect } from 'react';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { TaskID, TenantID } from '@/types/aliases';
import { Tool } from '@/types/workflowAI';
import { buildScopeKey, taskSubPath } from './utils';

enableMapSet();

interface ToolsState {
  tools: Map<string, Tool[]>;
  isInitializedByScope: Map<string, boolean>;
  isLoadingByScope: Map<string, boolean>;

  fetchTools(tenant: TenantID | undefined, taskId: TaskID): Promise<void>;
  saveTool(tenant: TenantID | undefined, taskId: TaskID, tool: Tool): Promise<void>;
}

export const useTools = create<ToolsState>((set, get) => ({
  tools: new Map<string, Tool[]>(),
  isInitializedByScope: new Map<string, boolean>(),
  isLoadingByScope: new Map<string, boolean>(),

  fetchTools: async (tenant: TenantID | undefined, taskId: TaskID) => {
    const scope = buildScopeKey({
      tenant,
      taskId,
    });
    if (get().isLoadingByScope.get(scope)) {
      return;
    }
    set(
      produce((state: ToolsState) => {
        state.isLoadingByScope.set(scope, true);
      })
    );

    try {
      const url = taskSubPath(tenant, taskId, '/tools');

      const tools = await client.get<Tool[]>(url);
      set(
        produce((state) => {
          state.tools.set(scope, tools);
        })
      );
    } catch (error) {
      console.error('Failed to fetch tools', error);
    }
    set(
      produce((state: ToolsState) => {
        state.isInitializedByScope.set(scope, true);
        state.isLoadingByScope.set(scope, false);
      })
    );
  },

  saveTool: async (tenant: TenantID | undefined, taskId: TaskID, tool: Tool) => {
    const scope = buildScopeKey({
      tenant,
      taskId,
    });

    try {
      const url = taskSubPath(tenant, taskId, '/tools');

      const body = {
        name: tool.name,
        description: tool.description,
        input_schema: tool.parameters,
      };

      const newTool = await client.post<Tool>(url, body);
      set(
        produce((state) => {
          const tools = state.tools.get(scope) ?? [];
          tools.push(newTool);
          state.tools.set(scope, tools);
        })
      );
    } catch (error) {
      console.error('Failed to save tool', error);
    }
  },
}));

export const useOrFetchTools = (tenant: TenantID | undefined, taskId: TaskID) => {
  const scope = buildScopeKey({
    tenant,
    taskId,
  });

  const tools = useTools((state) => state.tools.get(scope));
  const isInitialized = useTools((state) => state.isInitializedByScope.get(scope));
  const isLoading = useTools((state) => state.isLoadingByScope.get(scope));

  const fetchTools = useTools((state) => state.fetchTools);
  const saveToolExternal = useTools((state) => state.saveTool);

  const saveTool = useCallback(
    async (tool: Tool) => {
      await saveToolExternal(tenant, taskId, tool);
    },
    [tenant, taskId, saveToolExternal]
  );

  useEffect(() => {
    fetchTools(tenant, taskId);
  }, [fetchTools, tenant, taskId]);

  return {
    tools,
    isInitialized,
    isLoading,
    saveTool,
  };
};
