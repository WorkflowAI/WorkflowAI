import Image from 'next/image';
import { cn } from '@/lib/utils';
import { ImageEntry } from '../StaticData/LandingStaticData';

type Props = {
  className?: string;
  entry: ImageEntry;
};

export function ImageComponent(props: Props) {
  const { className, entry } = props;

  return (
    <div
      className={cn(
        'flex flex-col items-center sm:gap-8 gap-6 sm:px-16 px-4 w-full max-w-[1260px]',
        className,
        entry.url && 'cursor-pointer'
      )}
      onClick={() => {
        if (entry.url) {
          window.open(entry.url, '_blank');
        }
      }}
    >
      <Image src={entry.imageSrc} alt='Image' width={entry.width} height={entry.height} className='flex w-full' />
    </div>
  );
}
