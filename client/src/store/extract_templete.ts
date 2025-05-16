import { enableMapSet, produce } from 'immer';
import { useCallback, useMemo } from 'react';
import { useEffect } from 'react';
import { useRef } from 'react';
import { create } from 'zustand';
import { client } from '@/lib/api';
import { TaskID, TenantID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { ProxyMessage } from '@/types/workflowAI';
import { buildScopeKey, taskSubPath } from './utils';

enableMapSet();

interface ExtractTempleteState {
  schemaByScope: Map<string, JsonSchema>;
  isLoadingByScope: Map<string, boolean>;
  messagesByScope: Map<string, ProxyMessage[]>;

  extract: (
    tenant: TenantID | undefined,
    taskId: TaskID,
    messages: ProxyMessage[],
    signal?: AbortSignal
  ) => Promise<void>;

  clear: (tenant: TenantID | undefined, taskId: TaskID, messages: ProxyMessage[] | undefined) => void;
}

export const useExtractTemplete = create<ExtractTempleteState>((set, get) => ({
  schemaByScope: new Map(),
  isLoadingByScope: new Map(),
  messagesByScope: new Map(),

  extract: async (tenant, taskId, messages, signal) => {
    const scopeKey = buildScopeKey({
      tenant,
      taskId,
    });

    if (get().isLoadingByScope.get(scopeKey)) return;
    set(
      produce((state) => {
        state.isLoadingByScope.set(scopeKey, true);
      })
    );

    const path = taskSubPath(tenant, taskId, '/templates/extract', true);

    try {
      const { json_schema } = await client.post<{ messages: ProxyMessage[] }, { json_schema: JsonSchema }>(
        path,
        {
          messages,
        },
        signal
      );

      set(
        produce((state) => {
          state.schemaByScope.set(scopeKey, json_schema);
        })
      );
    } catch (error) {
      if (signal?.aborted) {
        set(
          produce((state) => {
            state.isLoadingByScope.set(scopeKey, false);
          })
        );
        return;
      }
      console.error('Failed to fetch evaluation inputs', error);
    } finally {
      set(
        produce((state) => {
          state.isLoadingByScope.set(scopeKey, false);
        })
      );
    }
  },

  clear: (tenant, taskId, messages) => {
    set(
      produce((state) => {
        const scopeKey = buildScopeKey({ tenant, taskId });
        state.schemaByScope.delete(scopeKey);
        state.isLoadingByScope.delete(scopeKey);
        if (messages) {
          state.messagesByScope.set(scopeKey, messages);
        } else {
          state.messagesByScope.delete(scopeKey);
        }
      })
    );
  },
}));

function textInProxyMessages(messages: ProxyMessage[] | undefined): string | undefined {
  if (!messages) return undefined;
  let text = '';
  for (const message of messages) {
    message.content.forEach((content) => {
      if (!!content.text) {
        text += content.text;
      }
    });
  }
  return text;
}

function extractInputKeys(messages: ProxyMessage[] | undefined): string[] | undefined {
  if (!messages) return undefined;

  const text = textInProxyMessages(messages);
  if (!text) return undefined;

  const regex = /\{\{(.*?)\}\}/g;
  const matches = text.match(regex);

  if (!matches) return undefined;
  const cleanedMatches = matches.map((match) => match.replace('{{', '').replace('}}', '').trim());
  return cleanedMatches.sort();
}

export const useOrExtractTemplete = (
  tenant: TenantID | undefined,
  taskId: TaskID,
  messages: ProxyMessage[] | undefined
) => {
  const scopeKey = buildScopeKey({ tenant, taskId });

  const isLoading = useExtractTemplete((state) => state.isLoadingByScope.get(scopeKey));
  const lastMessages = useExtractTemplete((state) => state.messagesByScope.get(scopeKey));
  const schema = useExtractTemplete((state) => state.schemaByScope.get(scopeKey));

  const extract = useExtractTemplete((state) => state.extract);
  const clear = useExtractTemplete((state) => state.clear);

  const newInputKeysString: string | undefined = useMemo(() => {
    const keys = extractInputKeys(messages);
    if (!keys) return undefined;
    return keys.join(',');
  }, [messages]);

  const lastInputKeysString: string | undefined = useMemo(() => {
    const keys = extractInputKeys(lastMessages);
    if (!keys) return undefined;
    return keys.join(',');
  }, [lastMessages]);

  const inputKeys: string[] | undefined = useMemo(() => {
    const newKeys = newInputKeysString?.split(',') ?? [];
    const lastKeys = lastInputKeysString?.split(',') ?? [];

    const keys = [...new Set([...newKeys, ...lastKeys])].sort();
    if (keys.length === 0) return undefined;

    return keys;
  }, [newInputKeysString, lastInputKeysString]);

  const abortControllerRef = useRef<AbortController | undefined>(undefined);

  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // Clear states when task or new orginal version messages are changed
  useEffect(() => {
    clear(tenant, taskId, messagesRef.current);
  }, [clear, tenant, taskId]);

  // Request to extract that should be called when a edit to a message is done and the field is not active anymore
  const requestExtract = useCallback(async () => {
    abortControllerRef.current?.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    if (!messages || messages.length === 0 || inputKeys?.length === 0 || inputKeys === undefined) {
      useExtractTemplete.setState(
        produce((state) => {
          state.isLoadingByScope.delete(scopeKey);
          state.schemaByScope.set(scopeKey, {});
        })
      );
      return;
    }

    await extract(tenant, taskId, messages, abortController.signal);
  }, [extract, tenant, taskId, messages, inputKeys, scopeKey]);

  // If new input key was added request extract
  useEffect(() => {
    requestExtract();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputKeys]);

  useEffect(() => {}, [schema]);

  return {
    isLoading,
    schema,
    inputKeys,
    requestExtract,
  };
};
