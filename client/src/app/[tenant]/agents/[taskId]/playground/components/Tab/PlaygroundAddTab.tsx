import { Add12Regular } from '@fluentui/react-icons';
import { Button } from '@/components/ui/Button';

type Props = {
  onAddTab: () => void;
};

export function PlaygroundAddTab(props: Props) {
  const { onAddTab } = props;

  return (
    <div className='flex items-center justify-center h-full w-[calc(100%-500px)] min-w-[220px]'>
      <Button
        variant='newDesignGray'
        icon={<Add12Regular className='w-[14px] h-[14px]' />}
        size='sm'
        onClick={onAddTab}
      >
        Add Version
      </Button>
    </div>
  );
}
