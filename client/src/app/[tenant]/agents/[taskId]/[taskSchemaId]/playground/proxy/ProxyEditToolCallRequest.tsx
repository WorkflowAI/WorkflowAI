import { Dismiss12Regular } from '@fluentui/react-icons';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { ToolCallRequestWithID } from '@/types/workflowAI/models';

type Props = {
  request: ToolCallRequestWithID | undefined;
  setRequest: (request: ToolCallRequestWithID | undefined) => void;
  onClose: () => void;
};

export function ProxyEditToolCallRequest(props: Props) {
  const { request, setRequest, onClose } = props;

  const requestText = useMemo(() => {
    try {
      return JSON.stringify(request?.tool_input_dict, null, 2);
    } catch {
      return '';
    }
  }, [request]);

  const requestToolName = request?.tool_name;
  const requestToolCallId = request?.id;

  const [text, setText] = useState<string | undefined>(requestText);
  const [toolName, setToolName] = useState<string | undefined>(requestToolName);
  const [toolCallId, setToolCallId] = useState<string | undefined>(requestToolCallId);

  const areThereChanges = useMemo(
    () => toolName !== requestToolName || toolCallId !== requestToolCallId || text !== requestText,
    [toolName, toolCallId, text, requestToolName, requestToolCallId, requestText]
  );

  const onSave = () => {
    let tool_input_dict: Record<string, unknown>;
    try {
      tool_input_dict = JSON.parse(text || '{}');
    } catch {
      tool_input_dict = { value: text || '' };
    }

    setRequest({
      ...request,
      tool_name: toolName || 'tool_name',
      id: toolCallId || 'tool_call_id',
      tool_input_dict: tool_input_dict,
    });
    onClose();
  };

  return (
    <div className='flex flex-col h-full w-full'>
      <div className='flex items-center px-4 justify-between h-[52px] flex-shrink-0 border-b border-gray-200 border-dashed'>
        <div className='flex items-center gap-4 text-gray-900 text-[16px] font-semibold'>
          <Button
            onClick={onClose}
            variant='newDesign'
            icon={<Dismiss12Regular className='w-3 h-3' />}
            className='w-7 h-7'
            size='none'
          />
          Tool Call Request
        </div>
        <Button onClick={onSave} variant='newDesign' size='sm' disabled={!areThereChanges}>
          Save
        </Button>
      </div>
      <div className='flex flex-col w-full flex-1 p-4 gap-4'>
        <div className='flex flex-col w-full h-full gap-1'>
          <div className='text-gray-700 text-[13px] font-medium'>Tool Call ID</div>
          <Textarea
            className='flex text-gray-700 placeholder:text-gray-500 font-normal text-[13px] rounded-[2px] border-gray-300 overflow-y-auto focus-within:ring-inset bg-white whitespace-pre-wrap font-mono overflow-auto'
            value={toolCallId}
            onChange={(e) => setToolCallId(e.target.value)}
          />
        </div>

        <div className='flex flex-col w-full h-full gap-1'>
          <div className='text-gray-700 text-[13px] font-medium'>Tool Name</div>
          <Textarea
            className='flex text-gray-700 placeholder:text-gray-500 font-normal text-[13px] rounded-[2px] border-gray-300 overflow-y-auto focus-within:ring-inset bg-white whitespace-pre-wrap font-mono overflow-auto'
            value={toolName}
            onChange={(e) => setToolName(e.target.value)}
          />
        </div>

        <div className='flex flex-col w-full h-full gap-1'>
          <div className='text-gray-700 text-[13px] font-medium'>Input Dict</div>
          <Textarea
            className='flex flex-1 text-gray-700 placeholder:text-gray-500 font-normal text-[13px] rounded-[2px] border-gray-300 overflow-y-auto focus-within:ring-inset bg-white whitespace-pre-wrap font-mono overflow-auto'
            style={{ minHeight: 300 }}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
