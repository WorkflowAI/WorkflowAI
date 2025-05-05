import { Switch } from '@/components/ui/Switch';

type ToolboxMenuHeaderProps = {
  name: string;
  text: string;
  isOn: boolean;
  onSelect: () => void;
};

export function ToolboxMenuHeader(props: ToolboxMenuHeaderProps) {
  const { name, text, isOn, onSelect } = props;

  return (
    <div className='flex flex-col gap-1 w-full px-4 py-4'>
      <div className='font-medium text-[16px] text-gray-900'>{name}</div>
      <div className='flex flex-row gap-3 w-full justify-between items-start'>
        <div className='font-normal text-[13px] text-gray-700'>{text}</div>
        <Switch checked={isOn} onCheckedChange={onSelect} />
      </div>
    </div>
  );
}
