import isEmpty from 'lodash/isEmpty';
import { TaskOutput, ToolCallPreview } from '@/types';
import { ReasoningStep } from '@/types/workflowAI';
import { InternalReasoningSteps } from './InternalReasoningSteps';
import { ObjectViewer, ObjectViewerProps } from './ObjectViewer';

const OBJECT_VIEWER_BLACKLISTED_KEYS = new Set(['internal_reasoning_steps']);

type TaskOutputViewerProps = Omit<ObjectViewerProps, 'blacklistedKeys' | 'value'> & {
  value: TaskOutput | null | undefined;
  streamLoading?: boolean;
  toolCalls?: Array<ToolCallPreview>;
  reasoningSteps?: ReasoningStep[];
  defaultOpenForSteps?: boolean;
};

export function ObjectViewerPrefixSlot(props: {
  toolCalls: Array<ToolCallPreview> | undefined;
  reasoningSteps: ReasoningStep[] | undefined;
  streamLoading: boolean | undefined;
  defaultOpenForSteps?: boolean;
}) {
  const { streamLoading, toolCalls, reasoningSteps, defaultOpenForSteps } = props;

  if (isEmpty(reasoningSteps) && isEmpty(toolCalls)) {
    return null;
  }

  return (
    <InternalReasoningSteps
      steps={reasoningSteps}
      streamLoading={streamLoading}
      toolCalls={toolCalls}
      defaultOpen={defaultOpenForSteps}
    />
  );
}

export function TaskOutputViewer(props: TaskOutputViewerProps) {
  const { streamLoading, value, toolCalls: toolCallsPreview, reasoningSteps, defaultOpenForSteps, ...rest } = props;

  return (
    <ObjectViewer
      blacklistedKeys={OBJECT_VIEWER_BLACKLISTED_KEYS}
      prefixSlot={
        <ObjectViewerPrefixSlot
          streamLoading={streamLoading}
          toolCalls={toolCallsPreview}
          reasoningSteps={reasoningSteps}
          defaultOpenForSteps={defaultOpenForSteps}
        />
      }
      value={value}
      {...rest}
    />
  );
}
