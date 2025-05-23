import { Subtract16Filled } from '@fluentui/react-icons';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';

type Props = {
  isRemovable: boolean;
  className?: string;
  onRemove: () => void;
  children: React.ReactNode;
};

export function ProxyRemovableContent(props: Props) {
  const { isRemovable, children, onRemove, className } = props;

  const [isHovering, setIsHovering] = useState(false);

  return (
    <div
      className={cn('flex max-w-full relative', className)}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {children}
      {isHovering && isRemovable && (
        <Button
          variant='destructive'
          size='none'
          icon={<Subtract16Filled />}
          onClick={onRemove}
          className='absolute w-6 h-6 -right-2 -top-1.5 rounded-full'
        />
      )}
    </div>
  );
}
