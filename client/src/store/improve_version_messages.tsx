import { enableMapSet } from 'immer';
import { create } from 'zustand';
import { Method, SSEClient } from '@/lib/api/client';
import { TaskID, TenantID } from '@/types/aliases';
import { ProxyMessage } from '@/types/workflowAI';
import { rootTaskPathNoProxyV1 } from './utils';

enableMapSet();

export type ImproveVersionMessagesResponse = {
  improved_messages: ProxyMessage[] | undefined;
  changelog: string[] | undefined;
};

type ImproveVersionMessagesRequest = {
  improvement_instructions: string | undefined;
  overriden_messages: ProxyMessage[] | undefined;
};

interface ImproveVersionMessagesState {
  improveVersionMessages(
    tenant: TenantID | undefined,
    taskId: TaskID,
    versionId: string,
    improvementInstructions: string,
    overridenMessages: ProxyMessage[] | undefined,
    onMessage: (message: ImproveVersionMessagesResponse) => void,
    signal?: AbortSignal
  ): Promise<ImproveVersionMessagesResponse>;
}

export const useImproveVersionMessages = create<ImproveVersionMessagesState>(() => ({
  improveVersionMessages: async (
    tenant,
    taskId,
    versionId,
    improvementInstructions,
    overridenMessages,
    onMessage,
    signal
  ) => {
    const lastMessage = await SSEClient<ImproveVersionMessagesRequest, ImproveVersionMessagesResponse>(
      `${rootTaskPathNoProxyV1(tenant)}/${taskId}/versions/${versionId}/messages/improve`,
      Method.POST,
      {
        improvement_instructions: improvementInstructions,
        overriden_messages: overridenMessages,
      },
      onMessage,
      signal
    );
    return lastMessage;
  },
}));
