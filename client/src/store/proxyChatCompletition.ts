import { create } from 'zustand';
import {
  AdvancedSettings,
  getCacheValue,
} from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/hooks/useProxyPlaygroundSearchParams';
import { Method, SSEClient } from '@/lib/api/client';
import { API_URL } from '@/lib/constants';
import { TaskID, TaskSchemaID } from '@/types/aliases';
import {
  OpenAIProxyChatCompletionRequest,
  OpenAIProxyTool,
  ProxyMessage,
  ToolKind,
  Tool_Output,
} from '@/types/workflowAI';

function getWorkflowAITools(toolCalls?: (ToolKind | Tool_Output)[]): string[] | undefined {
  if (!toolCalls) {
    return undefined;
  }

  const workflowaiTools: string[] = [];

  for (const tool of toolCalls) {
    if (typeof tool === 'string') {
      workflowaiTools.push(tool);
    }
  }

  if (workflowaiTools.length === 0) {
    return undefined;
  }

  return workflowaiTools;
}

function getOpenAITools(tools?: (ToolKind | Tool_Output)[]): OpenAIProxyTool[] | undefined {
  if (!tools) {
    return undefined;
  }

  const result: OpenAIProxyTool[] = [];

  for (const tool of tools) {
    if (typeof tool === 'object' && 'name' in tool && 'input_schema' in tool) {
      const openAITool: OpenAIProxyTool = {
        type: 'function',
        function: {
          name: tool.name,
          description: tool.description,
          parameters: tool.input_schema,
          strict:
            'strict' in tool && tool.strict !== undefined && typeof tool.strict === 'boolean' ? tool.strict : undefined,
        },
      };
      result.push(openAITool);
    }
  }
  return result.length > 0 ? result : undefined;
}

interface ProxyChatCompletitionState {
  performRun(
    taskId: TaskID,
    schemaId: TaskSchemaID,
    model: string,
    input: Record<string, unknown> | undefined,
    messages: ProxyMessage[],
    advancedSettings: AdvancedSettings | undefined,
    tools?: (ToolKind | Tool_Output)[],
    signal?: AbortSignal
  ): Promise<string>;
}

export const useProxyChatCompletition = create<ProxyChatCompletitionState>(() => ({
  performRun: async (taskId, schemaId, model, input, messages, advancedSettings, tools, signal) => {
    const fullInput = {
      ...input,
      'workflowai.messages': messages,
    };

    const body: OpenAIProxyChatCompletionRequest = {
      agent_id: taskId,
      input: fullInput,
      messages: [],
      model: model,
      temperature: advancedSettings?.temperature !== undefined ? Number(advancedSettings.temperature) : undefined,
      max_tokens: advancedSettings?.max_tokens !== undefined ? Number(advancedSettings.max_tokens) : undefined,
      top_p: advancedSettings?.top_p !== undefined ? Number(advancedSettings.top_p) : undefined,
      frequency_penalty:
        advancedSettings?.frequency_penalty !== undefined ? Number(advancedSettings.frequency_penalty) : undefined,
      presence_penalty:
        advancedSettings?.presence_penalty !== undefined ? Number(advancedSettings.presence_penalty) : undefined,
      stream: advancedSettings?.stream !== undefined ? advancedSettings.stream === 'true' : undefined,
      stream_options:
        advancedSettings?.stream_options_include_usage !== undefined
          ? { include_usage: advancedSettings?.stream_options_include_usage === 'true' }
          : undefined,
      stop: advancedSettings?.stop !== undefined ? advancedSettings.stop : undefined,
      use_cache: getCacheValue(advancedSettings?.cache),
      workflowai_tools: getWorkflowAITools(tools),
      tools: getOpenAITools(tools),
    };

    const path = `${API_URL}/v1/chat/completions`;

    const lastMessage = await SSEClient<OpenAIProxyChatCompletionRequest, { id: string }>(
      path,
      Method.POST,
      body,
      () => {},
      signal
    );

    return lastMessage.id;
  },
}));
