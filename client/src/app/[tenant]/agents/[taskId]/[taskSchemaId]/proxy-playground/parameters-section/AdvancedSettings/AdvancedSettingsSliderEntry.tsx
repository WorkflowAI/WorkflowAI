import { QuestionCircle16Regular } from '@fluentui/react-icons';
import { useCallback } from 'react';
import { Slider } from '@/components/ui/Slider';
import { Switch } from '@/components/ui/Switch';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { cn } from '@/lib/utils';
import { parseValidNumber } from '../../utils';

type Props = {
  name: string;
  prompt: string;
  minValue: number;
  maxValue: number;
  textWidth?: number;
  step: number;
  value: string | undefined;
  setValue: (value: string | undefined) => void;
  defaultValue: string | undefined;
  allowGoingAboveMaxValue?: boolean;
  isOptional: boolean;
  className?: string;
};

function formatValue(value: string | undefined, step: number): string | undefined {
  if (value === undefined) return undefined;
  const num = Number(value);
  if (isNaN(num)) return value;

  // Count decimal places in step
  const stepDecimals = step.toString().split('.')[1]?.length || 0;
  return num.toFixed(stepDecimals);
}

export function AdvancedSettingsSliderEntry(props: Props) {
  const {
    name,
    prompt,
    minValue,
    maxValue,
    textWidth,
    step,
    value,
    setValue,
    defaultValue,
    isOptional,
    className,
    allowGoingAboveMaxValue = false,
  } = props;

  const valueToUse = value ?? defaultValue;
  const midValue = Math.floor((minValue + maxValue) / 2);

  const onSetValue = useCallback(
    (value: string | undefined) => {
      const formattedValue = formatValue(value, step);
      const formattedDefaultValue = formatValue(defaultValue, step);
      if (formattedValue === formattedDefaultValue) {
        setValue(undefined);
        return;
      }
      setValue(formattedValue);
    },
    [setValue, defaultValue, step]
  );

  const onUpdateValue = useCallback(
    (value: string | undefined) => {
      if (value === undefined || value === '') {
        onSetValue(undefined);
        return;
      }

      const num = Number(value);
      if (isNaN(num)) {
        onSetValue(undefined);
        return;
      }

      if (num < minValue) {
        onSetValue(String(minValue));
        return;
      }

      if (allowGoingAboveMaxValue) {
        onSetValue(value);
      } else {
        if (num > maxValue) {
          onSetValue(String(maxValue));
        } else {
          onSetValue(value);
        }
      }
    },
    [allowGoingAboveMaxValue, onSetValue, maxValue, minValue]
  );

  return (
    <div className={cn('flex flex-col gap-2 py-3 px-4', className)}>
      <div className='flex flex-row gap-2 items-center justify-between'>
        <div className='flex flex-row gap-1.5 items-center'>
          <div className='text-gray-700 text-[13px] font-medium'>{name}</div>
          <SimpleTooltip content={prompt} tooltipClassName='w-[320px] text-center' tooltipDelay={100}>
            <QuestionCircle16Regular className='w-4 h-4 text-gray-500' />
          </SimpleTooltip>
        </div>
        <div className='flex flex-row gap-2.5 items-center'>
          {(!isOptional || valueToUse !== undefined) && (
            <input
              type='number'
              data-1p-ignore
              autoFocus={false}
              tabIndex={-1}
              className='text-gray-900 text-right rounded-[2px] text-[13px] placeholder:text-gray-400 py-0.5 px-1 border border-gray-300 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none focus:outline-none focus:ring-0'
              style={{ width: textWidth ? `${textWidth}px` : '50px' }}
              value={formatValue(valueToUse, step)}
              onChange={(e) => onUpdateValue(e.target.value)}
              placeholder='0.0'
              step={step}
            />
          )}

          {isOptional && (
            <Switch
              checked={valueToUse !== undefined}
              onCheckedChange={() => onUpdateValue(valueToUse === undefined ? String(midValue) : undefined)}
            />
          )}
        </div>
      </div>
      {valueToUse !== undefined && (
        <Slider
          min={minValue}
          max={maxValue}
          value={[parseValidNumber(valueToUse) ?? 0]}
          onValueChange={(value) => onUpdateValue(String(value[0]))}
          step={step}
          rangeColor='bg-gray-700'
          thumbBorderColor='border-gray-700 border-2'
          thumbSize='h-3 w-3'
        />
      )}
    </div>
  );
}
