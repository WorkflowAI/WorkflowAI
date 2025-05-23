import { useCallback, useMemo, useRef } from 'react';
import { GeneralizedTaskInput } from '@/types/task_run';
import { ProxyMessage } from '@/types/workflowAI';

type Props = {
  input: GeneralizedTaskInput | undefined;
  setInput: (input: GeneralizedTaskInput) => void;
};

export function useProxyInputStructure(props: Props) {
  const { input, setInput } = props;

  const newKeyForMessages = useMemo(() => {
    if (!input) {
      return 'messages';
    }

    return 'properties' in input ? 'workflowai.replies' : 'messages';
  }, [input]);

  const { messages, cleanInput } = useMemo(() => {
    if (!input || (!('workflowai.replies' in input) && !('messages' in input))) {
      return { messages: undefined, cleanInput: input as Record<string, unknown> };
    }

    const taskInput = input as Record<string, unknown>;
    const messages = (taskInput['workflowai.replies'] || taskInput['messages']) as ProxyMessage[];

    const cleanTaskInput: Record<string, unknown> = {
      ...taskInput,
    };

    delete cleanTaskInput['workflowai.replies'];
    delete cleanTaskInput['messages'];

    return {
      messages: messages,
      cleanInput: cleanTaskInput,
    };
  }, [input]);

  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const cleanInputRef = useRef(cleanInput);
  cleanInputRef.current = cleanInput;

  const setMessages = useCallback(
    (messages: ProxyMessage[] | undefined) => {
      const taskInput = {
        [newKeyForMessages]: messages,
        ...cleanInputRef.current,
      };

      setInput(taskInput as GeneralizedTaskInput);
    },
    [setInput, newKeyForMessages]
  );

  const setCleanInput = useCallback(
    (cleanInput: Record<string, unknown>) => {
      setInput({ ...cleanInput, [newKeyForMessages]: messagesRef.current });
    },
    [setInput, newKeyForMessages]
  );

  return { messages, setMessages, cleanInput, setCleanInput };
}
