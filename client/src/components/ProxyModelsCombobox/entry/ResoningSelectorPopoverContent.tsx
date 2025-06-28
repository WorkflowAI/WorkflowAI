import { InfoRegular } from '@fluentui/react-icons';
import { useCallback } from 'react';
import { Slider } from '@/components/ui/Slider';
import { Switch } from '@/components/ui/Switch';
import { formatNumber } from '@/lib/formatters/numberFormatters';
import { cn } from '@/lib/utils';
import { ReasoningValue } from '../utils';

type ResoningSelectorItemProps = {
  name: string;
  isSelected: boolean;
  onClick: () => void;
};

function ResoningSelectorItem(props: ResoningSelectorItemProps) {
  const { name, isSelected, onClick } = props;

  return (
    <div
      className={cn(
        'flex items-center justify-center rounded-[2px] h-5.5 px-2 cursor-pointer text-gray-500 hover:text-gray-900 text-[13px]',
        isSelected && 'bg-white border border-gray-300 shadow-sm text-gray-900'
      )}
      onClick={onClick}
    >
      {name}
    </div>
  );
}

function isOptionSelected(option: 'Low' | 'Medium' | 'High' | '# Tokens', reasoningValue: ReasoningValue) {
  if (option === '# Tokens') {
    const number = Number(reasoningValue);
    return !isNaN(number);
  }
  if (option === 'Low' && reasoningValue === 'low') {
    return true;
  }
  if (option === 'Medium' && reasoningValue === 'medium') {
    return true;
  }
  if (option === 'High' && reasoningValue === 'high') {
    return true;
  }
  return false;
}

type Props = {
  reasoningValue: ReasoningValue;
  onReasoningValueChange: (reasoning: ReasoningValue) => void;
  maxTokens: number;
};

export function ResoningSelectorPopoverContent(props: Props) {
  const { reasoningValue, onReasoningValueChange, maxTokens } = props;

  const options: ('Low' | 'Medium' | 'High' | '# Tokens')[] = ['Low', 'Medium', 'High', '# Tokens'];

  const onChangeOption = useCallback(
    (option: string) => {
      switch (option) {
        case '# Tokens':
          onReasoningValueChange(maxTokens / 2);
          break;
        case 'Low':
          onReasoningValueChange('low');
          break;
        case 'Medium':
          onReasoningValueChange('medium');
          break;
        case 'High':
          onReasoningValueChange('high');
          break;
      }
    },
    [onReasoningValueChange, maxTokens]
  );

  return (
    <div className='flex flex-col gap-2' onClick={(e) => e.stopPropagation()}>
      <div className='flex flex-row gap-2 items-center justify-between'>
        <a
          className='flex flex-row gap-1 items-center'
          href='https://docs2.workflowai.com/inference/reasoning'
          target='_blank'
          rel='noopener noreferrer'
        >
          <div className='text-[13px] font-medium text-gray-900'>Reasoning</div>
          <InfoRegular className='text-gray-500 w-4 h-4' />
        </a>
        <Switch
          checked={reasoningValue !== 'disabled'}
          onCheckedChange={() => onReasoningValueChange(reasoningValue === 'disabled' ? 'medium' : 'disabled')}
        />
      </div>
      <div className='flex flex-row h-7 items-center px-1 py-2 bg-gray-100/50 rounded-[2px] border border-gray-300'>
        {options.map((item) => (
          <ResoningSelectorItem
            key={item}
            name={item}
            isSelected={isOptionSelected(item, reasoningValue)}
            onClick={() => onChangeOption(item)}
          />
        ))}
      </div>
      {isOptionSelected('# Tokens', reasoningValue) && (
        <div className='flex flex-row items-center justify-between py-1'>
          <Slider
            min={1}
            max={maxTokens}
            value={[Number(reasoningValue)]}
            onValueChange={(value) => onReasoningValueChange(String(value[0]) as ReasoningValue)}
            step={1}
            rangeColor='bg-gray-700'
            thumbBorderColor='border-gray-700 border-2'
            thumbSize='h-3 w-3'
          />
          <div className='text-[13px] font-medium text-gray-900 px-1 rounded-[2px] border border-gray-300 ml-3'>
            {formatNumber(Number(reasoningValue))}
          </div>
          <div className='text-[13px] text-gray-900 pl-1'>tokens</div>
        </div>
      )}
    </div>
  );
}
