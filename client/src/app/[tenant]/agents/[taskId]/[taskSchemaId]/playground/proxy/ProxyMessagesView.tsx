import { Add16Regular } from '@fluentui/react-icons';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Popover, PopoverContent } from '@/components/ui/Popover';
import { PopoverTrigger } from '@/components/ui/Popover';
import { TaskID } from '@/types/aliases';
import { TenantID } from '@/types/aliases';
import { JsonSchema } from '@/types/json_schema';
import { ProxyMessage } from '@/types/workflowAI';
import { ProxyInputVariables } from './ProxyInputVariables';
import { ProxyMessageView } from './ProxyMessageView';
import { createEmptyAgentMessage, createEmptyUserMessage } from './utils';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  title: string;
  messages: ProxyMessage[];
  setMessages: (messages: ProxyMessage[]) => void;
  inputSchema?: JsonSchema;
  input?: Record<string, unknown>;
  setInput?: (input: Record<string, unknown>) => void;
};

export function ProxyMessagesView(props: Props) {
  const { title, messages, setMessages, inputSchema, input, setInput, tenant, taskId } = props;

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

  const [isHovering, setIsHovering] = useState(false);
  const [showAddMessagePopover, setShowAddMessagePopover] = useState(false);

  const addUserMessage = useCallback(() => {
    setShowAddMessagePopover(false);
    setMessages([...messages, createEmptyUserMessage('text')]);
  }, [messages, setMessages]);

  const addAgentMessage = useCallback(() => {
    setShowAddMessagePopover(false);
    setMessages([...messages, createEmptyAgentMessage('text')]);
  }, [messages, setMessages]);

  return (
    <div
      className='flex flex-col w-full h-full'
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <div className='flex w-full items-center px-4 h-[48px] border-b border-gray-200 border-dashed font-semibold text-[16px] text-gray-700 flex-shrink-0 justify-between'>
        <div>{title}</div>
        {(isHovering || showAddMessagePopover) && (
          <Popover open={showAddMessagePopover} onOpenChange={setShowAddMessagePopover}>
            <PopoverTrigger asChild>
              <Button
                variant='newDesign'
                size='sm'
                icon={<Add16Regular />}
                onClick={() => setShowAddMessagePopover(true)}
              >
                Add Message
              </Button>
            </PopoverTrigger>
            <PopoverContent className='flex flex-col w-full p-1 rounded-[2px]'>
              <Button
                variant='newDesignText'
                onClick={() => addUserMessage()}
                className='w-full justify-start hover:bg-gray-100 hover:text-gray-900 font-normal'
              >
                User Message
              </Button>
              <Button
                variant='newDesignText'
                onClick={() => addAgentMessage()}
                className='w-full justify-start hover:bg-gray-100 hover:text-gray-900 font-normal'
              >
                Agent Message
              </Button>
            </PopoverContent>
          </Popover>
        )}
      </div>
      <div className='flex flex-col py-4 gap-2 overflow-y-auto' id='proxy-messages-view'>
        {!!input && !!setInput && (
          <div className='flex px-4 h-max w-full'>
            <ProxyInputVariables
              inputSchema={inputSchema}
              input={undefined}
              setInput={setInput}
              tenant={tenant}
              taskId={taskId}
            />
          </div>
        )}
        <div className='flex flex-col gap-2 px-4 h-max w-full'>
          {messages.map((message, index) => (
            <ProxyMessageView key={index} message={message} setMessage={(message) => onMessageChange(message, index)} />
          ))}
        </div>
      </div>
    </div>
  );
}
