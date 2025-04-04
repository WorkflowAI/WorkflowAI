import Image from 'next/image';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';
import { FeatureEntry } from '../StaticData/LandingStaticData';

type FeatureCardProps = {
  entry: FeatureEntry;
};

function FeatureCard(props: FeatureCardProps) {
  const { entry } = props;

  return (
    <div
      className='flex sm:flex-row flex-col border border-gray-200 rounded-[2px] bg-custom-gradient-1 sm:p-6 p-4 cursor-pointer items-center overflow-hidden'
      onClick={() => {
        window.open(entry.url, '_blank');
      }}
    >
      <Image src={entry.imageSrc} alt={entry.title} width={458} height={232} className='flex flex-[50%]' />
      <div className='flex flex-col sm:px-6 px-0 sm:py-0 pt-6 flex-[50%]'>
        <div className='sm:text-[18px] text-[16px] font-semibold text-gray-900 pb-1'>{entry.title}</div>
        <div className='sm:text-[16px] text-[13px] font-normal text-gray-500'>{entry.description}</div>
        <div className='flex justify-start mt-6'>
          <Button variant='newDesignGray' toRoute={entry.url}>
            {entry.buttonText}
          </Button>
        </div>
      </div>
    </div>
  );
}

type Props = {
  className?: string;
  entries: FeatureEntry[];
};

export function RowsComponent(props: Props) {
  const { className, entries } = props;

  return (
    <div className={cn('flex items-center sm:gap-8 gap-6 sm:px-16 px-4 w-full max-w-[1260px]', className)}>
      <div className='flex flex-col w-full gap-6'>
        {entries.map((feature) => (
          <FeatureCard entry={feature} key={feature.title} />
        ))}
      </div>
    </div>
  );
}
