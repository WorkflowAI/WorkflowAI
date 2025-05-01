import { VariantProps, cva } from 'class-variance-authority';
import { ArrowUp } from 'lucide-react';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { cn } from '@/lib/utils';

const valueVariant = cva('text-xs rounded-[2px] font-semibold font-lato', {
  variants: {
    variant: {
      default: 'text-gray-500',
      empty: 'text-gray-500',
      bestValue: 'bg-green-200 text-green-900 px-1.5 py-1',
      badge: 'bg-gray-200 text-gray-700 px-1.5 py-1',
    },
  },
  defaultVariants: {
    variant: 'default',
  },
});

export type TBaseOutputValueRowVariant = VariantProps<typeof valueVariant>['variant'];

type BaseOutputValueRowProps = VariantProps<typeof valueVariant> & {
  label: string | undefined;
  value: React.ReactNode;
  noteContent?: React.ReactNode;
  noteTitle?: React.ReactNode;
};
export function BaseOutputValueRow(props: BaseOutputValueRowProps) {
  const { label, value, variant, noteTitle, noteContent } = props;
  const valueClassName = valueVariant({ variant });

  const renderNote = () => {
    if (!noteContent) {
      return null;
    }

    let tooltip = null;
    if (noteTitle) {
      tooltip = <div className='block max-w-[186px]'>{noteTitle}</div>;
    }

    return (
      <SimpleTooltip content={tooltip} align='center' supportClick={true}>
        <span className='flex flex-row gap-x-0.5 items-center text-xs font-medium text-red-500'>
          {noteContent}
          <ArrowUp size={12} />
        </span>
      </SimpleTooltip>
    );
  };

  return (
    <div className={cn('flex flex-row justify-between h-full w-full items-center', label ? 'px-4' : 'px-2')}>
      {label && (
        <div data-testid='label' className='text-gray-500 text-[13px] font-normal'>
          {label}
        </div>
      )}
      <div className='flex flex-row items-center'>
        {renderNote()}
        <div data-testid='value' className={valueClassName}>
          {value}
        </div>
      </div>
    </div>
  );
}
