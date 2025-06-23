import { BrainCircuitRegular, SportHockeyRegular } from '@fluentui/react-icons';
import { useCallback, useMemo, useState } from 'react';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { formatNumber } from '@/lib/formatters/numberFormatters';
import { ModelResponse } from '@/types/workflowAI';
import { ReasoningValue } from '../utils';
import { ResoningSelectorPopoverContent } from './ResoningSelectorPopoverContent';

function formatReasoning(value: ReasoningValue) {
  if (typeof value === 'number') {
    return formatNumber(value);
  }
  return value;
}

type Props = {
  reasoning: string | undefined;
  onReasoningChange: (reasoning: string | undefined) => void;
  model: ModelResponse;
};

export function ResoningSelector(props: Props) {
  const { reasoning, onReasoningChange, model } = props;

  const maxTokens = useMemo(() => {
    return model.metadata.context_window_tokens;
  }, [model]);

  const value: ReasoningValue = useMemo(() => {
    if (reasoning === undefined) {
      return 'medium';
    }

    switch (reasoning) {
      case 'low':
        return 'low';
      case 'medium':
        return 'medium';
      case 'high':
        return 'high';
      case 'disabled':
        return 'disabled';
      default:
        const number = Number(reasoning);
        if (isNaN(number)) {
          return 'medium';
        }
        return number;
    }
  }, [reasoning]);

  const isToken = useMemo(() => {
    return typeof value === 'number';
  }, [value]);

  const [temporaryValue, setTemporaryValue] = useState<ReasoningValue | undefined>(undefined);

  const onOpenChange = useCallback(
    (open: boolean) => {
      if (!open && temporaryValue !== value && temporaryValue !== undefined) {
        onReasoningChange(temporaryValue.toString());
        setTemporaryValue(undefined);
      }
    },
    [onReasoningChange, temporaryValue, value]
  );

  return (
    <SimpleTooltip
      content={
        <ResoningSelectorPopoverContent
          reasoningValue={temporaryValue ?? value}
          onReasoningValueChange={setTemporaryValue}
          maxTokens={maxTokens}
        />
      }
      side='bottom'
      tooltipDelay={0}
      tooltipClassName='bg-white border border-gray-300 rounded-[2px] shadow-sm px-4 py-3'
      onOpenChange={onOpenChange}
    >
      <div className='flex flex-row h-6 gap-1 items-center p-1 bg-gray-100/50 text-gray-500 rounded-[2px] border border-gray-200 text-[13px] capitalize'>
        {formatReasoning(value)}
        {isToken ? (
          <SportHockeyRegular className='text-gray-500 w-4 h-4' />
        ) : (
          <BrainCircuitRegular className='text-gray-500 w-4 h-4' />
        )}
      </div>
    </SimpleTooltip>
  );
}
