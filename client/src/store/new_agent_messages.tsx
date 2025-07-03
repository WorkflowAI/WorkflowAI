import { produce } from 'immer';
import { useEffect, useRef } from 'react';
import { useCallback } from 'react';
import { create } from 'zustand';
import { Method, SSEClient } from '@/lib/api/client';
import { API_URL } from '@/lib/constants';
import { TenantID } from '@/types/aliases';

export type NewAgentChatMessage = {
  role: 'USER' | 'ASSISTANT';
  content: string;
};

export type NewAgentRedirect = {
  agent_id: string;
  agent_schema_id: number;
  version_id: string;
  run_id: string;
};

export type NewAgentChatResponse = {
  assistant_answer?: string | null;
  agent_creation_result?: NewAgentRedirect | null;
};

export type NewAgentChatRequest = {
  messages: NewAgentChatMessage[];
};

interface NewAgentChatState {
  isLoadingByChatId: Record<string, boolean>;
  isInitializedByChatId: Record<string, boolean>;
  messagesByChatId: Record<string, NewAgentChatMessage[] | undefined>;
  agent_creation_resultByChatId: Record<string, NewAgentRedirect | undefined>;
  showRetryByChatId: Record<string, boolean>;

  clean: () => void;
  sendMessage: (tenant: TenantID | undefined, chatId: string, text: string, signal?: AbortSignal) => Promise<void>;
  retryLastMessage: (tenant: TenantID | undefined, chatId: string, signal?: AbortSignal) => Promise<void>;
}

export const useNewAgentChat = create<NewAgentChatState>((set, get) => ({
  isLoadingByChatId: {},
  isInitializedByChatId: {},
  messagesByChatId: {},
  agent_creation_resultByChatId: {},
  showRetryByChatId: {},

  clean: () => {
    set(
      produce((state: NewAgentChatState) => {
        state.isInitializedByChatId = {};
        state.isLoadingByChatId = {};
        state.messagesByChatId = {};
        state.agent_creation_resultByChatId = {};
        state.showRetryByChatId = {};
      })
    );
  },

  sendMessage: async (tenant: TenantID | undefined, chatId: string, text: string, signal?: AbortSignal) => {
    const oldMessages = get().messagesByChatId[chatId];

    let messages: NewAgentChatMessage[] | undefined;

    const isLoading = get().isLoadingByChatId[chatId];

    if (!!isLoading) {
      return;
    }

    if (!!oldMessages && oldMessages.length > 0) {
      messages = oldMessages;
    }

    const previousMessages = messages || [];
    messages = [...previousMessages, { role: 'USER', content: text }];

    set(
      produce((state: NewAgentChatState) => {
        state.isLoadingByChatId[chatId] = true;
        state.messagesByChatId[chatId] = messages;
        state.showRetryByChatId[chatId] = false;
      })
    );

    const request: NewAgentChatRequest = {
      messages: messages ?? [],
    };

    const updateMessages = (response: NewAgentChatResponse) => {
      const previouseMessages = messages ?? [];
      const newMessage: NewAgentChatMessage | undefined = response.assistant_answer
        ? { role: 'ASSISTANT', content: response.assistant_answer }
        : undefined;

      const updatedMessages = !!newMessage ? [...previouseMessages, newMessage] : previouseMessages;

      if (signal?.aborted) {
        return;
      }

      set(
        produce((state: NewAgentChatState) => {
          state.messagesByChatId[chatId] = updatedMessages;
        })
      );
    };

    try {
      const path = `${API_URL}/v1/${tenant ?? '_'}/agents/build/messages`;

      const response = await SSEClient<NewAgentChatRequest, NewAgentChatResponse>(
        path,
        Method.POST,
        request,
        updateMessages,
        signal
      );

      set(
        produce((state: NewAgentChatState) => {
          const previouseMessages = messages ?? [];
          const newMessage: NewAgentChatMessage | undefined = response.assistant_answer
            ? { role: 'ASSISTANT', content: response.assistant_answer }
            : undefined;

          const updatedMessages = !!newMessage ? [...previouseMessages, newMessage] : previouseMessages;

          state.messagesByChatId[chatId] = updatedMessages;
          state.isLoadingByChatId[chatId] = false;
          state.isInitializedByChatId[chatId] = true;

          if (!state.agent_creation_resultByChatId[chatId] && !!response.agent_creation_result) {
            state.agent_creation_resultByChatId[chatId] = response.agent_creation_result;
          }
        })
      );
    } catch {
      set(
        produce((state: NewAgentChatState) => {
          state.showRetryByChatId[chatId] = true;
        })
      );
    } finally {
      set(
        produce((state: NewAgentChatState) => {
          state.isLoadingByChatId[chatId] = false;
          state.isInitializedByChatId[chatId] = true;
        })
      );
    }
  },

  retryLastMessage: async (tenant: TenantID | undefined, chatId: string, signal?: AbortSignal) => {
    const messages = get().messagesByChatId[chatId] ?? [];

    const isLoading = get().isLoadingByChatId[chatId];

    if (!!isLoading) {
      return;
    }

    set(
      produce((state: NewAgentChatState) => {
        state.isLoadingByChatId[chatId] = true;
        state.messagesByChatId[chatId] = messages;
        state.showRetryByChatId[chatId] = false;
      })
    );

    const request: NewAgentChatRequest = {
      messages: messages ?? [],
    };

    const updateMessages = (response: NewAgentChatResponse) => {
      const previouseMessages = messages ?? [];
      const newMessage: NewAgentChatMessage | undefined = response.assistant_answer
        ? { role: 'ASSISTANT', content: response.assistant_answer }
        : undefined;

      const updatedMessages = !!newMessage ? [...previouseMessages, newMessage] : previouseMessages;

      if (signal?.aborted) {
        return;
      }

      set(
        produce((state: NewAgentChatState) => {
          state.messagesByChatId[chatId] = updatedMessages;
        })
      );
    };

    try {
      const path = `${API_URL}/v1/${tenant ?? '_'}/agents/build/messages`;

      const response = await SSEClient<NewAgentChatRequest, NewAgentChatResponse>(
        path,
        Method.POST,
        request,
        updateMessages,
        signal
      );

      set(
        produce((state: NewAgentChatState) => {
          const previouseMessages = messages ?? [];
          const newMessage: NewAgentChatMessage | undefined = response.assistant_answer
            ? { role: 'ASSISTANT', content: response.assistant_answer }
            : undefined;

          const updatedMessages = !!newMessage ? [...previouseMessages, newMessage] : previouseMessages;

          state.messagesByChatId[chatId] = updatedMessages;
          state.isLoadingByChatId[chatId] = false;
          state.isInitializedByChatId[chatId] = true;

          if (!state.agent_creation_resultByChatId[chatId] && !!response.agent_creation_result) {
            state.agent_creation_resultByChatId[chatId] = response.agent_creation_result;
          }
        })
      );
    } catch {
      set(
        produce((state: NewAgentChatState) => {
          state.showRetryByChatId[chatId] = true;
        })
      );
    } finally {
      set(
        produce((state: NewAgentChatState) => {
          state.isLoadingByChatId[chatId] = false;
          state.isInitializedByChatId[chatId] = true;
        })
      );
    }
  },
}));

export const useOrFetchNewAgentChat = (chatId: string, tenant: TenantID | undefined) => {
  const messages = useNewAgentChat((state) => state.messagesByChatId[chatId]);
  const agentCreationResult = useNewAgentChat((state) => state.agent_creation_resultByChatId[chatId]);
  const isLoading = useNewAgentChat((state) => state.isLoadingByChatId[chatId]);
  const isInitialized = useNewAgentChat((state) => state.isInitializedByChatId[chatId]);
  const showRetry = useNewAgentChat((state) => state.showRetryByChatId[chatId]);

  const sendMessageNewAgentChat = useNewAgentChat((state) => state.sendMessage);
  const retryLastMessageNewAgentChat = useNewAgentChat((state) => state.retryLastMessage);
  const cleanNewAgentChat = useNewAgentChat((state) => state.clean);

  const sendMessageAbortController = useRef<AbortController | null>(null);
  const sendMessageInProgressRef = useRef(false);

  const updateAbortController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (chatId) {
      cleanNewAgentChat();
    }
  }, [chatId, cleanNewAgentChat]);

  const sendMessage = useCallback(
    async (text: string) => {
      sendMessageInProgressRef.current = true;

      updateAbortController.current?.abort();

      sendMessageAbortController.current?.abort();
      const newAbortController = new AbortController();
      sendMessageAbortController.current = newAbortController;

      await sendMessageNewAgentChat(tenant, chatId, text, newAbortController.signal);
      sendMessageInProgressRef.current = false;
    },
    [sendMessageNewAgentChat, tenant, chatId]
  );

  const retry = useCallback(async () => {
    sendMessageInProgressRef.current = true;

    updateAbortController.current?.abort();

    sendMessageAbortController.current?.abort();
    const newAbortController = new AbortController();
    sendMessageAbortController.current = newAbortController;

    await retryLastMessageNewAgentChat(tenant, chatId, newAbortController.signal);
    sendMessageInProgressRef.current = false;
  }, [retryLastMessageNewAgentChat, tenant, chatId]);

  return {
    messages,
    agentCreationResult,
    isLoading,
    isInitialized,
    sendMessage,
    showRetry,
    retry,
  };
};
