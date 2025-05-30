import { useCallback, useMemo, useRef } from 'react';
import { GeneralizedTaskInput } from '@/types/task_run';
import { ProxyMessage } from '@/types/workflowAI';

type Props = {
  input: GeneralizedTaskInput | undefined;
  setInput?: (input: GeneralizedTaskInput) => void;
};

export function useProxyInputStructure(props: Props) {
  const { input, setInput } = props;

  const { messages, cleanInput } = useMemo(() => {
    if (!input || !('workflowai.replies' in input)) {
      return { messages: undefined, cleanInput: input as Record<string, unknown> };
    }

    const taskInput = input as Record<string, unknown>;
    const messages = taskInput['workflowai.replies'] as ProxyMessage[];

    const cleanTaskInput: Record<string, unknown> = {
      ...taskInput,
    };

    delete cleanTaskInput['workflowai.replies'];

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
      if (!setInput) {
        return;
      }

      const taskInput = {
        ['workflowai.replies']: messages,
        ...cleanInputRef.current,
      };

      setInput(taskInput as GeneralizedTaskInput);
    },
    [setInput]
  );

  const setCleanInput = useCallback(
    (cleanInput: Record<string, unknown>) => {
      if (!setInput) {
        return;
      }

      setInput({ ...cleanInput, ['workflowai.replies']: messagesRef.current });
    },
    [setInput]
  );

  return { messages, setMessages, cleanInput, setCleanInput };
}
