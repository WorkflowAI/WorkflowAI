import { QuestionCircle16Regular } from '@fluentui/react-icons';
import { Switch } from '@/components/ui/Switch';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { cn } from '@/lib/utils';

type Props = {
  name: string;
  prompt: string;
  value: string | undefined;
  setValue: (value: string | undefined) => void;
  className?: string;
};

export function AdvancedSettingsSwitchEntry(props: Props) {
  const { name, prompt, value, setValue, className } = props;

  return (
    <div className={cn('flex flex-col py-3 px-4', className)}>
      <div className='flex flex-row gap-2 items-center justify-between'>
        <div className='flex flex-row gap-1.5 items-center'>
          <div className='text-gray-700 text-[13px] font-medium'>{name}</div>
          <SimpleTooltip content={prompt} tooltipClassName='w-[320px] text-center' tooltipDelay={100}>
            <QuestionCircle16Regular className='w-4 h-4 text-gray-500' />
          </SimpleTooltip>
        </div>
        <Switch checked={value === 'true'} onCheckedChange={() => setValue(value === 'true' ? undefined : 'true')} />
      </div>
    </div>
  );
}
