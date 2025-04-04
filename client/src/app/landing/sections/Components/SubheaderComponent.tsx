import { cn } from '@/lib/utils';
import { SubheaderElement } from '../Elements/SubheaderElement';
import { HeaderEntry } from '../StaticData/LandingStaticData';

type Props = {
  className?: string;
  entry: HeaderEntry;
  id?: string;
};

export function SubheaderComponent(props: Props) {
  const { className, entry, id } = props;

  return (
    <div
      className={cn('flex flex-col items-center sm:gap-8 gap-6 sm:px-16 px-4 w-full max-w-[1260px]', className)}
      id={id}
    >
      <SubheaderElement entry={entry} />
    </div>
  );
}
