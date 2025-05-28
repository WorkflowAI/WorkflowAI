import { nanoid } from 'nanoid';
import { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { ToolCallPreview } from '@/types/task_run';
import { TaskInputDict, TaskOutputDict, ToolCallRequestWithID } from '@/types/workflowAI';
import { ProxyMessage, ProxyMessageContent } from '@/types/workflowAI';
import { ProxyMessageView } from './ProxyMessageView';
import { cleanMessageContent } from './utils';

type Props = {
  input: TaskInputDict;
  output: TaskOutputDict;
  toolCalls: ToolCallPreview[] | undefined;
  updateInputAndRun: (input: TaskInputDict) => Promise<void>;
  runId?: string;
};

export function ProxyReplyView(props: Props) {
  const { input, output, toolCalls, updateInputAndRun } = props;
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

  const supportToolCallResult = useMemo(() => {
    return !!toolCallRequest;
  }, [toolCallRequest]);

  const blankMessage: ProxyMessage = useMemo(() => {
    if (supportToolCallResult) {
      return {
        role: 'user',
        content: [
          {
            tool_call_result: {
              id: toolCallRequest?.id ?? nanoid(),
              result: 'Result of the tool call',
              tool_name: toolCallRequest?.tool_name ?? 'tool_name',
              tool_input_dict: toolCallRequest?.tool_input_dict,
            },
          },
        ],
      };
    }

    return {
      role: 'user',
      content: [
        {
          text: '',
        },
      ],
    };
  }, [supportToolCallResult, toolCallRequest]);

  const assistantMessage: ProxyMessage = useMemo(() => {
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

    return {
      role: 'assistant',
      content: requestContent,
    };
  }, [toolCallRequest, output]);

  const [newMessage, setNewMessage] = useState<ProxyMessage>(blankMessage);

  const onSendMessage = useCallback(async () => {
    const taskInput = input as Record<string, unknown>;
    const oldMessages: ProxyMessage[] = (taskInput['workflowai.replies'] as ProxyMessage[]) ?? [];

    const messages = [...oldMessages];

    messages.push(assistantMessage);
    messages.push(newMessage);

    const updatedInput: TaskInputDict = { ...input, ['workflowai.replies']: messages };

    setIsLoading(true);
    await updateInputAndRun(updatedInput);
    setIsLoading(false);
  }, [input, updateInputAndRun, newMessage, assistantMessage]);

  const handleSetMessage = useCallback(
    (message: ProxyMessage | undefined) => {
      if (!message || message.content.length === 0) {
        setNewMessage(blankMessage);
        return;
      }

      setNewMessage({
        ...message,
        content: cleanMessageContent(message.content),
      });
    },
    [blankMessage]
  );

  return (
    <div className='flex flex-col w-full px-4 py-2 gap-2.5'>
      <ProxyMessageView
        message={newMessage}
        avaibleTypes={supportToolCallResult ? ['toolCallResult', 'user'] : ['user']}
        setMessage={handleSetMessage}
        oneMessageMode={true}
        previouseMessage={assistantMessage}
      />
      <div className='flex flex-row w-full justify-between items-center'>
        <div className='flex flex-row gap-2 items-center'>
          <Button variant='newDesign' size='sm' onClick={onSendMessage} loading={isLoading}>
            Send
          </Button>
        </div>
        <div className='text-[12px] text-gray-500'>Will be sent to all models</div>
      </div>
    </div>
  );
}
