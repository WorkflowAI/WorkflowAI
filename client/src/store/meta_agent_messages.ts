import { produce } from 'immer';
import { create } from 'zustand';
import { Method, SSEClient } from '@/lib/api/client';
import { TaskID, TenantID } from '@/types/aliases';
import { MetaAgentChatMessage, MetaAgentChatRequest, PlaygroundState, Provider } from '../types/workflowAI/models';
import { rootTaskPathNoProxy } from './utils';

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

function makeAllNotUsedToolCallsIgnored(messages: MetaAgentChatMessage[]): MetaAgentChatMessage[] {
  return messages.map((message) => {
    if (!!message.tool_call && message.tool_call.status === 'assistant_proposed') {
      return {
        ...message,
        tool_call: {
          ...message.tool_call,
          status: 'user_ignored',
        },
      };
    }
    return message;
  });
}

export type ProviderConfig = {
  provider: Provider;
};

export type MetaAgentChatResponse = {
  messages: MetaAgentChatMessage[];
};

interface MetaAgentChatState {
  isLoadingByTaskId: Record<TaskID, boolean>;
  isInitializedByTaskId: Record<TaskID, boolean>;
  messagesByTaskId: Record<TaskID, MetaAgentChatMessage[] | undefined>;

  remove: (taskId: TaskID) => void;

  reset: (tenant: TenantID | undefined, taskId: TaskID, playgroundState: PlaygroundState) => void;

  sendMessage: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    text: string | undefined,
    role: 'USER' | 'PLAYGROUND',
    playgroundState: PlaygroundState,
    signal?: AbortSignal
  ) => Promise<void>;

  updateStateForToolCallId: (
    taskId: TaskID,
    toolCallId: string,
    status: 'assistant_proposed' | 'user_ignored' | 'completed' | 'failed'
  ) => void;
}

const loadMetaAgentChatFromStorage = (): Partial<MetaAgentChatState> => {
  if (!isBrowser()) {
    return {};
  }

  try {
    const stored = localStorage.getItem('persistedMetaAgentMessages');
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        isInitializedByTaskId: parsed.isInitializedByTaskId || {},
        isLoadingByTaskId: parsed.isLoadingByTaskId || {},
        messagesByTaskId: parsed.messagesByTaskId || {},
      };
    }
  } catch (error) {
    console.error('Error loading meta agent chat from storage:', error);
  }
  return {};
};

export const useMetaAgentChat = create<MetaAgentChatState>((set, get) => ({
  isLoadingByTaskId: loadMetaAgentChatFromStorage().isLoadingByTaskId || {},
  isInitializedByTaskId: loadMetaAgentChatFromStorage().isInitializedByTaskId || {},
  messagesByTaskId: loadMetaAgentChatFromStorage().messagesByTaskId || {},

  remove: (taskId: TaskID) => {
    set(
      produce((state: MetaAgentChatState) => {
        state.isInitializedByTaskId[taskId] = false;
        state.isLoadingByTaskId[taskId] = false;
        state.messagesByTaskId[taskId] = undefined;

        const item = JSON.stringify({
          isInitializedByTaskId: state.isInitializedByTaskId,
          isLoadingByTaskId: state.isLoadingByTaskId,
          messagesByTaskId: state.messagesByTaskId,
        });

        localStorage.setItem('persistedMetaAgentMessages', item);
      })
    );
  },

  reset: (tenant: TenantID | undefined, taskId: TaskID, playgroundState: PlaygroundState) => {
    get().remove(taskId);
    get().sendMessage(tenant, taskId, undefined, 'USER', playgroundState);
  },

  sendMessage: async (
    tenant: TenantID | undefined,
    taskId: TaskID,
    text: string | undefined,
    role: 'USER' | 'PLAYGROUND',
    playgroundState: PlaygroundState,
    signal?: AbortSignal
  ) => {
    const oldMessages = get().messagesByTaskId[taskId];
    let messages: MetaAgentChatMessage[] | undefined;

    const isLoading = get().isLoadingByTaskId[taskId];

    if (!!isLoading) {
      return;
    }

    if (!!oldMessages && oldMessages.length > 0) {
      messages = oldMessages;
    }

    if (!!text) {
      const previousMessages = makeAllNotUsedToolCallsIgnored(messages || []);
      messages = [...previousMessages, { role: role, content: text }];
    }

    if (!!messages && messages.length > 0 && !text) {
      return;
    }

    set(
      produce((state: MetaAgentChatState) => {
        state.isLoadingByTaskId[taskId] = true;
        state.messagesByTaskId[taskId] = messages;
      })
    );

    const request: MetaAgentChatRequest = {
      messages: messages ?? [],
      playground_state: playgroundState,
    };

    const updateMessages = (response: MetaAgentChatResponse) => {
      const previouseMessages = messages ?? [];
      const updatedMessages = !!response.messages ? [...previouseMessages, ...response.messages] : previouseMessages;

      if (signal?.aborted) {
        return;
      }

      set(
        produce((state: MetaAgentChatState) => {
          state.messagesByTaskId[taskId] = updatedMessages;
        })
      );
    };

    try {
      const path = `${rootTaskPathNoProxy(tenant)}/${taskId}/prompt-engineer-agent/messages`;

      const response = await SSEClient<MetaAgentChatRequest, MetaAgentChatResponse>(
        path,
        Method.POST,
        request,
        updateMessages,
        signal
      );

      set(
        produce((state: MetaAgentChatState) => {
          const previouseMessages = messages ?? [];

          const updatedMessages = !!response.messages
            ? [...previouseMessages, ...response.messages]
            : previouseMessages;

          state.messagesByTaskId[taskId] = updatedMessages;
          state.isLoadingByTaskId[taskId] = false;
          state.isInitializedByTaskId[taskId] = true;

          localStorage.setItem(
            'persistedMetaAgentMessages',
            JSON.stringify({
              isInitializedByTaskId: state.isInitializedByTaskId,
              isLoadingByTaskId: state.isLoadingByTaskId,
              messagesByTaskId: state.messagesByTaskId,
            })
          );
        })
      );
    } finally {
      set(
        produce((state: MetaAgentChatState) => {
          state.isLoadingByTaskId[taskId] = false;
          state.isInitializedByTaskId[taskId] = true;
        })
      );
    }
  },

  updateStateForToolCallId: (
    taskId: TaskID,
    toolCallId: string,
    status: 'assistant_proposed' | 'user_ignored' | 'completed' | 'failed'
  ) => {
    set(
      produce((state: MetaAgentChatState) => {
        const messages = state.messagesByTaskId[taskId];
        if (!messages) {
          return;
        }

        let didUpdate = false;
        const updatedMessages = messages.map((message) => {
          if (message.tool_call?.tool_call_id === toolCallId && message.tool_call?.status !== status) {
            didUpdate = true;
            return {
              ...message,
              tool_call: {
                ...message.tool_call,
                status: status,
              },
            };
          }
          return message;
        });

        if (!didUpdate) {
          return;
        }

        state.messagesByTaskId[taskId] = updatedMessages;

        const item = JSON.stringify({
          isInitializedByTaskId: state.isInitializedByTaskId,
          isLoadingByTaskId: state.isLoadingByTaskId,
          messagesByTaskId: state.messagesByTaskId,
        });

        localStorage.setItem('persistedMetaAgentMessages', item);
      })
    );
  },
}));
