import { cn } from '@/lib/utils';
import { ToolboxTab } from './ToolboxTab';

type ToolboxModalTabProps = {
  tab: ToolboxTab;
  isSelected: boolean;
  isOn: boolean;
  onSelect: () => void;
};

export function ToolboxModalTab(props: ToolboxModalTabProps) {
  const { tab, isSelected, isOn, onSelect } = props;

  return (
    <div
      className={cn(
        'flex flex-row items-center justify-between gap-2 pr-2 py-[6px] hover:bg-indigo-50 cursor-pointer transition-colors duration-200 ease-in-out',
        {
          'bg-indigo-100/70 border-l-2 border-indigo-700 pl-[6px]': isSelected,
          'pl-2': !isSelected,
        }
      )}
      onClick={onSelect}
    >
      <div className='flex flex-row items-center gap-2'>
        {isSelected ? tab.iconOn : tab.iconOff}
        <div
          className={cn('text-[13px]', {
            'text-indigo-700 font-semibold': isSelected,
            'text-gray-700 font-medium': !isSelected,
          })}
        >
          {tab.name}
        </div>
      </div>
      {isOn && (
        <div
          className={cn('text-[12px]', {
            'text-indigo-700 font-semibold': isSelected,
            'text-gray-700 font-medium': !isSelected,
          })}
        >
          On
        </div>
      )}
    </div>
  );
}
