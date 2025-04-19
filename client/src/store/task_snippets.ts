import { enableMapSet, produce } from 'immer';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { CodeLanguage } from '@/types/snippets';
import { GenerateCodeBlockRequest, GenerateCodeBlockResponse } from '@/types/workflowAI';
import { taskSchemaSubPath } from './utils';

enableMapSet();

export function buildSnippetScopeKey(
  taskId: TaskID,
  taskSchemaId: TaskSchemaID,
  language: CodeLanguage,
  iteration?: number,
  environment?: string,
  taskInput?: Record<string, unknown>
) {
  return `${taskId}-${taskSchemaId}-${language}-${iteration ?? 0}-${environment ?? ''}-${JSON.stringify(taskInput)}`;
}

interface TaskSnippetsState {
  taskSnippetsByScope: Map<string, GenerateCodeBlockResponse>;
  isLoadingByScope: Map<string, boolean>;
  isInitializedByScope: Map<string, boolean>;
  fetchSnippet: (
    tenant: TenantID,
    taskId: TaskID,
    taskSchemaId: TaskSchemaID,
    language: CodeLanguage,
    exampleTaskRunInput: Record<string, unknown> | undefined,
    iteration?: number,
    environment?: string,
    url?: string,
    secondaryInput?: Record<string, unknown>
  ) => Promise<void>;
}

export const useTaskSnippets = create<TaskSnippetsState>((set, get) => ({
  taskSnippetsByScope: new Map(),
  isLoadingByScope: new Map(),
  isInitializedByScope: new Map(),
  fetchSnippet: async (
    tenant,
    taskId,
    taskSchemaId,
    language,
    exampleTaskRunInput,
    iteration,
    environment,
    url,
    secondaryInput
  ) => {
    const scopeKey = buildSnippetScopeKey(taskId, taskSchemaId, language, iteration, environment, exampleTaskRunInput);
    if (get().isLoadingByScope.get(scopeKey)) return;
    set(
      produce((state) => {
        state.isLoadingByScope.set(scopeKey, true);
      })
    );

    try {
      const requestBody: GenerateCodeBlockRequest = {
        group_iteration: iteration || 0,
        group_environment: environment ?? '',
        example_task_run_input: exampleTaskRunInput ?? {},
        url,
        secondary_input: secondaryInput ?? undefined,
        separate_run_and_stream: true,
      };

      // Map the CodeLanguage to the appropriate API endpoint
      let endpointPath = '/python'; // Default to Python
      if (language === CodeLanguage.GO) {
        endpointPath = '/go';
      }

      const snippet = await client.post<GenerateCodeBlockRequest, GenerateCodeBlockResponse>(
        taskSchemaSubPath(tenant, taskId, taskSchemaId, endpointPath),
        requestBody
      );
      set(
        produce((state) => {
          state.taskSnippetsByScope.set(scopeKey, snippet);
        })
      );
    } catch (error) {
      console.error('Failed to fetch AI agent snippet by AI agent schema id', error);
    }
    set(
      produce((state) => {
        state.isLoadingByScope.set(scopeKey, false);
        state.isInitializedByScope.set(scopeKey, true);
      })
    );
  },
}));
