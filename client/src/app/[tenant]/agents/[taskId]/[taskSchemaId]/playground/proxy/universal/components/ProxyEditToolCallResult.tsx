import { Dismiss12Regular } from '@fluentui/react-icons';
import { nanoid } from 'nanoid';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { ProxyToolCallResult } from '@/types/workflowAI';
import { formatResponseToText, formatTextToResponse } from '../../utils';

type Props = {
  result: ProxyToolCallResult | undefined;
  setResult: (result: ProxyToolCallResult | undefined) => void;
  onClose: () => void;
};

export function ProxyEditToolCallResult(props: Props) {
  const { result, setResult, onClose } = props;

  const resultToolCallId = result?.id;

  const resultText = useMemo(() => formatResponseToText(result?.result), [result]);
  const [text, setText] = useState<string | undefined>(resultText);
  const [toolCallId, setToolCallId] = useState<string | undefined>(resultToolCallId);

  const areThereChanges = useMemo(
    () => toolCallId !== resultToolCallId || text !== resultText,
    [toolCallId, text, resultToolCallId, resultText]
  );

  const onSave = () => {
    setResult({
      ...result,
      id: toolCallId || nanoid(),
      result: formatTextToResponse(text),
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
          Tool Call Result
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
          <div className='text-gray-700 text-[13px] font-medium'>Result</div>
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
