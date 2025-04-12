import { useCallback, useMemo, useState } from 'react';
import { useToggle } from 'usehooks-ts';
import { cn } from '@/lib/utils';
import { VideoDemo, videoDemos } from '../../StaticData/LandingStaticData';
import { SingleVideoComponent } from './SingleVideoComponent';
import { VideoDemoButton } from './VideoDemoButton';

type Props = {
  className?: string;
};

export function VideosComponent(props: Props) {
  const { className } = props;

  const [selectedVideoDemoIndex, setSelectedVideoDemoIndex] = useState(0);
  const [rewind, toggleRewind] = useToggle(false);

  const selectedVideoDemo = useMemo(() => videoDemos[selectedVideoDemoIndex], [selectedVideoDemoIndex]);

  const setSelectedVideoDemo = useCallback(
    (videoDemo: VideoDemo) => {
      if (videoDemo.videoId === selectedVideoDemo.videoId) {
        toggleRewind();
        return;
      }
      const index = videoDemos.findIndex((v) => v.videoId === videoDemo.videoId);
      if (index !== -1) {
        setSelectedVideoDemoIndex(index);
      }
    },
    [selectedVideoDemo, toggleRewind]
  );

  const onVideoEnded = useCallback(
    (videoDemo: VideoDemo) => {
      if (videoDemo.videoId !== selectedVideoDemo.videoId) {
        return;
      }
      const index = videoDemos.findIndex((v) => v.videoId === videoDemo.videoId);
      if (index !== -1) {
        if (index === videoDemos.length - 1) {
          setSelectedVideoDemoIndex(0);
        } else {
          setSelectedVideoDemoIndex(index + 1);
        }
      }
    },
    [selectedVideoDemo]
  );

  return (
    <div className={cn('flex flex-col items-center sm:px-4 px-2 w-full max-w-[1292px] gap-6', className)}>
      <div className='flex flex-wrap w-full justify-center items-center gap-4'>
        {videoDemos.map((videoDemo) => (
          <VideoDemoButton
            key={videoDemo.videoId}
            videoDemo={videoDemo}
            selectedVideoDemo={selectedVideoDemo}
            setSelectedVideoDemo={setSelectedVideoDemo}
          />
        ))}
      </div>

      <div className='flex w-full h-full border border-gray-200 rounded-[4px] overflow-hidden'>
        <div className='relative flex w-full overflow-hidden' style={{ paddingTop: '58.9%' }}>
          {videoDemos.map((videoDemo, index) => (
            <SingleVideoComponent
              key={videoDemo.videoId}
              videoDemo={videoDemo}
              index={index}
              selectedVideoDemo={selectedVideoDemo}
              rewind={rewind}
              onVideoEnded={onVideoEnded}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
