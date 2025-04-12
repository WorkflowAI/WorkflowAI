import Image from 'next/image';
import { cn } from '@/lib/utils';
import { ImageEntry } from '../StaticData/LandingStaticData';

type Props = {
  className?: string;
  entry: ImageEntry;
  isMobile: boolean;
};

export function ImageComponent(props: Props) {
  const { className, entry, isMobile } = props;

  const imageSrc = isMobile ? entry.mobileImageSrc ?? entry.imageSrc : entry.imageSrc;
  const width = isMobile ? entry.mobileWidth ?? entry.width : entry.width;
  const height = isMobile ? entry.mobileHeight ?? entry.height : entry.height;

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
      <Image src={imageSrc} alt='Image' width={width} height={height} className='flex w-full' />
    </div>
  );
}
