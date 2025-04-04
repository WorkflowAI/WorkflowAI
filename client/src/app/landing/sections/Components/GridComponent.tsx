import Image from 'next/image';
import { useCallback } from 'react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';
import { QuoteElement } from '../Elements/QuoteElement';
import { FeatureEntry } from '../StaticData/LandingStaticData';

type FeatureCardProps = {
  entry: FeatureEntry;
  scrollToSuggestedFeatures: () => void;
};

function FeatureCard(props: FeatureCardProps) {
  const { entry, scrollToSuggestedFeatures } = props;

  const onClick = useCallback(() => {
    switch (entry.url) {
      case 'ScrollToSuggestedFeatures':
        scrollToSuggestedFeatures();
        break;
      default:
        window.open(entry.url, '_blank');
    }
  }, [entry.url, scrollToSuggestedFeatures]);

  return (
    <div className='flex flex-col border border-gray-200 rounded-[2px] bg-custom-gradient-1'>
      <div className={cn('flex flex-col sm:p-6 p-4', entry.url && 'cursor-pointer')} onClick={onClick}>
        <Image src={entry.imageSrc} alt={entry.title} width={458} height={232} className='flex w-full mb-6' />
        <div className='sm:text-[18px] text-[16px] font-semibold text-gray-900 pb-1'>{entry.title}</div>
        <div className='sm:text-[16px] text-[13px] font-normal text-gray-500'>{entry.description}</div>
        {entry.url && (
          <div className='flex justify-start mt-6'>
            <Button variant='newDesignGray'>{entry.buttonText}</Button>
          </div>
        )}
      </div>
      {entry.qoute && (
        <div className='flex w-full h-full sm:p-10 p-6 border-t border-gray-200'>
          <QuoteElement entry={entry.qoute} />
        </div>
      )}
    </div>
  );
}

type Props = {
  className?: string;
  entries: FeatureEntry[];
  scrollToSuggestedFeatures: () => void;
};

export function GridComponent(props: Props) {
  const { className, entries, scrollToSuggestedFeatures } = props;

  return (
    <div className={cn('flex items-center sm:px-16 px-4 w-full max-w-[1260px]', className)}>
      <div className={cn('grid w-full grid-cols-1 sm:grid-cols-1 lg:grid-cols-2 gap-6')}>
        {entries.map((feature) => (
          <FeatureCard entry={feature} key={feature.title} scrollToSuggestedFeatures={scrollToSuggestedFeatures} />
        ))}
      </div>
    </div>
  );
}
