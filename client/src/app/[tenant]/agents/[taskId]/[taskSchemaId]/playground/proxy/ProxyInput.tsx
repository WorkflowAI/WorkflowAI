import { useCallback, useEffect, useState } from 'react';
import { GeneralizedTaskInput } from '@/types/task_run';
import { ToolKind, Tool_Output } from '@/types/workflowAI';
import { ProxyMessagesView } from './ProxyMessagesView';
import { ProxyParameters } from './ProxyParameters';
import { ProxyMessage, createEmptySystemMessage, createEmptyUserMessage } from './utils';

interface Props {
  input: GeneralizedTaskInput | undefined;
  setInput: (input: GeneralizedTaskInput) => void;
  temperature: number;
  setTemperature: (temperature: number) => void;
  handleRunTasks: () => void;
  toolCalls: (ToolKind | Tool_Output)[] | undefined;
  setToolCalls: (toolCalls: (ToolKind | Tool_Output)[] | undefined) => void;
  maxHeight: number | undefined;
}

export function ProxyInput(props: Props) {
  const { input, setInput, temperature, setTemperature, handleRunTasks, toolCalls, setToolCalls, maxHeight } = props;

  const [systemMessage, setSystemMessage] = useState<ProxyMessage>(createEmptySystemMessage());
  const [otherMessages, setOtherMessages] = useState<ProxyMessage[]>([createEmptyUserMessage()]);

  useEffect(() => {
    if (!input || !('messages' in input)) {
      return;
    }

    const taskInput = input as Record<string, unknown>;
    const messages = taskInput?.messages as ProxyMessage[];

    const systemMessage = messages.find((message) => message.role === 'system');
    const otherMessages = messages.filter((message) => message.role !== 'system');

    if (systemMessage) {
      setSystemMessage(systemMessage);
    }

    if (otherMessages.length > 0) {
      setOtherMessages(otherMessages);
    }
  }, [input]);

  const onUpdateInput = useCallback(
    (systemMessage: ProxyMessage, otherMessages: ProxyMessage[]) => {
      const messages = [systemMessage, ...otherMessages];
      const taskInput = {
        messages,
      };
      setInput(taskInput as GeneralizedTaskInput);
    },
    [setInput]
  );

  return (
    <div
      className='flex w-full items-stretch border-b border-gray-200 border-dashed overflow-hidden'
      style={{ maxHeight }}
    >
      <div className='w-1/2 border-r border-gray-200 border-dashed overflow-hidden'>
        <ProxyMessagesView
          messages={otherMessages}
          setMessages={(messages) => onUpdateInput(systemMessage, messages)}
        />
      </div>
      <div className='w-1/2'>
        <ProxyParameters
          systemMessage={systemMessage}
          setSystemMessage={(message) => onUpdateInput(message, otherMessages)}
          temperature={temperature}
          setTemperature={setTemperature}
          handleRunTasks={handleRunTasks}
          toolCalls={toolCalls}
          setToolCalls={setToolCalls}
        />
      </div>
    </div>
  );
}
