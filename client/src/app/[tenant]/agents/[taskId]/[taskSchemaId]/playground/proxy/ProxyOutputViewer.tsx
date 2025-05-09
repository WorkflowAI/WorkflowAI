import { useMemo } from 'react';
import { ObjectViewerPrefixSlot } from '@/components/ObjectViewer/TaskOutputViewer';
import { ToolCallPreview } from '@/types';
import { TaskOutput } from '@/types/task_run';
import { ReasoningStep } from '@/types/workflowAI';
import { formatResponseToText } from './utils';

type ProxyOutputViewerProps = {
  taskOutput: TaskOutput | undefined;
  toolCalls: ToolCallPreview[] | undefined;
  reasoningSteps: ReasoningStep[] | undefined;
  streamLoading: boolean;
};

export function ProxyOutputViewer(props: ProxyOutputViewerProps) {
  const { taskOutput, toolCalls, reasoningSteps, streamLoading } = props;

  const formattedText = useMemo(() => {
    return formatResponseToText(taskOutput);
  }, [taskOutput]);

  return (
    <div className='flex flex-col flex-1 w-full bg-white border-b border-gray-200 border-dashed overflow-hidden'>
      <ObjectViewerPrefixSlot
        streamLoading={streamLoading}
        toolCalls={toolCalls}
        reasoningSteps={reasoningSteps}
        defaultOpenForSteps={true}
      />
      <div className='flex flex-col flex-1 px-4 py-3 gap-1 overflow-hidden'>
        <div className='text-gray-700 text-[13px] font-medium'>assistant message:</div>
        {formattedText === undefined ? (
          <div className='flex py-0.5 px-1.5 border border-gray-200 rounded-[2px] text-gray-700 text-[13px] font-medium w-fit'>
            string
          </div>
        ) : (
          <div className='flex flex-col py-2 px-3 gap-2 border border-gray-200 rounded-[2px] min-h-[100px] overflow-y-auto'>
            <div className='text-gray-900 text-[13px] font-normal whitespace-pre-wrap'>{formattedText}</div>
          </div>
        )}
      </div>
    </div>
  );
}
