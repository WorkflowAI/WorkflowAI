import { Add12Regular, Open16Regular } from '@fluentui/react-icons';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useMemo, useState } from 'react';
import { useCopyToClipboard } from 'usehooks-ts';
import { Button } from '@/components/ui/Button';
import { displaySuccessToaster } from '@/components/ui/Sonner';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { taskSchemaRoute } from '@/lib/routeFormatter';
import { cn } from '@/lib/utils';
import { useOrFetchRunV1 } from '@/store/fetchers';
import { useOrFetchRunCompletions } from '@/store/fetchers';
import { TaskSchemaID, TenantID } from '@/types/aliases';
import { TaskID } from '@/types/aliases';
import { ProxyMessage, ProxyMessageContent } from '@/types/workflowAI';
import { ProxyMessageViewHeader } from './ProxyMessageViewHeader';
import { ProxyFile } from './components/ProxyFile';
import { ProxyMessageRunFooter } from './components/ProxyMessageRunFooter';
import { ProxyTextarea } from './components/ProxyTextarea';
import { ProxyToolCallRequest } from './components/ProxyToolCallRequest';
import { ProxyToolCallResultView } from './components/ProxyToolCallResult';
import { ProxyToolCallResultInstantEditView } from './components/ProxyToolCallResultInstantEditView';
import {
  ContentType,
  ExtendedMessageType,
  createEmptyMessageContent,
  getContentToCopy,
  getContentTypeForContent,
  getContentTypes,
  getExtendedMessageType,
  getMessageType,
  isProxyMessageContentEmpty,
  requiredContentTypeForType,
} from './utils';

type Props = {
  id?: string;
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
  inputVariblesKeys?: string[];
  supportInputVaribles?: boolean;
  supportRunDetails?: boolean;
  supportOpeningInPlayground?: boolean;
  supportToolCallResultInstantEdit?: boolean;
  onTextareaFocus?: () => void;
  onTextareaBlur?: () => void;
};

export function ProxyMessageView(props: Props) {
  const {
    id,
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
    inputVariblesKeys,
    supportInputVaribles = true,
    supportRunDetails = false,
    supportOpeningInPlayground = true,
    supportToolCallResultInstantEdit = false,
    onTextareaFocus,
    onTextareaBlur,
  } = props;

  const { tenant, taskId } = useParams();
  const { run } = useOrFetchRunV1(tenant as TenantID, taskId as TaskID, message.run_id);
  const { completions } = useOrFetchRunCompletions(tenant as TenantID, taskId as TaskID, message.run_id);

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

  const showMoveButton = false;

  const showRunDetails = useMemo(() => {
    return supportRunDetails && !!message.run_id && message.role === 'assistant';
  }, [message.run_id, message.role, supportRunDetails]);

  const router = useRouter();

  const onTryInPlayground = useCallback(() => {
    if (!run) {
      return;
    }

    const route = taskSchemaRoute(tenant as TenantID, taskId as TaskID, `${run.task_schema_id}` as TaskSchemaID, {
      versionId: run.version.id,
      taskRunId1: message.run_id,
      baseRunId: message.run_id,
    });

    router.push(route);
  }, [run, tenant, taskId, message.run_id, router]);

  const [, copy] = useCopyToClipboard();

  const onCopy = useCallback(() => {
    copy(getContentToCopy(message));
    displaySuccessToaster('Copied to clipboard');
  }, [copy, message]);

  return (
    <div
      id={id}
      className='flex flex-col relative'
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <div
        className={cn(
          'flex flex-col border border-gray-200 min-h-[50px] bg-white pb-3',
          showRunDetails ? 'rounded-t-[2px]' : 'rounded-[2px]'
        )}
      >
        <ProxyMessageViewHeader
          type={getExtendedMessageType(message.role, message.content)}
          isHovering={isHovering}
          avaibleTypes={avaibleTypes}
          onRemove={oneMessageMode || isLastMessage ? undefined : onRemove}
          onChangeType={(type) => onChangeType(type)}
          onAddContentEntry={onAddContentEntry}
          onCopy={onCopy}
          readonly={readonly}
        />
        <div className='flex flex-col gap-[10px]'>
          {message.content.map((content, index) => {
            return (
              <div key={index} className='flex flex-col gap-[10px]'>
                {content.text !== undefined && (
                  <div className='flex w-full'>
                    <ProxyTextarea
                      key={index}
                      content={content}
                      setContent={(content) => onMessageChange(index, content)}
                      placeholder='Message text content'
                      readOnly={readonly}
                      inputVariblesKeys={inputVariblesKeys}
                      supportInputVaribles={supportInputVaribles}
                      supportObjectViewerIfPossible={message.role === 'assistant'}
                      onFocus={onTextareaFocus}
                      onBlur={onTextareaBlur}
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
                    {supportToolCallResultInstantEdit ? (
                      <ProxyToolCallResultInstantEditView
                        result={content.tool_call_result}
                        setContent={(content) => onMessageChange(index, content)}
                      />
                    ) : (
                      <ProxyToolCallResultView
                        result={content.tool_call_result}
                        setContent={(content) => onMessageChange(index, content)}
                        readonly={readonly}
                      />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {showRunDetails && !!message.run_id && <ProxyMessageRunFooter run={run} completions={completions} />}

      {isHovering && !readonly && !oneMessageMode && (
        <>
          <SimpleTooltip
            content='Add message above'
            tooltipDelay={0}
            triggerClassName='absolute top-0 left-[50%] -translate-x-1/2 -translate-y-[7px] w-4 h-4 items-center justify-center'
          >
            <Button
              variant='newDesignText'
              size='none'
              className='w-4 h-4 p-0.5 bg-gray-100 rounded-[2px] border border-gray-200'
              icon={<Add12Regular className='w-3 h-3' />}
              onClick={addMessageAbove}
            />
          </SimpleTooltip>

          <SimpleTooltip
            content='Add message below'
            tooltipDelay={0}
            triggerClassName='absolute bottom-0 left-[50%] -translate-x-1/2 translate-y-[8px] w-4 h-4 items-center justify-center'
          >
            <Button
              variant='newDesignText'
              size='none'
              className='w-4 h-4 p-0.5 bg-gray-100 rounded-[2px] border border-gray-200'
              icon={<Add12Regular className='w-3 h-3' />}
              onClick={addMessageBelow}
            />
          </SimpleTooltip>
        </>
      )}

      {showRunDetails && supportOpeningInPlayground && !!message.run_id && isHovering && (
        <div className='absolute top-0 right-0 translate-x-2 -translate-y-[17px] items-center justify-center z-10'>
          <Button
            variant='newDesign'
            size='sm'
            icon={<Open16Regular className='w-4 h-4' />}
            onClick={onTryInPlayground}
          >
            Load From Here In Playground
          </Button>
        </div>
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
