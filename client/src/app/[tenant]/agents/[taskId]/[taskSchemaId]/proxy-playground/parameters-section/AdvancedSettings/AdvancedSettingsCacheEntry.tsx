import { QuestionCircle16Regular } from '@fluentui/react-icons';
import { useCallback } from 'react';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { cn } from '@/lib/utils';

type OptionSelectorItemProps = {
  name: string;
  isSelected: boolean;
  onClick: () => void;
};

function OptionSelectorItem(props: OptionSelectorItemProps) {
  const { name, isSelected, onClick } = props;

  return (
    <div
      className={cn(
        'flex items-center justify-center rounded-[2px] h-5.5 px-2 cursor-pointer text-gray-500 hover:text-gray-900 text-[13px] capitalize',
        isSelected && 'bg-white border border-gray-300 shadow-sm text-gray-900'
      )}
      onClick={onClick}
    >
      {name}
    </div>
  );
}

type Props = {
  name: string;
  prompt: string;
  value: string | undefined;
  setValue: (value: string | undefined) => void;
  defaultValue: string | undefined;
  className?: string;
};

export function AdvancedSettingsCacheEntry(props: Props) {
  const { name, prompt, value, setValue, className, defaultValue } = props;

  const options = ['auto', 'always', 'never'];
  const valueToUse = value ?? defaultValue;

  const onUpdateValue = useCallback(
    (value: string | undefined) => {
      if (value === defaultValue) {
        setValue(undefined);
        return;
      }

      setValue(value);
    },
    [setValue, defaultValue]
  );

  return (
    <div className={cn('flex flex-row justify-between items-center gap-1 py-3 px-4', className)}>
      <div className='flex flex-row gap-1.5 items-center'>
        <div className='text-gray-700 text-[13px] font-medium'>{name}</div>
        <SimpleTooltip content={prompt} tooltipClassName='w-[320px] text-center' tooltipDelay={100}>
          <QuestionCircle16Regular className='w-4 h-4 text-gray-500' />
        </SimpleTooltip>
      </div>
      <div className='flex flex-row h-7 items-center p-1 bg-gray-100/50 rounded-[2px] border border-gray-300'>
        {options.map((item) => (
          <OptionSelectorItem
            key={item}
            name={item}
            isSelected={item === valueToUse}
            onClick={() => onUpdateValue(item)}
          />
        ))}
      </div>
    </div>
  );
}
