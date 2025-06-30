import { cn } from '@/lib/utils';

export enum ColumnName {
  Version = 'Version',
  Model = 'Model',
  Price = 'Price',
  Avatar = 'Avatar',
  Temperature = 'Temperature',
  Runs = 'Runs',
}

export const COLUMN_WIDTHS = {
  [ColumnName.Version]: 'w-[80px]',
  [ColumnName.Model]: 'w-[200px]',
  // allow the price label to fit on one line without extra spacing
  [ColumnName.Price]: 'whitespace-nowrap w-fit',
  [ColumnName.Avatar]: 'w-[24px]',
  [ColumnName.Temperature]: 'w-[90px]',
  [ColumnName.Runs]: 'w-[45px]',
};

export const SMALL_COLUMN_WIDTHS = {
  [ColumnName.Version]: 'w-[60px]',
  // use a hugging width in small mode too
  [ColumnName.Price]: 'whitespace-nowrap w-fit',
};

type TaskVersionsHeaderProps = {
  smallMode: boolean;
};

export function TaskVersionsHeader(props: TaskVersionsHeaderProps) {
  const { smallMode } = props;

  if (smallMode) {
    return (
      <div className='px-2 py-2.5 flex items-center gap-4 w-full border-b border-gray-100 font-lato text-gray-900 text-[13px] font-medium'>
        <div className={cn('flex items-center', SMALL_COLUMN_WIDTHS[ColumnName.Version])}>Version</div>
        <div className='flex-1 items-center'>Model</div>
        <div className={cn('flex items-center', SMALL_COLUMN_WIDTHS[ColumnName.Price])}>Price (1k runs)</div>
      </div>
    );
  }

  return (
    <div className='px-2 py-2.5 flex items-center gap-4 w-full border-b border-gray-100 font-lato text-gray-900 text-[13px] font-medium'>
      <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Version])}>Version</div>
      <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Model])}>Model</div>
      <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Price])}>Price (1k runs)</div>
      <div className={COLUMN_WIDTHS[ColumnName.Avatar]} />
      <div className='flex-1 items-center'>Preview</div>
      <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Temperature])}>Temperature</div>
      <div className={cn('flex items-center', COLUMN_WIDTHS[ColumnName.Runs])}>Runs</div>
    </div>
  );
}
