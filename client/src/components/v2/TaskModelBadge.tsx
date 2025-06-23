import { cx } from 'class-variance-authority';
import Image from 'next/image';
import { AIProviderIcon } from '@/components/icons/models/AIProviderIcon';
import { Badge } from '@/components/ui/Badge';
import { ResoningBadge } from '../ProxyModelsCombobox/entry/ResoningBadge';

type TaskModelBadgeProps = {
  model: string | null | undefined;
  providerId?: string | null | undefined;
  modelIcon?: string | null | undefined;
  reasoning?: string;
  allowTooltips?: boolean;
  className?: string;
};

export function TaskModelBadge(props: TaskModelBadgeProps) {
  const { model, providerId, modelIcon, reasoning, className, allowTooltips = true } = props;

  if (!model) {
    return null;
  }

  return (
    <div className='flex flex-row items-center gap-1 max-w-full'>
      <Badge variant='tertiary' className={cx('truncate flex items-center gap-1.5 py-0 max-w-[300px]', className)}>
        {!!modelIcon ? (
          <Image src={modelIcon} alt='model icon' className='w-3 h-3' width={12} height={12} />
        ) : providerId ? (
          <AIProviderIcon providerId={providerId} fallbackOnMysteryIcon sizeClassName='w-3 h-3' />
        ) : null}
        {model && <div className='truncate'>{model}</div>}
      </Badge>
      {reasoning && <ResoningBadge reasoning={reasoning} allowTooltips={allowTooltips} />}
    </div>
  );
}
