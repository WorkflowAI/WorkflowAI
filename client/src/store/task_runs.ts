import { enableMapSet, produce } from 'immer';
import { isEqual, orderBy } from 'lodash';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { TaskRun } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { Page } from '@/types/page';
import { FieldQuery, Page_RunItemV1_, RunItemV1, RunV1, SearchTaskRunsRequest } from '@/types/workflowAI';
import { buildScopeKey, buildSearchTaskRunsScopeKey, taskSchemaSubPath, taskSubPath } from './utils';

enableMapSet();

export interface TaskRunsState {
  taskRunItemsV1ByScope: Map<string, RunItemV1[]>;
  taskRunsByScope: Map<string, TaskRun[]>;
  taskRunsById: Map<string, TaskRun>;
  isInitializedByScope: Map<string, boolean>;
  isInitializedById: Map<string, boolean>;
  isLoadingById: Map<string, boolean>;
  isLoadingByScope: Map<string, boolean>;
  countByScope: Map<string, number>;

  runV1ById: Map<string, RunV1>;
  isRunV1LoadingById: Map<string, boolean>;
  isRunV1InitializedById: Map<string, boolean>;

  isLatestRunLoadingByScope: Map<string, boolean>;
  isLatestRunInitializedByScope: Map<string, boolean>;
  latestRunByScope: Map<string, RunV1>;

  fetchTaskRuns(params: {
    tenant: TenantID | undefined;
    taskId: TaskID;
    taskSchemaId: TaskSchemaID;
    searchParams?: string;
  }): Promise<TaskRun[] | undefined>;
  searchTaskRuns(params: {
    tenant: TenantID | undefined;
    taskId: TaskID;
    limit: number;
    offset: number;
    fieldQueries: Array<FieldQuery> | undefined;
  }): Promise<void>;
  fetchTaskRun(tenant: TenantID | undefined, taskId: TaskID, runId: string): Promise<TaskRun | undefined>;
  fetchRunV1(tenant: TenantID | undefined, taskId: TaskID, runId: string): Promise<RunV1 | undefined>;
  fetchLatestRun(tenant: TenantID | undefined, taskId: TaskID, taskSchemaId?: TaskSchemaID): Promise<void>;
}

export const useTaskRuns = create<TaskRunsState>((set, get) => ({
  taskRunItemsV1ByScope: new Map<string, RunItemV1[]>(),
  taskRunsByScope: new Map<string, TaskRun[]>(),
  taskRunsById: new Map<string, TaskRun>(),
  isInitializedByScope: new Map<string, boolean>(),
  isInitializedById: new Map<string, boolean>(),
  isLoadingById: new Map<string, boolean>(),
  isLoadingByScope: new Map<string, boolean>(),
  countByScope: new Map<string, number>(),

  isLatestRunLoadingByScope: new Map<string, boolean>(),
  isLatestRunInitializedByScope: new Map<string, boolean>(),
  latestRunByScope: new Map<string, RunV1>(),

  runV1ById: new Map<string, RunV1>(),
  isRunV1LoadingById: new Map<string, boolean>(),
  isRunV1InitializedById: new Map<string, boolean>(),

  fetchTaskRuns: async ({ tenant, taskId, taskSchemaId, searchParams }) => {
    if (!tenant) {
      return;
    }
    const scope = buildScopeKey({ tenant, taskId, taskSchemaId, searchParams });
    if (get().isLoadingByScope.get(scope)) {
      return;
    }
    set(
      produce((state: TaskRunsState) => {
        state.isLoadingByScope.set(scope, true);
      })
    );

    let result: TaskRun[] | undefined = undefined;

    try {
      const { items: taskRuns, count } = await client.get<Page<TaskRun>>(
        taskSchemaSubPath(tenant, taskId, taskSchemaId, `/runs${searchParams ? `?${searchParams}` : ''}`)
      );
      set(
        produce((state) => {
          state.taskRunsByScope.set(scope, orderBy(taskRuns, 'start_time', 'desc'));
          state.countByScope.set(scope, count);
        })
      );
      result = taskRuns;
    } catch (error) {
      console.error('Failed to fetch AI agents runs', error);
    }
    set(
      produce((state: TaskRunsState) => {
        state.isInitializedByScope.set(scope, true);
        state.isLoadingByScope.set(scope, false);
      })
    );

    return result;
  },

  searchTaskRuns: async ({ tenant, taskId, limit, offset, fieldQueries }) => {
    if (!tenant) {
      return;
    }
    const scope = buildSearchTaskRunsScopeKey({
      tenant,
      taskId,
      limit,
      offset,
      fieldQueries,
    });
    if (get().isLoadingByScope.get(scope)) {
      return;
    }
    set(
      produce((state: TaskRunsState) => {
        state.isLoadingByScope.set(scope, true);
      })
    );

    try {
      const { items: runItems, count } = await client.post<SearchTaskRunsRequest, Page_RunItemV1_>(
        taskSubPath(tenant, taskId, `/runs/search`, true),
        {
          field_queries: fieldQueries ?? [],
          limit,
          offset,
        }
      );

      set(
        produce((state) => {
          state.taskRunItemsV1ByScope.set(scope, orderBy(runItems, 'start_time', 'desc'));
          state.countByScope.set(scope, count);
        })
      );
    } catch (error) {
      console.error('Failed to fetch AI agents runs', error);
    }
    set(
      produce((state: TaskRunsState) => {
        state.isInitializedByScope.set(scope, true);
        state.isLoadingByScope.set(scope, false);
      })
    );
  },

  fetchTaskRun: async (tenant: TenantID, taskId: TaskID, runId: string) => {
    if (get().isLoadingById.get(runId)) {
      return;
    }

    set(
      produce((state: TaskRunsState) => {
        state.isLoadingById.set(runId, true);
      })
    );

    const taskRun = await client.get<TaskRun>(taskSubPath(tenant, taskId, `/runs/${runId}`)).catch(() => undefined);

    if (taskRun !== undefined && !isEqual(get().taskRunsById.get(runId), taskRun)) {
      set(
        produce((state: TaskRunsState) => {
          state.taskRunsById.set(runId, taskRun);
        })
      );
    }

    set(
      produce((state: TaskRunsState) => {
        state.isLoadingById.set(runId, false);
        state.isInitializedById.set(runId, true);
      })
    );
    return taskRun;
  },

  fetchRunV1: async (tenant: TenantID, taskId: TaskID, runId: string) => {
    if (get().isRunV1LoadingById.get(runId)) {
      return;
    }
    set(
      produce((state: TaskRunsState) => {
        state.isRunV1LoadingById.set(runId, true);
      })
    );
    const runV1 = await client.get<RunV1>(taskSubPath(tenant, taskId, `/runs/${runId}`, true)).catch(() => undefined);

    // When we poll the task run, we need to check if the task run has changed
    // Otherwise, it can trigger some useEffects that are not necessary
    if (runV1 !== undefined && !isEqual(get().runV1ById.get(runId), runV1)) {
      set(
        produce((state: TaskRunsState) => {
          state.runV1ById.set(runId, runV1);
        })
      );
    }
    set(
      produce((state: TaskRunsState) => {
        state.isRunV1LoadingById.set(runId, false);
        state.isRunV1InitializedById.set(runId, true);
      })
    );
    return runV1;
  },

  fetchLatestRun: async (tenant: TenantID | undefined, taskId: TaskID, taskSchemaId?: TaskSchemaID) => {
    const scope = buildScopeKey({ tenant, taskId, taskSchemaId });

    if (get().isLatestRunLoadingByScope.get(scope)) {
      return;
    }

    set(
      produce((state: TaskRunsState) => {
        state.isLatestRunLoadingByScope.set(scope, true);
      })
    );

    const params = new URLSearchParams();
    if (taskSchemaId) params.set('schema_id', taskSchemaId);

    try {
      const runV1 = await client.get<RunV1>(taskSubPath(tenant, taskId, `/runs/latest`, true), params);

      set(
        produce((state) => {
          state.latestRunByScope.set(scope, runV1);
        })
      );
    } catch (error) {
      console.error('Failed to fetch latest AI agents run', error);
    }

    set(
      produce((state: TaskRunsState) => {
        state.isLatestRunLoadingByScope.set(scope, false);
        state.isLatestRunInitializedByScope.set(scope, true);
      })
    );
  },
}));
