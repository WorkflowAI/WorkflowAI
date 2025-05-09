import { nanoid } from 'nanoid';
import { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { DialogContent } from '@/components/ui/Dialog';
import { Dialog } from '@/components/ui/Dialog';
import { Textarea } from '@/components/ui/Textarea';
import { ToolCallPreview } from '@/types/task_run';
import { TaskInputDict, TaskOutputDict, ToolCallRequestWithID } from '@/types/workflowAI';
import { ProxyEditToolCallResult } from './ProxyEditToolCallResult';
import { ProxyMessage, ProxyMessageContent, ToolCallResult } from './utils';

type Props = {
  input: TaskInputDict;
  output: TaskOutputDict;
  toolCalls: ToolCallPreview[] | undefined;
  updateInputAndRun: (input: TaskInputDict) => Promise<void>;
};

export function ProxyReplyView(props: Props) {
  const { input, output, toolCalls, updateInputAndRun } = props;
  const [text, setText] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const toolCallRequest: ToolCallRequestWithID | undefined = useMemo(() => {
    if (!toolCalls || toolCalls.length === 0) {
      return undefined;
    }

    const toolCallPreview = toolCalls[0];

    try {
      return {
        tool_name: toolCallPreview.name,
        tool_input_dict: JSON.parse(toolCallPreview.input_preview),
        id: toolCallPreview.id,
      };
    } catch {
      return undefined;
    }
  }, [toolCalls]);

  const onSendMessage = useCallback(async () => {
    const taskInput = input as Record<string, unknown>;
    const oldMessages = taskInput.messages as ProxyMessage[];

    const messages = [...oldMessages];

    const assistantText = JSON.stringify(output);

    const requestContent: ProxyMessageContent[] = [];

    if (toolCallRequest) {
      requestContent.push({
        tool_call_request: toolCallRequest,
      });
    }

    if (!!assistantText && assistantText !== '{}') {
      requestContent.push({
        text: assistantText,
      });
    }

    const assistantMessage: ProxyMessage = {
      role: 'assistant',
      content: requestContent,
    };

    messages.push(assistantMessage);

    const responseContent: ProxyMessageContent[] = [];

    if (toolCallRequest && !!text) {
      responseContent.push({
        tool_call_result: {
          id: toolCallRequest?.id ?? nanoid(),
          result: text,
          tool_name: toolCallRequest?.tool_name,
          tool_input_dict: toolCallRequest?.tool_input_dict,
        },
      });
    }

    if (!toolCallRequest && !!text) {
      responseContent.push({
        text: text,
      });
    }

    const newMessage: ProxyMessage = {
      role: 'user',
      content: responseContent,
    };

    messages.push(newMessage);

    const updatedInput: TaskInputDict = { ...input, messages };

    setText('');
    setIsLoading(true);
    await updateInputAndRun(updatedInput);
    setIsLoading(false);
  }, [input, text, output, updateInputAndRun, toolCallRequest]);

  return (
    <div className='flex flex-col w-full px-4 py-2 gap-2.5'>
      <Textarea
        className='flex w-full text-gray-900 placeholder:text-gray-500 font-normal text-[13px] rounded-[2px] border-gray-300 overflow-y-auto focus-within:ring-inset'
        placeholder={!!toolCallRequest ? 'Tool Call Result' : 'User Message'}
        value={text}
        onChange={(e) => setText(e.target.value)}
        autoFocus
        disabled={isLoading}
      />
      <div className='flex flex-row w-full justify-between items-center'>
        <div className='flex flex-row gap-2 items-center'>
          {!!toolCallRequest ? (
            <Button variant='newDesign' size='sm' onClick={onSendMessage} disabled={!text}>
              Send Tool Call Result
            </Button>
          ) : (
            <Button variant='newDesign' size='sm' onClick={onSendMessage} disabled={!text}>
              Send
            </Button>
          )}
        </div>
        <div className='text-[12px] text-gray-500'>Will be send to all models</div>
      </div>
    </div>
  );
}
