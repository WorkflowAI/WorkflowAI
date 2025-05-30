import { cx } from 'class-variance-authority';
import Image from 'next/image';
import { AIProviderIcon } from '@/components/icons/models/AIProviderIcon';
import { Badge } from '@/components/ui/Badge';

type TaskModelBadgeProps = {
  model: string | null | undefined;
  providerId?: string | null | undefined;
  modelIcon?: string | null | undefined;
  className?: string;
};

export function TaskModelBadge(props: TaskModelBadgeProps) {
  const { model, providerId, modelIcon, className } = props;

  if (!model) {
    return null;
  }

  return (
    <Badge variant='tertiary' className={cx('truncate flex items-center gap-1.5 max-w-[300px]', className)}>
      {!!modelIcon ? (
        <Image src={modelIcon} alt='model icon' className='w-3 h-3' width={12} height={12} />
      ) : providerId ? (
        <AIProviderIcon providerId={providerId} fallbackOnMysteryIcon sizeClassName='w-3 h-3' />
      ) : null}
      {model && <div className='truncate'>{model}</div>}
    </Badge>
  );
}
