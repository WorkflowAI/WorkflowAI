import { Add16Regular } from '@fluentui/react-icons';
import { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';
import { ProxyMessage } from '@/types/workflowAI';
import { ProxyMessageView } from './ProxyMessageView';
import { ExtendedMessageType, allExtendedMessageTypes, cleanMessagesAndAddIDs, createEmptyMessage } from './utils';

type Props = {
  messages: ProxyMessage[] | undefined;
  setMessages?: (messages: ProxyMessage[] | undefined) => void;

  defaultType?: ExtendedMessageType;
  avaibleTypes?: ExtendedMessageType[];

  className?: string;

  onMoveToVersion?: (message: ProxyMessage) => void;
  allowRemovalOfLastMessage?: boolean;

  inputVariblesKeys?: string[];
  supportInputVaribles?: boolean;
  supportRunDetails?: boolean;
  revertOrder?: boolean;
};

export function ProxyMessagesView(props: Props) {
  const {
    messages,
    setMessages,

    defaultType = allExtendedMessageTypes[0],
    avaibleTypes = allExtendedMessageTypes,

    className,

    onMoveToVersion,
    allowRemovalOfLastMessage = true,

    inputVariblesKeys,
    supportInputVaribles = true,
    supportRunDetails = false,
    revertOrder = false,
  } = props;

  const [isHovering, setIsHovering] = useState(false);

  const readonly = !setMessages;

  const cleanedMessages = useMemo(() => {
    const result = cleanMessagesAndAddIDs(messages);
    if (revertOrder && result) {
      return result.reverse();
    }
    return result;
  }, [messages, revertOrder]);

  const onMessageChange = useCallback(
    (message: ProxyMessage | undefined, index: number) => {
      if (!setMessages) {
        return;
      }

      if (message) {
        const newMessages = cleanedMessages?.map((m, i) => (i === index ? message : m));
        setMessages(newMessages ?? [message]);
      } else {
        const newMessages = cleanedMessages?.filter((_, i) => i !== index);
        if (newMessages && newMessages.length > 0) {
          setMessages(newMessages);
        } else {
          setMessages(undefined);
        }
      }
    },
    [cleanedMessages, setMessages]
  );

  const addMessage = useCallback(
    (index?: number) => {
      if (!setMessages) {
        return;
      }

      const lastIndex = !!cleanedMessages && cleanedMessages.length > 0 ? cleanedMessages.length - 1 : 0;
      const previouseIndex = Math.max(0, index ?? lastIndex);
      const previouseMessage = cleanedMessages?.[previouseIndex];

      const allMessages = cleanedMessages ?? [];
      const newMessage = createEmptyMessage(defaultType, previouseMessage);

      if (index === undefined || index >= allMessages.length) {
        setMessages([...allMessages, newMessage]);
      } else {
        const newMessages = [...allMessages];
        newMessages.splice(index, 0, newMessage);
        setMessages(newMessages);
      }
    },
    [cleanedMessages, setMessages, defaultType]
  );

  const handleMoveToVersion = useCallback(
    (index: number) => {
      const message = cleanedMessages?.[index];
      if (!message) {
        return;
      }

      onMessageChange(undefined, index);
      onMoveToVersion?.(message);
    },
    [cleanedMessages, onMessageChange, onMoveToVersion]
  );

  const thereAreNoMessages = cleanedMessages?.length === 0 || !cleanedMessages;
  const showAddMessageButton = (isHovering || thereAreNoMessages) && !readonly;

  return (
    <div
      className={cn('flex flex-col gap-2 h-max w-full flex-shrink-0', className)}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {cleanedMessages?.map((message, index) => (
        <ProxyMessageView
          key={message.internal_id ?? index}
          message={message}
          setMessage={(message) => onMessageChange(message, index)}
          avaibleTypes={avaibleTypes}
          addMessageAbove={() => addMessage(index)}
          addMessageBelow={() => addMessage(index + 1)}
          onMoveToVersion={onMoveToVersion ? () => handleMoveToVersion(index) : undefined}
          readonly={readonly}
          isLastMessage={(!cleanedMessages || cleanedMessages?.length === 1) && !allowRemovalOfLastMessage}
          previouseMessage={cleanedMessages?.[index - 1]}
          inputVariblesKeys={inputVariblesKeys}
          supportInputVaribles={supportInputVaribles}
          supportRunDetails={supportRunDetails}
        />
      ))}
      {showAddMessageButton && (
        <div className='flex flex-row gap-2 py-2'>
          <Button variant='newDesign' size='sm' icon={<Add16Regular />} onClick={() => addMessage()}>
            Add Message
          </Button>
        </div>
      )}
    </div>
  );
}
