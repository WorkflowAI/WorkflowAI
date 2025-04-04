import { cn } from '@/lib/utils';
import { QuoteElement } from '../Elements/QuoteElement';
import { QuoteEntry } from '../StaticData/LandingStaticData';

type Props = {
  className?: string;
  entry: QuoteEntry;
};

export function QuoteComponent(props: Props) {
  const { className, entry } = props;

  return (
    <div className={cn('flex flex-col items-center sm:gap-8 gap-6 sm:px-16 px-4 w-full max-w-[1260px]', className)}>
      <QuoteElement entry={entry} />
    </div>
  );
}
