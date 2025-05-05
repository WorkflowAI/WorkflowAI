import { formatFractionalCurrency, formatFractionalCurrencyAsNumber } from '@/lib/formatters/numberFormatters';
import { TaskRun } from '@/types/task_run';
import { ModelResponse } from '@/types/workflowAI';
import { BaseOutputValueRow, TBaseOutputValueRowVariant } from './BaseOutputValueRow';

function getScaleDisplayValue(value: number, minimumValue: number) {
  return `${Math.floor((10 * value) / minimumValue) / 10}x`;
}

type HoverTextProps = {
  currentAIModel: ModelResponse | undefined;
  minimumCostAIModel: ModelResponse | undefined;
  taskRun?: TaskRun;
  minimumCostTaskRun?: TaskRun;
};
function PriceOutputNote(props: HoverTextProps) {
  const { currentAIModel, minimumCostAIModel, taskRun, minimumCostTaskRun } = props;
  const value = formatFractionalCurrencyAsNumber(taskRun?.cost_usd);
  const minimumValue = formatFractionalCurrencyAsNumber(minimumCostTaskRun?.cost_usd);

  if (typeof value !== 'number' || typeof minimumValue !== 'number') {
    return <></>;
  }
  if (!currentAIModel || !minimumCostAIModel) {
    return <></>;
  }

  const scale = getScaleDisplayValue(value, minimumValue);
  return (
    <>
      It is {scale} more expensive to run this AI agent on {currentAIModel.name} than {minimumCostAIModel.name}
    </>
  );
}

type PriceOutputValueRowProps = {
  currentAIModel: ModelResponse | undefined;
  minimumCostAIModel: ModelResponse | undefined;
  taskRun: TaskRun | undefined;
  minimumCostTaskRun: TaskRun | undefined;
  hideLabel?: boolean;
};
export function PriceOutputValueRow(props: PriceOutputValueRowProps) {
  const { minimumCostTaskRun, taskRun, currentAIModel, minimumCostAIModel, hideLabel = false } = props;

  const value = taskRun?.cost_usd;
  const minimumValue = minimumCostTaskRun?.cost_usd;

  let variant: TBaseOutputValueRowVariant = 'default';
  let noteContent: React.ReactNode = null;
  let noteTitle: React.ReactNode = null;

  if (typeof value !== 'number') {
    variant = 'empty';
  } else if (typeof minimumValue !== 'number') {
    variant = 'default';
  } else {
    const formattedValueText = formatFractionalCurrency(value);
    const formattedMinimumValueText = formatFractionalCurrency(minimumValue);

    if (formattedMinimumValueText === formattedValueText) {
      variant = 'bestValue';
    } else {
      const formattedValueNumber = formatFractionalCurrencyAsNumber(value) ?? value;
      const formattedMinimumValueNumber = formatFractionalCurrencyAsNumber(minimumValue) ?? minimumValue;

      noteContent = getScaleDisplayValue(formattedValueNumber, formattedMinimumValueNumber);
      noteTitle = (
        <PriceOutputNote
          currentAIModel={currentAIModel}
          minimumCostAIModel={minimumCostAIModel}
          taskRun={taskRun}
          minimumCostTaskRun={minimumCostTaskRun}
        />
      );
    }
  }

  return (
    <BaseOutputValueRow
      label={hideLabel ? undefined : 'Price'}
      variant={variant}
      noteContent={noteContent}
      noteTitle={noteTitle}
      value={formatFractionalCurrency(value) ?? '-'}
    />
  );
}
