import { QuestionCircle16Regular } from '@fluentui/react-icons';
import { Textarea } from '@/components/ui/Textarea';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { cn } from '@/lib/utils';

type Props = {
  name: string;
  prompt: string;
  value: string | undefined;
  setValue: (value: string | undefined) => void;
  className?: string;
};

export function AdvancedSettingsTextEntry(props: Props) {
  const { name, prompt, value, setValue, className } = props;

  return (
    <div className={cn('flex flex-col gap-1 py-3 px-4', className)}>
      <div className='flex flex-row gap-1.5 items-center'>
        <div className='text-gray-700 text-[13px] font-medium'>{name}</div>
        <SimpleTooltip content={prompt} tooltipClassName='w-[320px] text-center' tooltipDelay={100}>
          <QuestionCircle16Regular className='w-4 h-4 text-gray-500' />
        </SimpleTooltip>
      </div>
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value === '' ? undefined : e.target.value)}
        placeholder='Optional'
        className='text-gray-900 border-gray-300 font-lato text-[13px] placeholder:text-gray-400 py-2'
        autoFocus={false}
      />
    </div>
  );
}
