import { Add12Regular } from '@fluentui/react-icons';
import { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { ProxyMessage, ProxyMessageContent } from '@/types/workflowAI';
import {
  ContentType,
  ExtendedMessageType,
  createEmptyMessageContent,
  getContentTypeForContent,
  getContentTypes,
  getExtendedMessageType,
  getMessageType,
  isProxyMessageContentEmpty,
  requiredContentTypeForType,
} from '../utils';
import { ProxyMessageViewHeader } from './ProxyMessageViewHeader';
import { ProxyFile } from './components/ProxyFile';
import { ProxyTextarea } from './components/ProxyTextarea';
import { ProxyToolCallRequest } from './components/ProxyToolCallRequest';
import { ProxyToolCallResultView } from './components/ProxyToolCallResult';

type Props = {
  message: ProxyMessage;
  setMessage?: (message: ProxyMessage | undefined) => void;
  avaibleTypes: ExtendedMessageType[];
  addMessageAbove?: () => void;
  addMessageBelow?: () => void;
  onMoveToVersion?: () => void;
  readonly?: boolean;
  oneMessageMode?: boolean;
  isLastMessage?: boolean;
  previouseMessage?: ProxyMessage;
};

export function ProxyMessageView(props: Props) {
  const {
    message,
    setMessage,
    avaibleTypes,
    addMessageAbove,
    addMessageBelow,
    onMoveToVersion,
    readonly,
    oneMessageMode = false,
    isLastMessage = false,
    previouseMessage,
  } = props;

  const onMessageChange = useCallback(
    (index: number, content: ProxyMessageContent) => {
      if (!setMessage) {
        return;
      }

      const newMessage = {
        ...message,
        content: message.content.map((item, i) => (i === index ? content : item)),
      };

      setMessage(newMessage);
    },
    [message, setMessage]
  );

  const onAddContentEntry = useCallback(
    (type: ContentType) => {
      if (!setMessage) {
        return;
      }

      const newMessage = {
        ...message,
        content: [...message.content, createEmptyMessageContent(type)],
      };

      setMessage(newMessage);
    },
    [message, setMessage]
  );

  const onRemoveContentEntry = useCallback(
    (index: number) => {
      if (!setMessage) {
        return;
      }

      const newMessage = {
        ...message,
        content: message.content.filter((_, i) => i !== index),
      };

      setMessage(newMessage);
    },
    [message, setMessage]
  );

  const onChangeType = useCallback(
    (type: ExtendedMessageType) => {
      if (!setMessage) {
        return;
      }

      const normalType = getMessageType(type);
      const contentTypes = getContentTypes(type);
      const defaultContentType = requiredContentTypeForType(type);

      const newContent: ProxyMessageContent[] = [];
      let isDefaultContentTypeAlreadyInContent = false;

      message.content.forEach((content) => {
        if (isProxyMessageContentEmpty(content)) {
          return;
        }

        const contentType = getContentTypeForContent(content);

        if (contentType && contentTypes.includes(contentType)) {
          newContent.push(content);
        }

        if (contentType === defaultContentType) {
          isDefaultContentTypeAlreadyInContent = true;
        }
      });

      if (!isDefaultContentTypeAlreadyInContent) {
        newContent.unshift(createEmptyMessageContent(defaultContentType, previouseMessage));
      }

      const newMessage = {
        ...message,
        content: newContent,
        role: normalType,
      };

      setMessage(newMessage);
    },
    [message, setMessage, previouseMessage]
  );

  const onRemove = useCallback(() => {
    if (!setMessage) {
      return;
    }

    setMessage(undefined);
  }, [setMessage]);

  const [isHovering, setIsHovering] = useState(false);

  const showMoveButton = useMemo(() => {
    if (!onMoveToVersion || readonly) {
      return false;
    }

    return message.role === 'system';
  }, [message.role, onMoveToVersion, readonly]);

  return (
    <div
      className='flex flex-col border border-gray-200 rounded-[2px] min-h-[50px] bg-white pb-3 relative'
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <ProxyMessageViewHeader
        type={getExtendedMessageType(message.role, message.content)}
        isHovering={isHovering}
        avaibleTypes={avaibleTypes}
        onRemove={oneMessageMode || isLastMessage ? undefined : onRemove}
        onChangeType={(type) => onChangeType(type)}
        onAddContentEntry={onAddContentEntry}
        readonly={readonly}
      />
      <div className='flex flex-col gap-[10px]'>
        {message.content.map((content, index) => {
          return (
            <>
              {content.text !== undefined && (
                <div className='flex w-full'>
                  <ProxyTextarea
                    key={index}
                    content={content}
                    setContent={(content) => onMessageChange(index, content)}
                    placeholder='Message text content'
                    readOnly={readonly}
                  />
                </div>
              )}
              {content.file && (
                <div className='flex w-full px-3'>
                  <ProxyFile
                    content={content}
                    setContent={(content) => onMessageChange(index, content)}
                    readonly={readonly}
                    onRemoveContentEntry={() => onRemoveContentEntry(index)}
                  />
                </div>
              )}
              {content.tool_call_request && (
                <div className='flex w-full px-3'>
                  <ProxyToolCallRequest
                    content={content}
                    setContent={(content) => onMessageChange(index, content)}
                    readonly={readonly}
                  />
                </div>
              )}
              {content.tool_call_result && (
                <div className='flex w-full px-3'>
                  <ProxyToolCallResultView
                    result={content.tool_call_result}
                    setContent={(content) => onMessageChange(index, content)}
                    readonly={readonly}
                  />
                </div>
              )}
            </>
          );
        })}
      </div>

      {isHovering && !readonly && !oneMessageMode && (
        <>
          <div className='absolute top-0 left-[50%] -translate-x-1/2 -translate-y-[11px] w-4 h-4 items-center justify-center'>
            <Button
              variant='newDesignText'
              size='none'
              className='w-4 h-4 p-0.5 bg-gray-100 rounded-[2px] border border-gray-200'
              icon={<Add12Regular className='w-3 h-3' />}
              onClick={addMessageAbove}
            />
          </div>

          <div className='absolute bottom-0 left-[50%] -translate-x-1/2 translate-y-[4px] w-4 h-4 items-center justify-center'>
            <Button
              variant='newDesignText'
              size='none'
              className='w-4 h-4 p-0.5 bg-gray-100 rounded-[2px] border border-gray-200'
              icon={<Add12Regular className='w-3 h-3' />}
              onClick={addMessageBelow}
            />
          </div>
        </>
      )}

      {showMoveButton && (
        <div className='absolute top-0 right-0 -translate-x-1/2 -translate-y-[11px] items-center justify-center'>
          <Button variant='newDesign' size='sm' onClick={onMoveToVersion}>
            Move to Version
          </Button>
        </div>
      )}
    </div>
  );
}
