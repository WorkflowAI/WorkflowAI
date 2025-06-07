import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { ProxyMessage, ProxyMessageWithID } from '@/types/workflowAI';
import { cleanMessagesAndAddIDs } from '../../proxy-messages/utils';
import { ProxyDiffMessageView } from './ProxyDiffMessageView';

type Props = {
  messages: ProxyMessage[] | undefined;
  oldMessages: ProxyMessage[] | undefined;
  inputVariblesKeys?: string[];
  className?: string;
};

export function ProxyDiffMessagesView(props: Props) {
  const { messages, oldMessages, inputVariblesKeys, className } = props;

  const cleanedMessages = useMemo(() => {
    return cleanMessagesAndAddIDs(messages);
  }, [messages]);

  const cleanedOldMessages = useMemo(() => {
    return cleanMessagesAndAddIDs(oldMessages);
  }, [oldMessages]);

  const entries: { newMessage: ProxyMessageWithID | undefined; oldMessage: ProxyMessageWithID | undefined }[] =
    useMemo(() => {
      const result: { newMessage: ProxyMessageWithID | undefined; oldMessage: ProxyMessageWithID | undefined }[] = [];
      const matchedOldMessagesIds: string[] = [];

      cleanedMessages?.forEach((message, index) => {
        const oldMessage = cleanedOldMessages?.[index];

        const isOldMessagePureText = oldMessage?.content.length === 1 && oldMessage?.content[0].text !== undefined;
        const isNewMessagePureText = message.content.length === 1 && message.content[0].text !== undefined;
        const didMatch = isOldMessagePureText && isNewMessagePureText;

        if (didMatch && !!oldMessage && !!oldMessage.internal_id) {
          matchedOldMessagesIds.push(oldMessage.internal_id);
        }

        result.push({
          newMessage: message,
          oldMessage: didMatch ? oldMessage : undefined,
        });
      });

      cleanedOldMessages?.forEach((message) => {
        if (!!message.internal_id && matchedOldMessagesIds.includes(message.internal_id)) {
          return;
        }

        result.push({
          newMessage: undefined,
          oldMessage: message,
        });
      });

      return result;
    }, [cleanedMessages, cleanedOldMessages]);

  return (
    <div className={cn('flex flex-col gap-2 h-max w-full flex-shrink-0', className)}>
      {entries.map((entry, index) => (
        <ProxyDiffMessageView
          key={entry.newMessage?.internal_id ?? entry.oldMessage?.internal_id ?? index}
          message={entry.newMessage}
          oldMessage={entry.oldMessage}
          inputVariblesKeys={inputVariblesKeys}
        />
      ))}
    </div>
  );
}
