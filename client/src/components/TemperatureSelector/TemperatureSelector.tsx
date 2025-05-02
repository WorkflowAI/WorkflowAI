import { Settings20Filled, Settings20Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useEffect, useState } from 'react';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { TemperatureSliderSelector } from './TemperatureSliderSelector';

const TEMPERATURE_OPTIONS = [
  {
    title: 'Precise',
    value: 0.0,
    tooltipText: `Accurate and focused responses,\nideal for factual tasks`,
  },
  {
    title: 'Balanced',
    value: 0.5,
    tooltipText: `Balanced responses with a blend\nof focus and creativity`,
  },
  {
    title: 'Creative',
    value: 1.0,
    tooltipText: `Creative and exploratory outputs,\nsuited for creative writing`,
  },
];

type TemperatureSelectorButtonProps = {
  title?: string;
  activeIcon?: React.ReactNode;
  inactiveIcon?: React.ReactNode;
  isSelected: boolean;
  onClick: () => void;
};

export function TemperatureSelectorButton(props: TemperatureSelectorButtonProps) {
  const { title, activeIcon, inactiveIcon, isSelected, onClick } = props;
  return (
    <div
      className={cx(
        'py-1 rounded-[2px] text-[13px] text-gray-500 cursor-pointer px-2 font-lato border hover:text-gray-800',
        isSelected && !!title ? 'bg-white border-gray-300 text-gray-800 shadow-sm' : 'border-transparent',
        isSelected && !title && 'text-gray-800'
      )}
      onClick={onClick}
    >
      {!!activeIcon && isSelected ? activeIcon : inactiveIcon}
      {!!title && title}
    </div>
  );
}

type TemperatureSelectorProps = {
  temperature: number;
  setTemperature: (temperature: number) => void;
  handleRunTasks?: () => void;
};

export function TemperatureSelector(props: TemperatureSelectorProps) {
  const { temperature, setTemperature, handleRunTasks } = props;
  const [showSettings, setShowSettings] = useState(false);

  const setTemperatureByButton = (value: number) => {
    setTemperature(value);
    setShowSettings(false);
    handleRunTasks?.();
  };

  useEffect(() => {
    if (TEMPERATURE_OPTIONS.some((option) => option.value === temperature)) {
      return;
    }
    setShowSettings(true);
  }, [temperature]);

  return (
    <div className='flex flex-col gap-1.5 w-fit'>
      <div className='flex flex-row p-1 rounded-[2px] border border-gray-300 items-center'>
        {TEMPERATURE_OPTIONS.map((option) => (
          <SimpleTooltip
            key={option.value}
            content={<div className='whitespace-break-spaces text-center'>{option.tooltipText}</div>}
          >
            <div>
              <TemperatureSelectorButton
                title={option.title}
                isSelected={temperature === option.value && !showSettings}
                onClick={() => setTemperatureByButton(option.value)}
              />
            </div>
          </SimpleTooltip>
        ))}
        <TemperatureSelectorButton
          activeIcon={<Settings20Filled className='w-5 h-5' />}
          inactiveIcon={<Settings20Regular className='w-5 h-5' />}
          isSelected={showSettings}
          onClick={() => setShowSettings(true)}
        />
      </div>
      {showSettings && <TemperatureSliderSelector {...props} />}
    </div>
  );
}
