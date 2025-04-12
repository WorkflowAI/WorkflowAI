import { Stream, StreamPlayerApi } from '@cloudflare/stream-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { VideoDemo } from '../../StaticData/LandingStaticData';

type SingleVideoProps = {
  videoDemo: VideoDemo;
  index: number;
  selectedVideoDemo: VideoDemo;
  rewind: boolean;
  onVideoEnded: (videoDemo: VideoDemo) => void;
};

export function SingleVideoComponent(props: SingleVideoProps) {
  const { videoDemo, index, selectedVideoDemo, rewind } = props;
  const [isLoaded, setIsLoaded] = useState(false);

  const height = String(videoDemo.height);
  const width = String(videoDemo.width);

  const isSelected = videoDemo.videoId === selectedVideoDemo.videoId;
  const isSelectedRef = useRef(isSelected);
  isSelectedRef.current = isSelected;

  const streamRef = useRef<StreamPlayerApi>();

  const onPlay = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.play();
    }
  }, []);

  const onStop = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.pause();
      streamRef.current.currentTime = 0;
    }
  }, []);

  const onRewind = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.currentTime = 0;
      streamRef.current.play();
    }
  }, []);

  useEffect(() => {
    if (!isSelectedRef.current) {
      return;
    }
    onRewind();
  }, [rewind, onRewind]);

  useEffect(() => {
    if (isSelected && isLoaded) {
      onPlay();
    } else {
      onStop();
    }
  }, [isSelected, onPlay, onStop, isLoaded]);

  const handleCanPlay = useCallback(() => {
    setIsLoaded(true);
    if (isSelected) {
      onPlay();
    }
  }, [isSelected, onPlay]);

  return (
    <div
      key={videoDemo.videoId}
      className='absolute top-0 left-0 flex items-center justify-center w-full h-full'
      style={{ zIndex: isSelected ? 10 : index }}
    >
      <Stream
        streamRef={streamRef}
        src={videoDemo.videoId}
        controls={false}
        muted={true}
        preload='auto'
        autoplay={false}
        loop={false}
        height={height}
        width={width}
        className='w-full h-full'
        onEnded={() => props.onVideoEnded(videoDemo)}
        onCanPlay={handleCanPlay}
      />
    </div>
  );
}
