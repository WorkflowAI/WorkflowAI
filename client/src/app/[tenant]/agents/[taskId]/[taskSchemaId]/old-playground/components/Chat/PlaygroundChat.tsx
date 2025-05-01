import { ChevronLeftFilled, ChevronRightFilled, ComposeRegular } from '@fluentui/react-icons';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocalStorage } from 'usehooks-ts';
import { WorkflowAIIcon } from '@/components/Logos/WorkflowAIIcon';
import { TaskConversationMessages } from '@/components/NewTaskModal/TaskConversation';
import { TaskConversationInput } from '@/components/NewTaskModal/TaskConversation';
import { ConversationMessage } from '@/components/NewTaskModal/TaskConversationMessage';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { ExtendedBordersContainer } from '@/components/v2/ExtendedBordersContainer';
import { ToolCallName } from '@/store/playgroundChatStore';
import { ModelOptional, TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { PlaygroundState } from '@/types/workflowAI/models';
import { UniversalToolCallMessage } from './UniversalToolCallMessage';
import { UnknownToolCall } from './UnknownToolCall';
import { usePlaygroundChatToolCalls } from './hooks/usePlaygroundChatToolCalls';

type Props = {
  tenant: TenantID | undefined;
  taskId: TaskID;
  schemaId: TaskSchemaID;
  playgroundState: PlaygroundState;
  onShowEditSchemaModal: (message?: string) => void;
  improveInstructions: (text: string, runId: string | undefined) => Promise<void>;
  changeModels: (
    columnsAndModels: {
      column: number;
      model: ModelOptional | undefined;
    }[]
  ) => void;
  generateNewInput: (instructions: string | undefined) => Promise<void>;
  onCancelChatToolCallOnPlayground: () => void;
  scrollToInput: () => void;
  scrollToOutput: () => void;
};

export function PlaygroundChat(props: Props) {
  const {
    tenant,
    taskId,
    schemaId,
    playgroundState,
    onShowEditSchemaModal,
    improveInstructions,
    changeModels,
    generateNewInput,
    onCancelChatToolCallOnPlayground,
    scrollToInput,
    scrollToOutput,
  } = props;

  const [open, setOpen] = useLocalStorage('playground-chat-open', true);
  const [width, setWidth] = useLocalStorage('playground-chat-width', 350);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);

  const handleSetOpen = useCallback(
    (value: boolean) => {
      setOpen(value);
    },
    [setOpen]
  );

  const handleMouseDown = (event: React.MouseEvent) => {
    setIsDragging(true);
    dragStartX.current = event.clientX;
    dragStartWidth.current = width;
    event.preventDefault();
  };

  const handleMouseMove = useCallback(
    (event: MouseEvent) => {
      if (isDragging) {
        const deltaX = dragStartX.current - event.clientX;
        const newWidth = Math.min(Math.max(dragStartWidth.current + deltaX, 250), 800);
        setWidth(newWidth);
      }
    },
    [isDragging, setWidth]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);

      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const {
    isLoading,
    messages,
    onSendMessage,
    onClean,
    userMessage,
    setUserMessage,
    inProgressToolCallIds,
    onEditSchema,
    onImproveInstructions,
    onChangeModels,
    onGenerateNewInput,
    onIgnoreToolCall,
    onActionForLastToolCall,
    onIgnoreLastToolCall,
    showStop,
    onStop,
  } = usePlaygroundChatToolCalls({
    tenant,
    taskId,
    schemaId,
    playgroundState,
    onShowEditSchemaModal,
    improveInstructions,
    changeModels,
    generateNewInput,
    onCancelChatToolCallOnPlayground,
    isAutoRunOn: true,
  });

  const convertedMessages: ConversationMessage[] = useMemo(() => {
    const result: ConversationMessage[] = [];

    messages?.forEach((message, index) => {
      let component: React.ReactNode | undefined;
      const toolCall = message.tool_call;

      if (message.role === 'PLAYGROUND') {
        return;
      }

      if (!!toolCall) {
        const isInProgress = toolCall.tool_call_id ? inProgressToolCallIds.has(toolCall.tool_call_id) : false;

        const wasUsed = toolCall.status === 'completed';
        const isIgnored = toolCall.status === 'user_ignored';

        switch (toolCall.tool_name) {
          case ToolCallName.IMPROVE_AGENT_INSTRUCTIONS:
            if ('run_feedback_message' in toolCall) {
              component = (
                <UniversalToolCallMessage
                  title='Improve Instructions?'
                  titleInProgress='Improving instructions...'
                  titleArchived='Instructions were not improved'
                  titleUsed='Instructions were improved'
                  isInProgress={isInProgress}
                  isArchived={isIgnored}
                  wasUsed={wasUsed}
                  onAction={() => onImproveInstructions(toolCall)}
                  onIgnore={() => onIgnoreToolCall(toolCall.tool_call_id)}
                  onInactiveAction={scrollToInput}
                />
              );
            }
            break;
          case ToolCallName.EDIT_AGENT_SCHEMA:
            if ('edition_request_message' in toolCall) {
              component = (
                <UniversalToolCallMessage
                  title='Update Schema?'
                  titleInProgress='Updating schema...'
                  titleArchived='Schema was not updated'
                  titleUsed='Schema was updated'
                  isInProgress={isInProgress}
                  isArchived={isIgnored}
                  wasUsed={wasUsed}
                  onAction={() => onEditSchema(toolCall)}
                  onIgnore={() => onIgnoreToolCall(toolCall.tool_call_id)}
                />
              );
            }
            break;
          case ToolCallName.RUN_CURRENT_AGENT_ON_MODELS:
            component = (
              <UniversalToolCallMessage
                title='Update Models?'
                titleInProgress='Updating models...'
                titleArchived='Models were not updated'
                titleUsed='Models were updated'
                isInProgress={isInProgress}
                isArchived={isIgnored}
                wasUsed={wasUsed}
                onAction={() => onChangeModels(toolCall)}
                onIgnore={() => onIgnoreToolCall(toolCall.tool_call_id)}
                onInactiveAction={scrollToOutput}
              />
            );
            break;
          case ToolCallName.GENERATE_AGENT_INPUT:
            component = (
              <UniversalToolCallMessage
                title='Update Input?'
                titleInProgress='Updating input...'
                titleArchived='Input was not updated'
                titleUsed='Input was updated'
                isInProgress={isInProgress}
                isArchived={isIgnored}
                wasUsed={wasUsed}
                onAction={() => onGenerateNewInput(toolCall)}
                onIgnore={() => onIgnoreToolCall(toolCall.tool_call_id)}
                onInactiveAction={scrollToInput}
              />
            );
            break;
          default:
            component = <UnknownToolCall toolCall={toolCall} />;
        }
      }

      const username = message.role === 'USER' ? 'You' : 'WorkflowAI';

      result.push({
        message: message.content,
        username: username,
        streamed: message.role === 'ASSISTANT' && index === messages.length - 1 && isLoading,
        component: component,
        feedbackToken: message.feedback_token,
      });
    });

    return result;
  }, [
    messages,
    isLoading,
    onEditSchema,
    onImproveInstructions,
    inProgressToolCallIds,
    onChangeModels,
    onGenerateNewInput,
    onIgnoreToolCall,
    scrollToInput,
    scrollToOutput,
  ]);

  const onOpenAndClean = useCallback(() => {
    onClean();
    setOpen(true);
  }, [onClean, setOpen]);

  if (!open) {
    return (
      <div
        className='flex flex-col h-full w-[92px] font-lato py-6 pr-6 cursor-pointer'
        onClick={() => handleSetOpen(true)}
      >
        <ExtendedBordersContainer className='flex flex-col h-full' borderColor='gray-100' margin={24}>
          <div className='flex flex-col justify-between items-center w-full h-full bg-white'>
            <div
              className='flex w-8 h-8 items-center justify-center rounded-full border border-gray-200 mt-3 cursor-pointer'
              onClick={() => handleSetOpen(true)}
            >
              <WorkflowAIIcon className='shrink-0' />
            </div>
            <SimpleTooltip content='Start New Chat' tooltipDelay={0} side='bottom' tooltipClassName='m-1'>
              <Button
                variant='text'
                size='sm'
                icon={<ComposeRegular className='w-5 h-5' />}
                className='mb-3'
                onClick={(event) => {
                  event.stopPropagation();
                  onOpenAndClean();
                }}
              />
            </SimpleTooltip>
            <div className='absolute left-0 top-1/2 transform -translate-y-1/2 -translate-x-1/2'>
              <Button
                variant='newDesign'
                size='none'
                icon={<ChevronLeftFilled className='w-3 h-3' />}
                className='w-5 h-5'
                onClick={(event) => {
                  event.stopPropagation();
                  handleSetOpen(true);
                }}
              />
            </div>
          </div>
        </ExtendedBordersContainer>
      </div>
    );
  }

  return (
    <div className='flex flex-col h-full font-lato py-6 pr-6' style={{ width: `${width}px` }}>
      <ExtendedBordersContainer className='flex flex-col h-full w-full relative' borderColor='gray-100' margin={24}>
        <div
          className='absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-blue-200 transition-colors'
          onMouseDown={handleMouseDown}
          style={{
            left: '-1px',
            cursor: isDragging ? 'grabbing' : 'ew-resize',
          }}
        />
        <div className='flex flex-col w-full h-full bg-white'>
          <div className='flex flex-row text-[13px] text-gray-500 font-medium px-4 py-2 items-center justify-between border-b border-gray-100'>
            <div>Agent</div>
            <div className='flex flex-row items-center gap-4'>
              <SimpleTooltip content='Start New Chat' tooltipDelay={0} side='bottom' tooltipClassName='m-1'>
                <Button
                  variant='text'
                  size='none'
                  icon={<ComposeRegular className='w-4 h-4 text-gray-800' />}
                  onClick={onClean}
                  className='bg-gray-100 rounded-[2px] w-7 h-7 hover:bg-gray-200'
                />
              </SimpleTooltip>
            </div>
          </div>
          <TaskConversationMessages
            messages={convertedMessages}
            loading={isLoading}
            showRetry={false}
            retry={() => {}}
            className='pt-[6px]'
          />
          <TaskConversationInput
            setUserMessage={setUserMessage}
            onSendIteration={onSendMessage}
            userMessage={userMessage}
            autoFocus={false}
            controlYPressed={onActionForLastToolCall}
            controlNPressed={onIgnoreLastToolCall}
            showStop={showStop}
            onStop={onStop}
          />
          <div className='absolute left-0 top-1/2 transform -translate-y-1/2 -translate-x-1/2'>
            <Button
              variant='newDesign'
              size='none'
              icon={<ChevronRightFilled className='w-3 h-3' />}
              className='w-5 h-5'
              onClick={() => handleSetOpen(false)}
            />
          </div>
        </div>
      </ExtendedBordersContainer>
    </div>
  );
}
