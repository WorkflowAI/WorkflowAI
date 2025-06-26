import { StreamOutputRegular } from '@fluentui/react-icons';
import { nanoid } from 'nanoid';
import { useMemo } from 'react';
import { Textarea } from '@/components/ui/Textarea';
import { ProxyMessageContent } from '@/types/workflowAI';
import { ProxyToolCallResult } from '@/types/workflowAI';
import { formatResponseToText, formatTextToResponse } from '../utils';

type Props = {
  result: ProxyToolCallResult;
  setContent: (content: ProxyMessageContent) => void;
};

export function ProxyToolCallResultInstantEditView(props: Props) {
  const { result, setContent } = props;

  const resultToolCallId = result?.id;
  const text = useMemo(() => formatResponseToText(result.result), [result.result]);

  const setText = (text: string) => {
    const toolCallResult = {
      ...result,
      id: resultToolCallId || nanoid(),
      result: formatTextToResponse(text) ?? '',
    };

    setContent({
      ...result,
      tool_call_result: toolCallResult,
    });
  };

  if (result.result === undefined || result.result === null) {
    return null;
  }

  return (
    <div className='flex flex-row w-full items-center justify-between relative'>
      <div className='flex flex-col'>
        <div className='flex items-center justify-between px-1'>
          <div className='flex items-center gap-2 text-gray-700 text-xsm'>
            <StreamOutputRegular className='w-4 h-4 text-gray-400' />
            Tool Call Result
          </div>
        </div>
        <div className='flex pl-6 pt-2 w-full'>
          <Textarea
            className='flex w-full flex-1 text-gray-700 placeholder:text-gray-500 border-l border-r-0 border-t-0 border-b-0 py-1 border-gray-200 font-normal text-[13px] overflow-y-auto focus-within:ring-inset  whitespace-pre-wrap overflow-auto'
            value={text ?? ''}
            placeholder='Result of the tool call'
            onChange={(e) => setText(e.target.value)}
            autoFocus={true}
          />
        </div>
      </div>
    </div>
  );
}
