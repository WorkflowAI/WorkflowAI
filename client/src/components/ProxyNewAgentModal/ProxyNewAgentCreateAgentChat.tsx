import { useCallback, useMemo, useState } from 'react';
import { NewAgentChatMessage } from '@/store/new_agent_messages';
import { TaskConversation } from '../NewTaskModal/TaskConversation';
import { ConversationMessage } from '../NewTaskModal/TaskConversationMessage';

type Props = {
  sendMessage: (message: string) => Promise<void>;
  messages: NewAgentChatMessage[];
  isLoading: boolean;
  showRetry: boolean;
  onRetry: () => void;
};

export function ProxyNewAgentCreateAgentChat(props: Props) {
  const { sendMessage, messages, isLoading, showRetry, onRetry } = props;

  const [userMessage, setUserMessage] = useState('');

  const convertedMessages: ConversationMessage[] = useMemo(() => {
    const result: ConversationMessage[] = [];

    messages?.forEach((message, index) => {
      const username = message.role === 'USER' ? 'You' : 'WorkflowAI';

      result.push({
        message: message.content,
        username: username,
        streamed: message.role === 'ASSISTANT' && index === messages.length - 1 && isLoading,
        component: undefined,
        feedbackToken: undefined,
      });
    });

    return result;
  }, [messages, isLoading]);

  const onSendIteration = useCallback(
    async (text: string) => {
      setUserMessage('');
      await sendMessage(text);
    },
    [sendMessage]
  );

  return (
    <div className='flex flex-col h-full w-full overflow-hidden'>
      <TaskConversation
        userMessage={userMessage}
        messages={convertedMessages}
        setUserMessage={setUserMessage}
        onSendIteration={() => onSendIteration(userMessage)}
        loading={isLoading}
        showRetry={showRetry}
        retry={onRetry}
        showLoadingWhenStreamingStarted={true}
      />
    </div>
  );
}
