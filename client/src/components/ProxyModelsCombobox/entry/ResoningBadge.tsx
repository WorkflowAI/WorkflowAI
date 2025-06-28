import { BrainCircuitRegular, SportHockeyRegular } from '@fluentui/react-icons';
import { useMemo } from 'react';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { formatNumber } from '@/lib/formatters/numberFormatters';
import { ReasoningValue } from '../utils';

function formatReasoning(value: ReasoningValue) {
  if (typeof value === 'number') {
    return formatNumber(value);
  }
  return value;
}

type Props = {
  reasoning: string | undefined;
  allowTooltips?: boolean;
};

export function ResoningBadge(props: Props) {
  const { reasoning, allowTooltips = true } = props;

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

  if (!allowTooltips) {
    return (
      <div className='flex flex-row h-6 gap-1 items-center p-1 bg-gray-100/50 text-gray-500 rounded-[2px] border border-gray-200 text-[13px] capitalize'>
        {formatReasoning(value)}
        {isToken ? (
          <SportHockeyRegular className='text-gray-500 w-4 h-4' />
        ) : (
          <BrainCircuitRegular className='text-gray-500 w-4 h-4' />
        )}
      </div>
    );
  }

  return (
    <SimpleTooltip content={isToken ? 'Thinking token budger' : 'Reasoning effort'} tooltipDelay={0}>
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
