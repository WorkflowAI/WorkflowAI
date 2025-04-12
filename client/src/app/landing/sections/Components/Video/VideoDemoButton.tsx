import { cn } from '@/lib/utils';
import { VideoDemo } from '../../StaticData/LandingStaticData';

type VideoDemoButtonProps = {
  videoDemo: VideoDemo;
  selectedVideoDemo: VideoDemo;
  setSelectedVideoDemo: (videoDemo: VideoDemo) => void;
};

export function VideoDemoButton(props: VideoDemoButtonProps) {
  const { videoDemo, selectedVideoDemo, setSelectedVideoDemo } = props;

  return (
    <div
      className={cn(
        'flex items-center gap-1 px-2 py-1 rounded-[2px] border border-gray-300 hover:bg-gray-100 cursor-pointer text-gray-800 font-semibold text-[12px]',
        selectedVideoDemo.videoId === videoDemo.videoId ? 'bg-gray-200 shadow-inner' : 'bg-white'
      )}
      onClick={() => setSelectedVideoDemo(videoDemo)}
    >
      {videoDemo.icon}
      {videoDemo.name}
    </div>
  );
}
