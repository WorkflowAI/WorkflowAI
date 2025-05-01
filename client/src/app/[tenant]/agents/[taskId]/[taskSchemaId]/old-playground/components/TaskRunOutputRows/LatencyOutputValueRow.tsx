import { TaskRun } from '@/types/task_run';
import { ModelResponse } from '@/types/workflowAI';
import { BaseOutputValueRow, TBaseOutputValueRowVariant } from './BaseOutputValueRow';

type LatencyOutputValueRowProps = {
  currentAIModel: ModelResponse | undefined;
  minimumCostAIModel: ModelResponse | undefined;
  taskRun: TaskRun | undefined;
  minimumLatencyTaskRun: TaskRun | undefined;
  hideLabel?: boolean;
};
export function LatencyOutputValueRow({
  currentAIModel,
  minimumCostAIModel,
  minimumLatencyTaskRun,
  taskRun,
  hideLabel = false,
}: LatencyOutputValueRowProps) {
  const value = taskRun?.duration_seconds;
  const minimumValue = minimumLatencyTaskRun?.duration_seconds;

  let displayValue = '-';
  if (typeof value === 'number') {
    displayValue = `${value.toFixed(1)}s`;
  }

  let variant: TBaseOutputValueRowVariant = 'default';
  let noteContent: React.ReactNode = null;
  let noteTitle: React.ReactNode = null;

  if (typeof value !== 'number') {
    variant = 'empty';
  } else if (typeof minimumValue !== 'number') {
    variant = 'default';
  } else {
    const formattedValue = `${minimumValue.toFixed(1)}s`;
    if (displayValue === formattedValue) {
      variant = 'bestValue';
    } else {
      const scale = Math.floor((10 * value) / minimumValue) / 10;
      noteContent = `${scale}x`;
      if (currentAIModel && minimumCostAIModel) {
        noteTitle = `It is ${scale}x slower to run this AI agent on ${currentAIModel.name} than ${minimumCostAIModel.name}`;
      }
    }
  }

  return (
    <BaseOutputValueRow
      label={hideLabel ? undefined : 'Latency'}
      variant={variant}
      noteContent={noteContent}
      noteTitle={noteTitle}
      value={displayValue}
    />
  );
}
