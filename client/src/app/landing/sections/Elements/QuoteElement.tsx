import Image from 'next/image';
import { cn } from '@/lib/utils';
import { QuoteEntry } from '../StaticData/LandingStaticData';

type Props = {
  entry: QuoteEntry;
};

export function QuoteElement(props: Props) {
  const { entry } = props;

  return (
    <div className='flex flex-col sm:gap-8 gap-6 w-full flex-1 items-center justify-between'>
      <div
        className={cn(
          'flex w-fit items-center justify-center text-center text-gray-500 font-normal sm:text-[18px] text-[13px]',
          entry.quoteMaxWidth
        )}
      >
        {entry.quote}
      </div>
      <div className='flex flex-col gap-2 w-fit items-center'>
        <Image
          src={entry.authorImageSrc}
          alt='Person'
          key={entry.authorImageSrc}
          className='object-cover w-10 h-10 rounded-full'
          width={40}
          height={40}
        />
        <div className='flex flex-col w-full items-center pt-2'>
          <div
            className={cn(
              'flex w-full items-center justify-center text-center text-gray-700 font-semibold sm:text-[16px] text-[13px]',
              entry.quoteMaxWidth
            )}
          >
            {entry.quoteAuthor}
          </div>
          <div className='flex w-full items-center justify-center text-center text-gray-500 font-normal sm:text-[16px] text-[13px]'>
            {entry.authorsPosition} at
            <a href={entry.companyURL} className='underline ml-1' target='_blank'>
              {entry.authorsCompany}
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
