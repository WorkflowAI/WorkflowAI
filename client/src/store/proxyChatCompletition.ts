import { create } from 'zustand';
import {
  AdvancedSettings,
  getCacheValue,
} from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/hooks/useProxyPlaygroundSearchParams';
import {
  getToolsFromMessages,
  parseValidNumber,
  toolChoiceFromValue,
} from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/utils';
import { Method, SSEClient } from '@/lib/api/client';
import { API_URL } from '@/lib/constants';
import { TaskID } from '@/types/aliases';
import {
  OpenAIProxyChatCompletionRequest,
  OpenAIProxyReasoning,
  OpenAIProxyTool,
  ProxyMessage,
  ToolKind,
  Tool_Output,
} from '@/types/workflowAI';

type OpenAIProxyChatCompletionResponse = {
  id: string;
  choices?: { delta?: { content?: string } }[];
};

function getRunId(id: string): string {
  const parts = id.split('/');
  if (parts.length > 1) {
    return parts[1];
  }
  return id;
}

function getContent(response: OpenAIProxyChatCompletionResponse): Record<string, unknown> {
  const text = response.choices?.[0]?.delta?.content;
  try {
    const output = JSON.parse(text ?? '{}');
    return output;
  } catch (error) {
    console.error(error);
    return { content: text };
  }
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

function getReasoningObject(reasoning: string | undefined): OpenAIProxyReasoning | undefined {
  const numberValue = Number(reasoning);

  const effort = isNaN(numberValue) ? reasoning : undefined;
  const budget = isNaN(numberValue) ? undefined : numberValue;

  if (effort !== undefined) {
    return { effort };
  }

  if (budget !== undefined) {
    return { budget };
  }

  return undefined;
}

interface ProxyChatCompletitionState {
  performRun(
    taskId: TaskID,
    variantId: string,
    model: string,
    reasoning: string | undefined,
    input: Record<string, unknown> | undefined,
    versionMessages: ProxyMessage[],
    advancedSettings: AdvancedSettings | undefined,
    tools?: (ToolKind | Tool_Output)[],
    onMessage?: (runId: string, output: Record<string, unknown>) => void,
    signal?: AbortSignal
  ): Promise<string>;
}

export const useProxyChatCompletition = create<ProxyChatCompletitionState>(() => ({
  performRun: async (
    taskId,
    variantId,
    model,
    reasoning,
    input,
    versionMessages,
    advancedSettings,
    tools,
    onMessage,
    signal
  ) => {
    const stream_options = { valid_json_chunks: true };

    const body: OpenAIProxyChatCompletionRequest = {
      agent_id: taskId,
      input,
      messages: [],
      model: model,
      temperature: parseValidNumber(advancedSettings?.temperature),
      max_tokens: parseValidNumber(advancedSettings?.max_tokens),
      top_p: parseValidNumber(advancedSettings?.top_p),
      frequency_penalty: parseValidNumber(advancedSettings?.frequency_penalty),
      presence_penalty: parseValidNumber(advancedSettings?.presence_penalty),
      stream: true,
      stream_options,
      use_cache: getCacheValue(advancedSettings?.cache),
      workflowai_tools: getToolsFromMessages(versionMessages),
      tools: getOpenAITools(tools),
      tool_choice: toolChoiceFromValue(advancedSettings?.tool_choice),
      workflowai_internal: {
        variant_id: variantId,
        version_messages: versionMessages,
      },
      reasoning: getReasoningObject(reasoning),
    };

    const path = `${API_URL}/v1/chat/completions`;

    const lastMessage = await SSEClient<OpenAIProxyChatCompletionRequest, OpenAIProxyChatCompletionResponse>(
      path,
      Method.POST,
      body,
      (message) => {
        const runId = getRunId(message.id);
        const content = getContent(message);
        onMessage?.(runId, content);
      },
      signal
    );

    const runId = getRunId(lastMessage.id);
    const content = getContent(lastMessage);
    onMessage?.(runId, content);

    return runId;
  },
}));
