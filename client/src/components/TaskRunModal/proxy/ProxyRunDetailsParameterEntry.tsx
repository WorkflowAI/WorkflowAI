import { cn } from '@/lib/utils';

type Props = {
  title: string;
  className?: string;
  children: React.ReactNode;
};

export function ProxyRunDetailsParameterEntry(props: Props) {
  const { title, children, className } = props;

  return (
    <div className={cn('flex w-full items-center justify-between h-10 px-4 flex-shrink-0', className)}>
      <div className='flex flex-col'>
        <div className='text-[13px] text-gray-500'>{title}</div>
      </div>
      <div>{children}</div>
    </div>
  );
}
