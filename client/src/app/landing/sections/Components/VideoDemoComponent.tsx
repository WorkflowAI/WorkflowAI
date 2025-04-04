import { Stream } from '@cloudflare/stream-react';
import { cn } from '@/lib/utils';

type Props = {
  className?: string;
};

export function VideoDemoComponent(props: Props) {
  const { className } = props;

  return (
    <div className={cn('flex flex-col items-center sm:px-16 px-4 w-full max-w-[1032px]', className)}>
      <Stream
        src='c118e79228b019f3d95228bbf236b563'
        controls={true}
        muted={false}
        preload='auto'
        autoplay={false}
        loop={false}
        className='w-full h-full rounded-[2px]'
        height='1080'
        width='1920'
      />
    </div>
  );
}
