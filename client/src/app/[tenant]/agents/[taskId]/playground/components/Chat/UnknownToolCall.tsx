import { EditSchemaToolCall, ImprovePromptToolCall } from '@/types/workflowAI/models';

type UnknownToolCallProps = {
  toolCall: ImprovePromptToolCall | EditSchemaToolCall;
};

export function UnknownToolCall(props: UnknownToolCallProps) {
  const { toolCall } = props;

  return (
    <div className='flex flex-col bg-gray-50 border border-gray-200 rounded-[4px] px-2 py-2'>
      <div className='text-[13px] text-gray-900 font-medium pb-2'>{toolCall.tool_name}</div>
      <div className='flex w-full text-sm text-gray-500 bg-white border border-gray-200 rounded-[2px] overflow-y-auto py-2 px-2 whitespace-break-spaces'>
        <pre className='whitespace-pre-wrap text-[11px]'>{JSON.stringify(toolCall, null, 2)}</pre>
      </div>
    </div>
  );
}
