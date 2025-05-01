import { Dismiss12Regular } from '@fluentui/react-icons';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

type Props = {
  showButtons: boolean;
  onClose: (() => void) | undefined;
};

export function PlaygroundTabHeader(props: Props) {
  const { showButtons, onClose } = props;

  return (
    <div className='flex flex-row w-full items-center h-[48px] bg-gray-100 border-b border-gray-200 justify-between'>
      <div></div>
      <div className={cn('flex flex-row gap-2 items-center px-4', showButtons ? 'opacity-100' : 'opacity-0')}>
        {onClose && (
          <Button
            onClick={onClose}
            variant='newDesign'
            icon={<Dismiss12Regular className='w-3 h-3' />}
            className='w-7 h-7'
            size='none'
          />
        )}
      </div>
    </div>
  );
}
