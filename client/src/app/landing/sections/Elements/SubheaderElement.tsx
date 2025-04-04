import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';
import { HeaderEntry } from '../StaticData/LandingStaticData';

type Props = {
  entry: HeaderEntry;
};

export function SubheaderElement(props: Props) {
  const { entry } = props;

  return (
    <div className='flex flex-col gap-4 w-full items-center'>
      <div
        className={cn(
          'flex w-full items-center justify-center text-center text-gray-900 font-semibold sm:text-[30px] text-[24px]',
          entry.titleSizeClassName ?? 'sm:text-[30px] text-[24px]'
        )}
      >
        {entry.title}
      </div>
      {entry.description && (
        <div
          className={cn(
            'flex w-fit items-center justify-center text-center text-gray-500 font-normal sm:text-[20px] text-[16px] whitespace-pre-wrap',
            entry.descriptionMaxWidth
          )}
        >
          {entry.description}
        </div>
      )}
      {entry.buttonText && entry.url && (
        <Button variant='newDesignGray' toRoute={entry.url} openInNewTab={true}>
          {entry.buttonText}
        </Button>
      )}
    </div>
  );
}
