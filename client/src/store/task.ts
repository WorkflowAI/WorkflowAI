import { enableMapSet, produce } from 'immer';
import { orderBy, sortBy } from 'lodash';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { Method, SSEClient } from '@/lib/api/client';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import {
  BuildAgentIteration,
  BuildAgentRequest,
  CreateAgentRequest,
  CreateAgentResponse,
  GenerateInputRequest,
  ImportInputsRequest,
  ImproveVersionRequest,
  Page_SerializableTask_,
  RunRequest,
  RunResponseStreamChunk,
  SerializableTask,
  TaskGroupProperties,
  ToolKind,
  UpdateTaskInstructionsRequest,
  UpdateTaskRequest,
} from '@/types/workflowAI';
import { useMetaAgentChat } from './meta_agent_messages';
import { buildScopeKey, rootTaskPath, rootTaskPathNoProxy, rootTaskPathNoProxyV1, runTaskPathNoProxy } from './utils';

enableMapSet();

export type ImproveVersionResponse = {
  improved_properties: TaskGroupProperties;
  changelog: string[];
};
type SuggestedInstructionsResponse = {
  suggested_instructions: string;
};

type GenerateInputMessage = Record<string, unknown>;
type ImportedInputMessage = {
  imported_input: GenerateInputMessage;
};

interface TasksState {
  tasksByTenant: Map<TenantID, SerializableTask[]>;
  tasksByScope: Map<string, SerializableTask>;
  isLoadingTasksByTenant: Map<TenantID, boolean>;
  isInitialiazedTasksByTenant: Map<string, boolean>;
  fetchTasks(tenant: TenantID): Promise<void>;
  isLoadingTaskByScope: Map<string, boolean>;
  isInitialiazedTaskByScope: Map<string, boolean>;

  fetchTask(tenant: TenantID | undefined, taskId: TaskID): Promise<void>;
  improveVersion(
    tenant: TenantID | undefined,
    taskId: TaskID,
    payload: ImproveVersionRequest,
    onMessage: (message: ImproveVersionResponse) => void,
    signal?: AbortSignal
  ): Promise<ImproveVersionResponse>;
  generatePlaygroundInput(
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    request: GenerateInputRequest,
    onMessage?: (message: GenerateInputMessage) => void,
    signal?: AbortSignal
  ): Promise<GenerateInputMessage>;
  generatePlaygroundInputWithText(
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    request: ImportInputsRequest,
    onMessage: (message: GenerateInputMessage) => void,
    signal?: AbortSignal
  ): Promise<GenerateInputMessage>;
  iterateTaskInputOutput(
    tenant: TenantID | undefined,
    request: BuildAgentRequest,
    onMessage: (message: BuildAgentIteration) => void,
    signal?: AbortSignal
  ): Promise<BuildAgentIteration>;
  generateSuggestedInstructions(
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    onMessage: (message: string) => void,
    signal?: AbortSignal
  ): Promise<string>;
  updateTaskInstructions(
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    instructions: string,
    tools: ToolKind[],
    onMessage: (message: string) => void,
    signal?: AbortSignal
  ): Promise<string>;
  createTask(tenant: TenantID | undefined, payload: Omit<CreateAgentRequest, 'id'>): Promise<CreateAgentResponse>;
  updateTask(tenant: TenantID | undefined, taskId: TaskID, payload: UpdateTaskRequest): Promise<SerializableTask>;
  deleteTask(tenant: TenantID, taskId: TaskID): Promise<void>;
  updateTaskSchema(
    tenant: TenantID | undefined,
    taskId: TaskID,
    payload: Omit<CreateAgentRequest, 'id'>
  ): Promise<CreateAgentResponse>;
  runTask(options: {
    tenant: TenantID | undefined;
    taskId: TaskID;
    taskSchemaId: TaskSchemaID;
    body: RunRequest;
    onMessage: (message: RunResponseStreamChunk) => void;
    signal?: AbortSignal;
  }): Promise<RunResponseStreamChunk>;
}

export const useTasks = create<TasksState>((set, get) => ({
  tasksByTenant: new Map(),
  tasksByScope: new Map(),
  isLoadingTaskByScope: new Map(),
  isInitialiazedTaskByScope: new Map(),
  isLoadingTasksByTenant: new Map(),
  isInitialiazedTasksByTenant: new Map(),

  fetchTasks: async (tenant) => {
    if (get().isLoadingTasksByTenant.get(tenant) ?? false) return;
    set(
      produce((state: TasksState) => {
        state.isLoadingTasksByTenant.set(tenant, true);
      })
    );
    try {
      // We always fetch task with a _ tenant which is equivalent to using the tenant provided
      // in the JWT
      const { items } = await client.get<Page_SerializableTask_>(rootTaskPath(tenant));

      const sortedTasksByName = sortBy(items, 'name');
      const sortedTasksWithSortedVersions = sortedTasksByName.map((task) => ({
        ...task,
        versions: orderBy(task.versions, 'schema_id', 'desc'),
      }));
      set(
        produce((state: TasksState) => {
          state.tasksByTenant.set(tenant, sortedTasksWithSortedVersions);
          // We set the tasks by ID since the payload is exactly the same
          // We set the task by scope to provide temp data but avoid setting the initialized state
          // To make sure the data is properly loaded by fetchTask.
          for (const task of sortedTasksWithSortedVersions) {
            const scopeKey = buildScopeKey({
              tenant,
              taskId: task.id as TaskID,
            });
            // Skipping to avoid overriding the task by scope
            if (state.tasksByScope.has(scopeKey)) continue;

            state.tasksByScope.set(scopeKey, task);
          }
        })
      );
    } catch (error) {
      console.error('Failed to fetch AI agents', error);
    }
    set(
      produce((state: TasksState) => {
        state.isLoadingTasksByTenant.delete(tenant);
        state.isInitialiazedTasksByTenant.set(tenant, true);
      })
    );
  },
  fetchTask: async (tenant, taskId) => {
    const scopeKey = buildScopeKey({ tenant, taskId });
    if (get().isLoadingTaskByScope.get(scopeKey)) return;

    set(
      produce((state: TasksState) => {
        state.isLoadingTaskByScope.set(scopeKey, true);
      })
    );
    try {
      const task = await client.get<SerializableTask>(`${rootTaskPath(tenant)}/${taskId}`);
      set(
        produce((state: TasksState) => {
          state.tasksByScope.set(scopeKey, task);
        })
      );
    } catch (error) {
      console.error('Failed to fetch AI agent', error);
    }
    set(
      produce((state: TasksState) => {
        state.isLoadingTaskByScope.set(scopeKey, false);
        state.isInitialiazedTaskByScope.set(scopeKey, true);
      })
    );
  },
  improveVersion: async (tenant, taskId, payload, onMessage, signal) => {
    const lastMessage = await SSEClient<ImproveVersionRequest, ImproveVersionResponse>(
      `${rootTaskPathNoProxyV1(tenant)}/${taskId}/versions/improve`,
      Method.POST,
      payload,
      onMessage,
      signal
    );
    return lastMessage;
  },
  generatePlaygroundInput: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    request: GenerateInputRequest,
    onMessage?: (message: GenerateInputMessage) => void,
    signal?: AbortSignal
  ) => {
    const lastMessage = await SSEClient<GenerateInputRequest, GenerateInputMessage>(
      `${rootTaskPathNoProxy(tenant)}/${taskId}/schemas/${taskSchemaId}/input`,
      Method.POST,
      request,
      onMessage,
      signal
    );
    return lastMessage;
  },
  generatePlaygroundInputWithText: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    request: ImportInputsRequest,
    onMessage: (message: GenerateInputMessage) => void,
    signal?: AbortSignal
  ) => {
    const handleOnMessage = (message: ImportedInputMessage) => {
      onMessage(message.imported_input);
    };
    const lastMessage = await SSEClient<ImportInputsRequest, ImportedInputMessage>(
      `${rootTaskPathNoProxy(tenant)}/${taskId}/schemas/${taskSchemaId}/inputs/import`,
      Method.POST,
      request,
      handleOnMessage,
      signal
    );
    return lastMessage.imported_input;
  },
  iterateTaskInputOutput: async (tenant: TenantID | undefined, request: BuildAgentRequest, onMessage, signal) => {
    const path = `${rootTaskPathNoProxy(tenant)}/schemas/iterate`;
    request.stream = true;
    const lastMessage = await SSEClient<BuildAgentRequest, BuildAgentIteration>(
      path,
      Method.POST,
      request,
      onMessage,
      signal
    );
    return lastMessage;
  },
  generateSuggestedInstructions: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    onMessage: (message: string) => void,
    signal?: AbortSignal
  ): Promise<string> => {
    const handleOnMessage = (message: SuggestedInstructionsResponse) => {
      onMessage(message.suggested_instructions);
    };
    const lastMessage = await SSEClient<string, SuggestedInstructionsResponse>(
      `${rootTaskPathNoProxy(tenant)}/${taskId}/schemas/${taskSchemaId}/suggested-instructions`,
      Method.GET,
      '',
      handleOnMessage,
      signal
    );
    return lastMessage.suggested_instructions;
  },

  updateTaskInstructions: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    instructions: string,
    tools: ToolKind[],
    onMessage: (message: string) => void,
    signal?: AbortSignal
  ): Promise<string> => {
    const lastInstructions = await SSEClient<
      UpdateTaskInstructionsRequest,
      { updated_task_instructions: string | undefined }
    >(
      `${rootTaskPathNoProxy(tenant)}/${taskId}/schemas/${taskSchemaId}/instructions`,
      Method.PUT,
      { instructions, selected_tools: tools },
      (message) => {
        if (message.updated_task_instructions) {
          onMessage(message.updated_task_instructions);
        }
      },
      signal
    );
    return lastInstructions.updated_task_instructions ?? '';
  },

  createTask: async (tenant: TenantID | undefined, payload: CreateAgentRequest): Promise<CreateAgentResponse> => {
    const task = await client.post<CreateAgentRequest, CreateAgentResponse>(rootTaskPath(tenant, true), payload);
    // Refetch tasks to get the updated list of schemas in the task switcher
    if (!!tenant) {
      await get().fetchTasks(tenant);
    }
    return task;
  },

  updateTask: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    payload: UpdateTaskRequest
  ): Promise<SerializableTask> => {
    const task = await client.patch<UpdateTaskRequest, SerializableTask>(`${rootTaskPath(tenant)}/${taskId}`, payload);
    // Refetch tasks to get the updated list of schemas in the task switcher
    if (!!tenant) {
      await get().fetchTasks(tenant);
    }
    return task;
  },

  deleteTask: async (tenant: TenantID | undefined, taskId: TaskID) => {
    await client.del(`${rootTaskPath(tenant)}/${taskId}`);
    // Refetch tasks to get the updated list of schemas in the task switcher
    if (!!tenant) {
      await get().fetchTasks(tenant);
    }
    useMetaAgentChat.getState().remove(taskId);
  },

  updateTaskSchema: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    payload: Omit<CreateAgentRequest, 'id'>
  ): Promise<CreateAgentResponse> => {
    return await client.post<CreateAgentRequest, CreateAgentResponse>(rootTaskPath(tenant, true), {
      ...payload,
      id: taskId,
    });
  },

  runTask: async ({ tenant, taskId, taskSchemaId, body, onMessage, signal }) => {
    const lastMessage = await SSEClient<RunRequest, RunResponseStreamChunk>(
      `${runTaskPathNoProxy(tenant)}/${taskId}/schemas/${taskSchemaId}/run`,
      Method.POST,
      body,
      onMessage,
      signal
    );
    return lastMessage;
  },
}));
