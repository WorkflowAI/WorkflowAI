import { Add16Regular } from '@fluentui/react-icons';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { ProxyMessageView } from './ProxyMessageView';
import { ProxyMessage, createEmptyUserMessage } from './utils';

type Props = {
  messages: ProxyMessage[];
  setMessages: (messages: ProxyMessage[]) => void;
};

export function ProxyMessagesView(props: Props) {
  const { messages, setMessages } = props;

  const onMessageChange = useCallback(
    (message: ProxyMessage | undefined, index: number) => {
      if (message) {
        const newMessages = messages.map((m, i) => (i === index ? message : m));
        setMessages(newMessages);
      } else {
        const newMessages = messages.filter((_, i) => i !== index);
        setMessages(newMessages);
      }
    },
    [messages, setMessages]
  );

  const addMessage = useCallback(() => {
    setMessages([...messages, createEmptyUserMessage('text')]);
  }, [messages, setMessages]);

  const [isHovering, setIsHovering] = useState(false);

  return (
    <div
      className='flex flex-col w-full h-full'
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <div className='flex w-full items-center px-4 h-[48px] border-b border-gray-200 border-dashed font-semibold text-[16px] text-gray-700 flex-shrink-0 justify-between'>
        <div>Messages</div>
        {isHovering && (
          <Button variant='newDesign' size='sm' icon={<Add16Regular />} onClick={() => addMessage()}>
            Add Message
          </Button>
        )}
      </div>
      <div className='flex overflow-y-auto' id='proxy-messages-view'>
        <div className='flex flex-col gap-2 px-4 py-4 h-max w-full'>
          {messages.map((message, index) => (
            <ProxyMessageView key={index} message={message} setMessage={(message) => onMessageChange(message, index)} />
          ))}
        </div>
      </div>
    </div>
  );
}
